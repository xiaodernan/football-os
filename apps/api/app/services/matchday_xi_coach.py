"""The Matchday XI's coach-read — one honest paragraph on the eleven the world would send.

The XI is computed by OVR for the tier-1 league the almanac speaks for — a fixture-implied four-at-the-back,
three in midfield, three across the line, with one goalkeeper. The model receives exactly the XI list, the
captain, the formation, the next scheduled fixture, and speaks one short paragraph about the XI's shape. It
never invents a name; it never produces a defensive choice the rows do not support; it refuses to name a club
the snapshot does not carry.

Without a configured provider the door answers `available: false` and the XI stands alone on the page.

Feature name for the ledger: `world.matchday_xi.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.verified_phrasing import phrase_verified_complete as _verified_complete
from app.services.world.matchday_xi import compute_matchday_xi

_SYSTEM = """\
You are the voice of The Matchday XI — the eleven players this product's synthetic world would send to the
tier-1 fixture on the opening night of the season, picked by overall rating with no simulation involved. You
see exactly the list of players, their captain, the formation, and the opening fixture clause. You know nothing
else about this league. Your task:

1. Speak one short paragraph about the XI's shape — the goalkeeper, the back four, the three midfielders, the
   front three, and who wears the captain's armband and why the minutes make him the obvious pick.
2. Name every player, club and fixture exactly as the list prints them. No inventing team selections, no
   invention of formations except the one carried.
3. Never invent any player, club, fixture or figure beyond the snapshot. The XI is what it is; it was picked
   by OVR and the snapshot says so — do not pretend the world asked anyone to pick it.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — the XI the world picks by overall rating for tier-1:

League: {competition_name} (tier-1), season {season}
Formation: {formation}
Next fixture: {fixture_summary}

XI (as printed by the door):
{slots_block}
Captain: {captain_name} ({captain_position}, {captain_number})

The reader wants one honest paragraph about what this XI is and who captains it.
"""


def _fmt_slot(slot: dict[str, Any]) -> str:
    sub = " (filled by non-primary)" if slot.get("substituted") else ""
    team = (slot.get("team") or {}).get("name") if slot.get("team") else "club unknown"
    return f"  {slot['number']:>2}. {slot['position']} {slot.get('name', '?')} ({team}, OVR {slot.get('overall', '?')}){sub}"


def compute_matchday_xi_coach_read(db: Session) -> dict[str, Any]:
    try:
        xi = compute_matchday_xi(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(text="", provider="unknown", model="matchday_xi-coach-read", demo_mode=True, error=str(error)[:300], latency_ms=0),
            feature="world.matchday_xi.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "matchday XI recompute failed"}

    if not xi.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": xi.get("reason", "matchday XI could not be composed"),
        }

    next_fixture = xi.get("next_fixture") or {}
    slots_block = "\n".join(_fmt_slot(slot) for slot in xi.get("slots", []) if slot.get("id"))
    prompt = _PROMPT.format(
        competition_name=(xi.get("competition") or {}).get("name", "?"),
        season=xi.get("season", "?"),
        formation=xi.get("formation", "4-3-3"),
        fixture_summary=f"{next_fixture.get('round_label', '?')} at {next_fixture.get('kickoff_at', '?')}"
        if next_fixture.get("slug")
        else "no fixture scheduled yet",
        slots_block=slots_block,
        captain_name=(xi.get("captain") or {}).get("name", "?"),
        captain_position=(xi.get("captain") or {}).get("position", "?"),
        captain_number=(xi.get("captain") or {}).get("number", "?"),
    )

    provider = get_llm_provider()
    try:
        result = _verified_complete(provider=provider, system=_SYSTEM, prompt=prompt, feature="world.matchday_xi.read", max_tokens=360, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.matchday_xi.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.matchday_xi.read")
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


__all__ = ["compute_matchday_xi_coach_read"]
