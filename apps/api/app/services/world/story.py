"""The season's story — three chapters, straight from the stored rows.

No chapter is authored. The world holds every fixture it ever played; the chapters below are
deterministic walks over those rows, slice by slice: the same league table the almanac prints,
the biggest margin any completed fixture produced, and the longest unbeaten streak.

Chapter I is the almanac's own title race, reused deliberately — two surfaces printing two
different champions out of the same fixtures would be a defect, not a feature, so this module
imports the exact function the almanac door serves. Chapters II and III are this module's own —
same discipline: recompute per read, never a stored column, never a provider.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, RealMatch, Team
from app.services.world.almanac import _league_centre, _title_race_from

STORY_CHAPTER_KEYS = ("title_race", "avalanche", "unbeaten_run")


def _world_context(session: Session, context: dict[str, Any] | None) -> tuple[list[RealMatch], dict[str, Team], dict[str, Competition]]:
    """The world-wide reads the avalanche chapter wants, built once per caller.

    `compute_story` builds this once and threads it; direct callers keep the
    historic standalone behaviour — identical SQL shape, identical answer.
    """
    if context is not None:
        return context["fixtures"], context["teams"], context["competitions"]
    fixtures = list(session.scalars(select(RealMatch).where(RealMatch.status == "completed")).all())
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    competitions = {c.id: c for c in session.scalars(select(Competition)).all()}
    return fixtures, teams, competitions


def chapter_avalanche(session: Session, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """The biggest margin any completed fixture produced — all competitions, cup and league alike."""
    fixtures, teams, competitions = _world_context(session, context)
    scored: list[RealMatch] = [
        f for f in fixtures if f.home_goals is not None and f.away_goals is not None
    ]
    if not scored:
        return {"key": "avalanche", "available": False}

    def goal_margin(fixture: RealMatch) -> int:
        return abs((fixture.home_goals or 0) - (fixture.away_goals or 0))

    biggest = max(scored, key=lambda f: (goal_margin(f), max(f.home_goals or 0, f.away_goals or 0)))
    home = teams.get(biggest.home_team_id)
    away = teams.get(biggest.away_team_id)
    competition = competitions.get(biggest.competition_id) if biggest.competition_id else None
    winner_id = biggest.home_team_id if (biggest.home_goals or 0) >= (biggest.away_goals or 0) else biggest.away_team_id
    winner_team = teams.get(winner_id)
    decisive_margin = goal_margin(biggest)
    if decisive_margin == 0:
        # No result separated any fixture — an "avalanche" chapter cannot be granted honesty.
        return {"key": "avalanche", "available": False}

    def side(team: Team | None, goals: int) -> dict[str, Any]:
        return {
            "id": team.id if team else None,
            "slug": team.slug if team else None,
            "name": team.name if team else "Data unavailable",
            "path": f"/team/{team.slug}" if team else None,
            "goals": goals,
        }

    return {
        "key": "avalanche",
        "available": True,
        "competition": competition.name if competition else None,
        "competition_slug": competition.slug if competition else None,
        "round_label": biggest.round_label,
        "kickoff_at": biggest.kickoff_at.isoformat() if biggest.kickoff_at else None,
        "venue_name": biggest.venue_name,
        "venue_city": biggest.venue_city,
        "match_path": f"/match/{biggest.slug}",
        "home": side(home, biggest.home_goals or 0),
        "away": side(away, biggest.away_goals or 0),
        "winner_name": winner_team.name if winner_team else "Data unavailable",
        "winner_path": f"/team/{winner_team.slug}" if winner_team else None,
        "margin": decisive_margin,
    }


def chapter_unbeaten_run(session: Session, *, centre: dict[str, Any] | None = None) -> dict[str, Any]:
    """The longest unbeaten streak of the league season (wins + draws, reset by each defeat).

    A caller that already walked the league centre passes it in — the fixtures and teams are
    the same rows, read once — so the story never opens a second league transaction for this
    chapter. Without the argument the chapter builds its standalone centre, as it always did.
    """
    if centre is None:
        centre = _league_centre(session)
    if not centre.get("available"):
        return {"key": "unbeaten_run", "available": False}

    fixtures = centre["fixtures"]
    scored = [f for f in fixtures if f.home_goals is not None and f.away_goals is not None]
    if not scored:
        return {"key": "unbeaten_run", "available": False}

    teams = centre["teams"]
    unbeaten: dict[str, int] = {}
    best: dict[str, int] = {}
    for fixture in scored:
        winner = "home" if (fixture.home_goals or 0) > (fixture.away_goals or 0) else (
            "away" if (fixture.away_goals or 0) > (fixture.home_goals or 0) else "draw"
        )
        for team_id in (fixture.home_team_id, fixture.away_team_id):
            side = "home" if team_id == fixture.home_team_id else "away"
            if winner == "draw" or winner == side:
                unbeaten[team_id] = unbeaten.get(team_id, 0) + 1
            else:
                unbeaten[team_id] = 0
            best[team_id] = max(best.get(team_id, 0), unbeaten[team_id])

    if not best:
        return {"key": "unbeaten_run", "available": False}

    team_id = max(sorted(best), key=lambda tid: best[tid])
    run = best[team_id]
    team = teams.get(team_id)

    # is the streak still alive? it lives when the team's most recent completed fixture is unbeaten
    recent = [f for f in scored if team_id in (f.home_team_id, f.away_team_id)][-1:]
    alive = False
    if recent:
        last = recent[0]
        side = "home" if team_id == last.home_team_id else "away"
        team_goals = last.home_goals if side == "home" else last.away_goals
        other_goals = last.away_goals if side == "home" else last.home_goals
        alive = (team_goals or 0) >= (other_goals or 0)

    return {
        "key": "unbeaten_run",
        "available": True,
        "competition": centre["competition"],
        "competition_slug": centre["competition_slug"],
        "team": {
            "id": team_id,
            "slug": team.slug if team else None,
            "name": team.name if team else "Data unavailable",
            "path": f"/team/{team.slug}" if team else None,
        },
        "run": run,
        "alive": bool(alive),
    }


def compute_story(session: Session) -> dict[str, Any]:
    """The whole story in deterministic chapter order.

    The world's shared rows (the full team table, the completed fixtures) are pulled once per
    call and threaded through the chapters; the league centre is built once and shared between
    chapter I and chapter III, so the streak never re-walks the league this chapter I already
    walked. The chapters keep their standalone defaults for direct callers.
    """
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    centre = _league_centre(session, teams=teams)

    title_race = _title_race_from(centre)
    if title_race.get("available"):
        chapter_one = {"key": "title_race", **title_race}
    else:
        chapter_one = {"key": "title_race", "available": False}

    competitions = {c.id: c for c in session.scalars(select(Competition)).all()}
    fixtures = list(session.scalars(select(RealMatch).where(RealMatch.status == "completed")).all())
    avalanche_context = {"fixtures": fixtures, "teams": teams, "competitions": competitions}

    return {
        "season": {"label": "2026/27", "kind": "7:3"},
        "chapters": [chapter_one, chapter_avalanche(session, avalanche_context), chapter_unbeaten_run(session, centre=centre)],
    }


__all__ = ["STORY_CHAPTER_KEYS", "chapter_avalanche", "chapter_unbeaten_run", "compute_story"]
