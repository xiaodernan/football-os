"""The predictor's ledger — the world's own noise, measured, not hidden.

The world's fixtures are not random events in a real sense: they are a seeded generator's output,
and any rating-based predictor is downstream of that seed's drawing. This module measures how
far the seed is from predictability and reads the result aloud — no provider, no simulation,
no authored "upset" claims — three plain arithmetic answers:

  * the rating-based caller's accuracy against the fixtures it cannot see,
  * the draws the caller correctly called,
  * the run of correct calls it managed, plus the five largest wrong calls.

A door that advertises predictive power it does not have is a door the line should not have.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealMatch, RealPlayer, Team
from app.services.world.almanac import _team_payload, _top_league

STRENGTH_LIMIT = 11
DRAW_WINDOW = 4.0


def _team_strength(session: Session, team_id: str) -> float | None:
    players = list(
        session.scalars(
            select(RealPlayer)
            .where(RealPlayer.team_id == team_id)
            .order_by(RealPlayer.overall.desc(), RealPlayer.slug.asc())
            .limit(STRENGTH_LIMIT)
        ).all()
    )
    return sum(player.overall for player in players) / len(players) if players else None


def _prediction(home_strength: float, away_strength: float) -> tuple[str, float]:
    diff = home_strength - away_strength
    if abs(diff) < DRAW_WINDOW:
        return "draw", diff
    return ("home" if diff > 0 else "away"), diff


def _actual(home_goals: int, away_goals: int) -> str:
    if home_goals == away_goals:
        return "draw"
    return "home" if home_goals > away_goals else "away"


def compute_noise(session: Session) -> dict[str, Any]:
    league = _top_league(session)
    if league is None:
        return {"available": False, "season": {"label": "2026/27", "kind": "7:3"}}

    fixtures = list(
        session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == league.id, RealMatch.status == "completed")
            .where(RealMatch.home_goals.is_not(None), RealMatch.away_goals.is_not(None))
            .order_by(RealMatch.kickoff_at.asc())
        ).all()
    )
    if not fixtures:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    strength_cache: dict[str, float | None] = {}
    for team_id in {fixture.home_team_id for fixture in fixtures} | {fixture.away_team_id for fixture in fixtures}:
        strength_cache[team_id] = _team_strength(session, team_id)

    correct = 0
    draw_calls = 0
    draw_hits = 0
    best_streak = 0
    streak = 0
    scored_calls: list[dict[str, Any]] = []

    for fixture in fixtures:
        home_s = strength_cache.get(fixture.home_team_id)
        away_s = strength_cache.get(fixture.away_team_id)
        if home_s is None or away_s is None:
            continue
        call, diff = _prediction(home_s, away_s)
        actual = _actual(fixture.home_goals or 0, fixture.away_goals or 0)
        hit = call == actual
        if call == "draw":
            draw_calls += 1
            if actual == "draw":
                draw_hits += 1
        if hit:
            correct += 1
            streak += 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
        home_team = teams.get(fixture.home_team_id)
        away_team = teams.get(fixture.away_team_id)
        scored_calls.append(
            {
                "slug": fixture.slug,
                "path": f"/match/{fixture.slug}",
                "kickoff_at": fixture.kickoff_at.isoformat() if fixture.kickoff_at else None,
                "home": _team_payload(home_team),
                "away": _team_payload(away_team),
                "home_goals": fixture.home_goals,
                "away_goals": fixture.away_goals,
                "called": call,
                "actual": actual,
                "hit": hit,
                "rating_gap": round(abs(diff), 2),
            }
        )

    judged = len(scored_calls)
    if judged == 0:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    upsets = sorted(
        (row for row in scored_calls if not row["hit"]),
        key=lambda row: -row["rating_gap"],
    )[:5]

    return {
        "available": True,
        "season": {"label": "2026/27", "kind": "7:3"},
        "competition": league.name,
        "competition_slug": league.slug,
        "judged": judged,
        "correct": correct,
        "wrong": judged - correct,
        "accuracy_pct": round(100 * correct / judged, 2),
        "chance_pct": round(100 / 3, 2),
        "draw_window": DRAW_WINDOW,
        "draw_calls": draw_calls,
        "draw_hits": draw_hits,
        "draw_hit_pct": round(100 * draw_hits / draw_calls, 2) if draw_calls else 0.0,
        "best_streak": best_streak,
        "upsets": upsets,
    }


__all__ = ["compute_noise"]
