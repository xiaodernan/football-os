"""The coach's read — one honest press on the almanac, grounded in its own figures.

The almanac prints every number the world counted. The coach receives that same arithmetic — the
golden boot, the playmaker, the complete forward, the season best performer, the breakthrough,
the discipline leader — and writes three short paragraphs a human would write for a reader, right
next to those figures. No figure invented; every claim traces to the payload the coach was
handed. Without a configured provider, the door answers `available: false` and the almanac's own
arithmetic — the awards, the title race, the running ledger — stands out loud on its own.

Feature name for the ledger: `world.almanac.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.almanac import compute_almanac

_SYSTEM = """\
You are the almanac coach for the FOOTBALL OS world. You see only this computed snapshot of the
world — no club, player or league outside it, and never any figure you were not handed. Your
task:

1. Name the edition's shape in one sentence — who leads the table on arithmetic, by how much.
2. Name the marquee stat line — the golden boot — in one sentence.
3. Answer one honest question a first-time reader would ask on opening the page.

Rules: cite exactly what was handed. No inventions. No hype. Plain English, three short
paragraphs. No headings, no bullets, no emoji.
"""

_PROMPT = """\
Snapshot of this edition:
Season: {season}
Table leader: {leader} — {points} points ({won} W, {drawn} D, {lost} L, GD {gd}) in {competition}
Golden boot: {boot_name} — {boot_goals} goals
Playmaker: {play_name} — {play_assists} assists
Complete forward: {complete_name} — {complete_gpg} combined goals-plus-assists
Player of the season: {poty_name} — rating {poty_rating}
Breakthrough: {break_name} — {break_ga} combined goals-plus-assists at age {break_age}
Discipline leader: {enforcer_name} — {cards} weighted cards

The reader opens this page once a cycle and asks "what does this edition look like?" — answer them.
"""


def _win(awards: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    return (awards.get(key) or {}).get("winner") or {}


def compute_almanac_coach_read(session: Session) -> dict[str, Any]:
    almanac = compute_almanac(session)
    awards = {row["key"]: row for row in almanac.get("awards", [])}
    best_manager = almanac.get("best_manager") or {}
    table = {
        "leader": best_manager.get("team", {}).get("name", "—"),
        "competition": best_manager.get("competition_name", "—"),
        "points": best_manager.get("points", "—"),
        "won": best_manager.get("won", "—"),
        "drawn": best_manager.get("drawn", "—"),
        "lost": best_manager.get("lost", "—"),
        "goals_for": best_manager.get("goals_for", "—"),
        "goals_against": best_manager.get("goals_against", "—"),
    }
    boot = _win(awards, "golden_boot")
    play = _win(awards, "playmaker_crown")
    complete = _win(awards, "complete_forward")
    poty = _win(awards, "player_of_season")
    breakthrough = _win(awards, "breakthrough")
    enforcer = _win(awards, "the_enforcer")

    gd = None
    if isinstance(table["goals_for"], int) and isinstance(table["goals_against"], int):
        gd = table["goals_for"] - table["goals_against"]

    prompt = _PROMPT.format(
        season=almanac.get("season", {}).get("label", "—"),
        leader=table["leader"],
        competition=table["competition"],
        points=table["points"],
        won=table["won"],
        drawn=table["drawn"],
        lost=table["lost"],
        gd=f"{gd:+d}" if gd is not None else "—",
        boot_name=boot.get("name", "—"),
        boot_goals=boot.get("stat", "—"),
        play_name=play.get("name", "—"),
        play_assists=play.get("stat", "—"),
        complete_name=complete.get("name", "—"),
        complete_gpg=complete.get("stat", "—"),
        poty_name=poty.get("name", "—"),
        poty_rating=poty.get("stat", "—"),
        break_name=breakthrough.get("name", "—"),
        break_ga=breakthrough.get("stat", "—"),
        break_age=breakthrough.get("age", "—"),
        enforcer_name=enforcer.get("name", "—"),
        cards=enforcer.get("stat", "—"),
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=420, temperature=0.4)
    except Exception as error:  # noqa: BLE001 — the provider is the risk; the door stays up.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.almanac.read")
        return {
            "available": False,
            "edition": almanac.get("season", {}).get("label", "—"),
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.almanac.read")
    if result.error:
        return {
            "available": False,
            "edition": almanac.get("season", {}).get("label", "—"),
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "edition": almanac.get("season", {}).get("label", "—"),
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


__all__ = ["compute_almanac_coach_read"]
