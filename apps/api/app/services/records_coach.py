"""The Record Book's coach-read — one honest paragraph spoken from the eight computed marks.

The records are computed from the world's own completed rows — the hat-trick ledger, the goal-fest,
the offence and defence clubs, the fortress, the cards fixture, the keeper's wall, the single highest
rating. The model receives exactly those eight payloads and speaks one short paragraph about the shape
of the season the rows describe. It never invents a fixture, club, player or figure beyond the snapshot;
it does not name any player not on a XI-listing the payloads carry, and it says where fewer than eight
rows computed a number and where none did.

Without a configured provider the door answers `available: false` and the book's own eight rows stand
alone on the page.

Feature name for the ledger: `world.records.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.records import compute_records

_SYSTEM = """\
You are the voice of The Record Book — eight marks computed from this product's own stored football world.
You see only the eight rows below — no club, player or result outside them, no figure you were not handed.
Your task:

1. Speak one short paragraph about the shape of the season these eight marks print together — the biggest
   haul, the goal-fest, the strongest offence and defence, the clean-sheet fortress, the cards fixture, the
   keeper's wall, and the single highest rating.
2. Name every club, player, fixture and figure exactly as the payloads print them. The offence/defence rows
   print a goals-for or conceded total; the fortress prints clean sheets; keeper_wall prints saves;
   highest_rated prints a rating with its minutes.
3. Never invent any of them. If the eight rows do not include a name, do not produce one.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — the eight computed records, printed as available.

{records_block}

The reader wants one honest paragraph about the shape of this season from these eight marks only."""


def _fmt_record(record: dict[str, Any]) -> str:
    if not record.get("available"):
        return f"- {record.get('key', '?')}: (no row computed)"
    key = record["key"]
    if key == "biggest_haul":
        player = record.get("player", {})
        team = player.get("team", {})
        match = record.get("match", {})
        return (
            f"- biggest_haul: {player.get('name', '?')} for {team.get('name', '?')} — "
            f"{record.get('goals')} goals ({record.get('assists')} assists), rating {record.get('rating')}, "
            f"in {match.get('home', {}).get('name', '?')} {match.get('home_goals')}-{match.get('away_goals')} {match.get('away', {}).get('name', '?')}"
        )
    if key == "goal_fest":
        match = record.get("match", {})
        return (
            f"- goal_fest: {record.get('goals')} goals in {match.get('home', {}).get('name', '?')} "
            f"{match.get('home_goals')}-{match.get('away_goals')} {match.get('away', {}).get('name', '?')}"
        )
    if key == "offence_club":
        return f"- offence_club: {record.get('team', {}).get('name', '?')} — {record.get('goals_for')} goals across their league games"
    if key == "defence_club":
        return f"- defence_club: {record.get('team', {}).get('name', '?')} — {record.get('goals_against')} goals conceded across their league games"
    if key == "castle":
        return f"- castle: {record.get('team', {}).get('name', '?')} — {record.get('clean_sheets')} clean sheets"
    if key == "cards_fixture":
        match = record.get("match") or {}
        return f"- cards_fixture: {record.get('weighted_cards')} weighted cards — {match.get('home', {}).get('name', '?')} vs {match.get('away', {}).get('name', '?')}"
    if key == "keeper_wall":
        return f"- keeper_wall: {record.get('player', {}).get('name', '?')} — {record.get('saves')} saves, rating {record.get('rating')}"
    if key == "highest_rated":
        return (
            f"- highest_rated: {record.get('player', {}).get('name', '?')} — rating {record.get('rating')} across "
            f"{record.get('minutes')} minutes ({record.get('goals')} goals, {record.get('assists')} assists)"
        )
    return f"- {key}: (shape unrecorded)"


def compute_records_coach_read(db: Session) -> dict[str, Any]:
    try:
        book = compute_records(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500, when the world is unavailable
        record_model_call_safely(
            result=LlmResult(text="", provider="unknown", model="records-coach-read", demo_mode=True, error=str(error)[:300], latency_ms=0),
            feature="world.records.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "records recompute failed"}

    records = book["records"]
    if not any(r.get("available") for r in records):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": "none of the eight records computed a row for the model to read",
        }

    block = "\n".join(_fmt_record(record) for record in records)
    prompt = _PROMPT.format(records_block=block)

    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=360, temperature=0.3, prompt_cache_key="world.records.read")
    except Exception as error:  # noqa: BLE001 — the provider is the risk; the door must stay up.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.records.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.records.read")
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


__all__ = ["compute_records_coach_read"]
