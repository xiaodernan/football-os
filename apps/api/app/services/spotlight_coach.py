"""The Spotlight's coach-read — one honest paragraph on the three recognitions the world cannot hide from.

The spotlight door computes three recognitions from the stored rows on every read: the hitman
(best goals per 90 among tier-1 players with a real sample), the fortress (the most home clean
sheets across the completed world) and the new blood (the youngest tier-1 player with real minutes).
The model receives exactly those three rows and speaks one short paragraph on what they hold
up together. It never invents a player, club, figure or fourth recognition beyond the snapshot.

Without a configured provider the door answers `available: false` and the spotlight stands alone on
the page.

Feature name for the ledger: `world.spotlight.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.spotlight import compute_spotlight

_SYSTEM = """\
You are the voice of The Spotlight — three recognitions this product's synthetic world cannot hide
from: the hitman, the fortress, the new blood. You see exactly the three rows the door printed:
the player, his club's run, the figures behind each (per-90, clean sheets, minutes). You know
nothing else about this league. Your task:

1. Speak one short paragraph on what the three recognitions, together, hold up — the hitman's
   harvest, the fortress's walls, the new blood's first spark.
2. Name every player, club and figure exactly as the rows print them. No inventing players,
   clubs, ratios or recognitions the door did not compute.
3. The rows name no club, city, venue or country for the hitman or for the new blood — the
   fortress's row names a club; the other two do not. Do not print a club, city, venue or
   country for either of them; name a nation only where the row carries one.
4. A per-90 is a rate over a minimum sample, not a destiny; a fortress is a season's measurement,
   not a forecast. Do not present either as a prediction of anything.
5. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what the spotlight computed:

{blocks}

The reader wants one honest paragraph on what these three recognitions hold up together.
"""


def _hitman_block(row: dict[str, Any]) -> str:
    if not row.get("available"):
        return "  hitman — unavailable (no player met the sample floor this season)"
    player = row.get("player", {})
    return (
        f"  hitman — {player.get('name', '?')} ({player.get('position', '?')}, {player.get('nation', '?')}) · overall {player.get('overall', '?')}\n"
        f"    {row.get('goals', 0)} goals in {row.get('minutes', 0)} minutes · {row.get('per_90', '?')} per 90"
    )


def _fortress_block(row: dict[str, Any]) -> str:
    if not row.get("available"):
        return "  fortress — unavailable (no club met the home sample floor this season)"
    team = row.get("team", {})
    return (
        f"  fortress — {team.get('name', '?')}\n"
        f"    {row.get('clean_sheets', 0)} home clean sheets in {row.get('played', 0)} played · {row.get('conceded', 0)} conceded at home"
    )


def _new_blood_block(row: dict[str, Any]) -> str:
    if not row.get("available"):
        return "  new blood — unavailable (no young player met the minutes floor this season)"
    player = row.get("player", {})
    return (
        f"  new blood — {player.get('name', '?')} ({row.get('position', '?')}, age {row.get('age', '?')}, {player.get('nation', '?')})\n"
        f"    {row.get('minutes', 0)} tier-1 minutes · overall {player.get('overall', '?')}"
    )


_BLOCK_BUILDERS = {
    "hitman": _hitman_block,
    "fortress": _fortress_block,
    "new_blood": _new_blood_block,
}


def compute_spotlight_coach_read(db: Session) -> dict[str, Any]:
    try:
        spotlight = compute_spotlight(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="spotlight-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.spotlight.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "spotlight recompute failed"}

    rows = spotlight.get("spotlights", [])
    blocks = []
    for row in rows:
        builder = _BLOCK_BUILDERS.get(row.get("key", ""))
        blocks.append(builder(row) if builder else f"  {row.get('key', '?')} — unavailable")
    prompt = _PROMPT.format(blocks="\n\n".join(blocks))

    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=320, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.spotlight.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.spotlight.read")
    if result.error:
        return {
            "available": False,
            "edition": "2026/27",
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "edition": "2026/27",
        "provider": result.provider,
        "model": result.model,
        "demo_mode": result.demo_mode,
        "input_tokens": result.input_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "cache_reported": result.cache_reported,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "answer": result.text,
    }


__all__ = ["compute_spotlight_coach_read"]
