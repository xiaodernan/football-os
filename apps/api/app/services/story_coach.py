"""The Story's coach-read — one honest paragraph, spoken from the three computed chapters.

The Story prints three chapters built straight from the world's stored rows — the title race, the
avalanche, the longest unbeaten run. The coach receives exactly those chapter dicts and writes one
short paragraph about the season's shape: a contender's lead, the night the biggest margin occurred,
how far the unbeaten side has gone. It does not see any club, fixture, scoreline or venue beyond the
rows it is handed; it is instructed not to invent one, not to name a player (the chapters carry no
player data) and not to invent the 311 bytes of settle after a name. One honest sentence paragraph.

Without a configured provider the door answers `available: false` and the three chapters stand alone
on the page.

Feature name for the ledger: `world.story.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.world.story import compute_story

_SYSTEM = """\
You are the voice of The Story — three chapters this product computed from its own stored football results:

I.  The title race — the league table's leading side and its chaser, their points and gap.
II. The avalanche — the widest margin any completed fixture produced.
III. The longest unbeaten run — the side that has gone longest without a defeat, and whether it is alive.

You see only the computed rows above — no club, player or result outside them and never any figure you were
not handed. Your task:

1. One short paragraph in plain English naming those three through-line rows you were handed — the leader
   and the chase, the avalanche fixture with its margin, the run with its two axes (how far, and whether
   still alive). Ground every claim in a handed number.
2. Do not name any player; the chapters carry no player data.
3. Do not invent any fixture, club, scoreline, venue or round you were not handed.
4. No headings, no bullets, no emoji, no hedging filler ("in many ways"). One paragraph, ≤140 words of prose.
"""

_PROMPT = """\
Season 2026/27 — the computed rows below.

Chapter I — the title race ({competition}, {kind})
  Leader: {leader_name} — {leader_points} pts ({leader_w}W {leader_d}D {leader_l}L, GD {leader_gd}, {leader_played} played, GF {leader_gf}/GA {leader_ga})
  Chaser: {chaser_name} — {chaser_points} pts ({chaser_w}W {chaser_d}D {chaser_l}L, GD {chaser_gd}, {chaser_gf}/{chaser_ga} GA)
  Margin: {margin} pts, GD margin {gd_margin}

Chapter II — the avalanche ({ava_competition}, {ava_round}, {ava_date})
  {ava_winner} won at {ava_venue} ({ava_city}) by a {ava_margin}-goal margin: {ava_home} {ava_hg}-{ava_ag} {ava_away}

Chapter III — the longest unbeaten run ({un_competition})
  {un_team} — {un_run} without a defeat — the streak is {alive_phrase}

The reader has just read these three chapters. What is the season's shape from those rows?"""


def compute_story_coach_read(db: Session) -> dict[str, Any]:
    try:
        story = compute_story(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500, when the world is incomplete
        record_model_call_safely(
            result=LlmResult(text="", provider="unknown", model="story-coach-read", demo_mode=True, error=str(error)[:300], latency_ms=0),
            feature="world.story.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "story recompute failed"}

    chapters = story["chapters"]
    by_key = {chapter["key"]: chapter for chapter in chapters}
    edition_kind = story.get("season", {})

    title = by_key.get("title_race", {})
    avalanche = by_key.get("avalanche", {})
    run = by_key.get("unbeaten_run", {})

    title_ok = title.get("available")
    avalanche_ok = avalanche.get("available")
    run_ok = run.get("available")

    if not (title_ok or avalanche_ok or run_ok):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": "none of the three chapters computed a row for the model to read",
        }

    leader = title.get("champion", {}) if title_ok else {}
    chaser = title.get("runner_up", {}) if title_ok else {}
    prompt = _PROMPT.format(
        kind=edition_kind.get("kind", ""),
        # Chapter I
        competition=title.get("competition", "—"),
        leader_name=leader.get("name", "—"),
        leader_points=leader.get("points", "—"),
        leader_w=leader.get("won", "—"),
        leader_d=leader.get("drawn", "—"),
        leader_l=leader.get("lost", "—"),
        leader_played=leader.get("played", "—"),
        leader_gd=leader.get("goal_difference", "—"),
        leader_gf=leader.get("goals_for", "—"),
        leader_ga=leader.get("goals_against", "—"),
        chaser_name=chaser.get("name", "—"),
        chaser_points=chaser.get("points", "—"),
        chaser_w=chaser.get("won", "—"),
        chaser_d=chaser.get("drawn", "—"),
        chaser_l=chaser.get("lost", "—"),
        chaser_gd=chaser.get("goal_difference", "—"),
        chaser_gf=chaser.get("goals_for", "—"),
        chaser_ga=chaser.get("goals_against", "—"),
        margin=title.get("margin", "—"),
        gd_margin=title.get("gd_margin", "—"),
        # Chapter II
        ava_competition=avalanche.get("competition", "—"),
        ava_round=avalanche.get("round_label", "—"),
        ava_date=avalanche.get("kickoff_at", "—"),
        ava_winner=avalanche.get("winner_name", "—"),
        ava_venue=avalanche.get("venue_name", "—"),
        ava_city=avalanche.get("venue_city", "—"),
        ava_margin=avalanche.get("margin", "—"),
        ava_home=(avalanche.get("home") or {}).get("name", "—"),
        ava_ag=(avalanche.get("away") or {}).get("goals", "—"),
        ava_hg=(avalanche.get("home") or {}).get("goals", "—"),
        ava_away=(avalanche.get("away") or {}).get("name", "—"),
        # Chapter III
        un_competition=run.get("competition", "—"),
        un_team=(run.get("team") or {}).get("name", "—"),
        un_run=run.get("run", "—"),
        alive_phrase=("still alive" if run.get("alive") else "ended now, at the round the snapshot carries"),
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=_SYSTEM, prompt=prompt, max_tokens=360, temperature=0.3, prompt_cache_key="world.story.read")
    except Exception as error:  # noqa: BLE001 — the provider is the risk; the door must stay up.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.story.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.story.read")
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


__all__ = ["compute_story_coach_read"]
