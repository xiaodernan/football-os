"""The record book — eight marks, computed from the stored rows on every read.

The almanac honours individuals (goals, assists, rating); the story tells the season
(chapters); this module records the *fixtures and season aggregates* the world produced.
No mark is authored, no figure is cached, every number re-derived from `real_matches` and
`real_player_match_stats` on the request that prints it — exactly the discipline the rest of
the world tier keeps.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Competition, RealMatch, RealPlayer, RealPlayerMatchStat, Team

RECORD_KEYS = (
    "biggest_haul",
    "goal_fest",
    "offence_club",
    "defence_club",
    "castle",
    "cards_fixture",
    "keeper_wall",
    "highest_rated",
)

MIN_MINUTES_FOR_RATING = 60


def _team_payload(team: Team | None) -> dict[str, Any]:
    if team is None:
        return {"name": "Data unavailable", "slug": None, "path": None}
    return {"id": team.id, "slug": team.slug, "name": team.name, "path": f"/team/{team.slug}"}


def _player_payload(player: RealPlayer | None, team: Team | None = None) -> dict[str, Any]:
    if player is None:
        return {"name": "Data unavailable", "slug": None, "path": None}
    payload: dict[str, Any] = {
        "id": player.id,
        "slug": player.slug,
        "name": player.name,
        "path": f"/player/{player.slug}",
    }
    if team is not None:
        payload["team"] = _team_payload(team)
    return payload


def _match_payload(fixture: RealMatch, teams: dict[str, Team]) -> dict[str, Any]:
    return {
        "slug": fixture.slug,
        "path": f"/match/{fixture.slug}",
        "kickoff_at": fixture.kickoff_at.isoformat() if fixture.kickoff_at else None,
        "round_label": fixture.round_label,
        "home": _team_payload(teams.get(fixture.home_team_id)),
        "away": _team_payload(teams.get(fixture.away_team_id)),
        "home_goals": fixture.home_goals,
        "away_goals": fixture.away_goals,
    }


def _league(session: Session) -> Competition | None:
    """The tier-1 league — the same selection `_top_league` makes for the almanac and story."""
    return session.scalar(
        select(Competition)
        .where(Competition.kind == "league")
        .order_by(Competition.tier.asc(), Competition.name.asc())
        .limit(1)
    )


def _completed(session: Session) -> list[RealMatch]:
    fixtures = session.scalars(
        select(RealMatch).where(RealMatch.status == "completed").order_by(RealMatch.kickoff_at.asc())
    ).all()
    return [f for f in fixtures if f.home_goals is not None and f.away_goals is not None]


def biggest_haul(session: Session) -> dict[str, Any]:
    """Most goals by one player in a single fixture — the hat-trick ledger."""
    rows = session.execute(
        select(RealPlayerMatchStat, RealPlayer, RealMatch, Team)
        .join(RealPlayer, RealPlayer.id == RealPlayerMatchStat.player_id)
        .join(RealMatch, RealMatch.id == RealPlayerMatchStat.match_id)
        .join(Team, Team.id == RealPlayerMatchStat.team_id)
        .where(RealPlayerMatchStat.goals > 0)
        .order_by(RealPlayerMatchStat.goals.desc(), RealPlayerMatchStat.rating.desc())
        .limit(1)
    ).all()
    if not rows:
        return {"key": "biggest_haul", "available": False}
    stat, player, fixture, team = rows[0]
    fixtures = _completed(session)
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    related = next((f for f in fixtures if f.id == fixture.id), fixture)
    return {
        "key": "biggest_haul",
        "available": True,
        "player": _player_payload(player, team),
        "goals": stat.goals,
        "rating": stat.rating,
        "assists": stat.assists,
        "match": _match_payload(related, teams),
    }


def goal_fest(session: Session) -> dict[str, Any]:
    """The highest-scoring completed fixture, league and cup alike."""
    fixtures = _completed(session)
    if not fixtures:
        return {"key": "goal_fest", "available": False}
    best = max(
        fixtures,
        key=lambda f: ((f.home_goals or 0) + (f.away_goals or 0), max(f.home_goals or 0, f.away_goals or 0)),
    )
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    return {
        "key": "goal_fest",
        "available": True,
        "goals": (best.home_goals or 0) + (best.away_goals or 0),
        "match": _match_payload(best, teams),
    }


def offence_club(session: Session) -> dict[str, Any]:
    """The club with the most goals scored across the completed league fixtures."""
    league = _league(session)
    if league is None:
        return {"key": "offence_club", "available": False}
    tally = _goals_by_club(session, league, "for")
    return _top_club_record("offence_club", tally, session, figure="goals_for")


def defence_club(session: Session) -> dict[str, Any]:
    """The club with the fewest goals conceded across the completed league fixtures."""
    league = _league(session)
    if league is None:
        return {"key": "defence_club", "available": False}
    tally = _goals_by_club(session, league, "against")
    # fewest conceded is the *lowest* figure — pick the smallest, not the largest
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    if not tally:
        return {"key": "defence_club", "available": False}
    team_id, conceded = min(tally.items(), key=lambda kv: (kv[1], kv[0]))
    team = teams.get(team_id)
    played = sum(1 for f in _completed_league(session, league) if team_id in (f.home_team_id, f.away_team_id))
    return {
        "key": "defence_club",
        "available": True,
        "team": _team_payload(team),
        "goals_against": conceded,
        "played": played,
        "competition": league.name,
        "competition_slug": league.slug,
    }


def castle(session: Session) -> dict[str, Any]:
    """The club with the most clean sheets kept across the completed league fixtures."""
    league = _league(session)
    if league is None:
        return {"key": "castle", "available": False}
    fixtures = _completed_league(session, league)
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    sheets: dict[str, int] = {}
    for fixture in fixtures:
        for team_id, scored_against in ((fixture.home_team_id, fixture.away_goals), (fixture.away_team_id, fixture.home_goals)):
            if scored_against == 0:
                sheets[team_id] = sheets.get(team_id, 0) + 1
    if not sheets:
        return {"key": "castle", "available": False}
    team_id, clean = max(sheets.items(), key=lambda kv: (kv[1], kv[0]))
    team = teams.get(team_id)
    return {
        "key": "castle",
        "available": True,
        "team": _team_payload(team),
        "clean_sheets": clean,
        "competition": league.name,
        "competition_slug": league.slug,
    }


def cards_fixture(session: Session) -> dict[str, Any]:
    """The fixture with the most weighted cards across both teams (yellow×1 + red×3)."""
    weighted = (
        select(
            RealPlayerMatchStat.match_id.label("match_id"),
            func.sum(RealPlayerMatchStat.yellow_cards + 3 * RealPlayerMatchStat.red_cards).label("cards"),
        )
        .group_by(RealPlayerMatchStat.match_id)
        .order_by(func.sum(RealPlayerMatchStat.yellow_cards + 3 * RealPlayerMatchStat.red_cards).desc())
        .limit(1)
    )
    row = session.execute(weighted).first()
    if row is None or row.cards is None or row.cards == 0:
        return {"key": "cards_fixture", "available": False}
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    fixture = session.get(RealMatch, row.match_id)
    return {
        "key": "cards_fixture",
        "available": True,
        "weighted_cards": int(row.cards),
        "match": _match_payload(fixture, teams) if fixture is not None else None,
    }


def keeper_wall(session: Session) -> dict[str, Any]:
    """The single-match wall — most saves by one player in a completed fixture."""
    rows = session.execute(
        select(RealPlayerMatchStat, RealPlayer, RealMatch, Team)
        .join(RealPlayer, RealPlayer.id == RealPlayerMatchStat.player_id)
        .join(RealMatch, RealMatch.id == RealPlayerMatchStat.match_id)
        .join(Team, Team.id == RealPlayerMatchStat.team_id)
        .where(RealPlayerMatchStat.saves > 0)
        .order_by(RealPlayerMatchStat.saves.desc(), RealPlayerMatchStat.rating.desc())
        .limit(1)
    ).all()
    if not rows:
        return {"key": "keeper_wall", "available": False}
    stat, player, fixture, team = rows[0]
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    return {
        "key": "keeper_wall",
        "available": True,
        "player": _player_payload(player, team),
        "saves": stat.saves,
        "rating": stat.rating,
        "match": _match_payload(fixture, teams),
    }


def highest_rated(session: Session) -> dict[str, Any]:
    """The best single-match rating across the completed world (≥60 minutes)."""
    rows = session.execute(
        select(RealPlayerMatchStat, RealPlayer, RealMatch, Team)
        .join(RealPlayer, RealPlayer.id == RealPlayerMatchStat.player_id)
        .join(RealMatch, RealMatch.id == RealPlayerMatchStat.match_id)
        .join(Team, Team.id == RealPlayerMatchStat.team_id)
        .where(RealPlayerMatchStat.minutes >= MIN_MINUTES_FOR_RATING)
        .order_by(RealPlayerMatchStat.rating.desc(), RealPlayerMatchStat.minutes.desc())
        .limit(1)
    ).all()
    if not rows:
        return {"key": "highest_rated", "available": False}
    stat, player, fixture, team = rows[0]
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    return {
        "key": "highest_rated",
        "available": True,
        "player": _player_payload(player, team),
        "rating": stat.rating,
        "minutes": stat.minutes,
        "goals": stat.goals,
        "assists": stat.assists,
        "match": _match_payload(fixture, teams),
    }


def _goals_by_club(session: Session, league: Competition, direction: str) -> dict[str, int]:
    tally: dict[str, int] = {}
    for fixture in _completed_league(session, league):
        for team_id, own, other in (
            (fixture.home_team_id, fixture.home_goals, fixture.away_goals),
            (fixture.away_team_id, fixture.away_goals, fixture.home_goals),
        ):
            if direction == "for":
                tally[team_id] = tally.get(team_id, 0) + (own or 0)
            else:
                tally[team_id] = tally.get(team_id, 0) + (other or 0)
    return tally


def _completed_league(session: Session, league: Competition) -> list[RealMatch]:
    return [
        f
        for f in session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == league.id, RealMatch.status == "completed")
            .order_by(RealMatch.kickoff_at.asc())
        ).all()
        if f.home_goals is not None and f.away_goals is not None
    ]


def _top_club_record(key: str, tally: dict[str, int], session: Session, *, figure: str) -> dict[str, Any]:
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    league = _league(session)
    if not tally:
        return {"key": key, "available": False}
    team_id, total = max(tally.items(), key=lambda kv: (kv[1], kv[0]))
    return {
        "key": key,
        "available": True,
        "team": _team_payload(teams.get(team_id)),
        figure: total,
        "competition": league.name if league else None,
        "competition_slug": league.slug if league else None,
    }


def compute_records(session: Session) -> dict[str, Any]:
    """Every record in the book, computed from the world's own rows."""
    return {
        "season": {"label": "2026/27", "kind": "7:3"},
        "records": [
            biggest_haul(session),
            goal_fest(session),
            offence_club(session),
            defence_club(session),
            castle(session),
            cards_fixture(session),
            keeper_wall(session),
            highest_rated(session),
        ],
    }


__all__ = ["RECORD_KEYS", "MIN_MINUTES_FOR_RATING", "compute_records"]
