"""Football World endpoints (spec §54 match centre, §55 player page, §56 search, §65 demo data).

Reads are public — the world is fictional, so browsing it needs no account — but rate-limited like
the other list surfaces, and every payload carries `data_origin`, `is_demo_data` and the
disclaimer, so no client can render one of these pages without also rendering what it is.

Two things are never served: a score for a fixture that has not been played (`status='scheduled'`
rows carry NULL, not 0-0), and a number that is not in the tables. Standings are aggregated from
`real_matches` on each request rather than stored, so the league page and the fixtures page cannot
drift apart. Promotion and relegation are read the same way: the clubs this season's fixtures name
against the clubs registered in the competition today.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import limit
from app.models import (
    WORLD_DISCLAIMER,
    Competition,
    NewsArticle,
    NewsArticleLink,
    RealMatch,
    RealPlayer,
    RealPlayerMatchStat,
    RealTrainingSession,
    Team,
)
from app.services.world import search_world, web_path
from app.services.world.builder import STAT_METHOD, WORLD_VERSION
from app.services.world.sync import GATE

router = APIRouter(prefix="/world", tags=["world"])

NOT_FOUND: Final = {"code": "not_found", "message": "No such record in the generated world"}
POSITIONS: Final = ("GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST")
PLAYER_SORTS: Final = {
    "overall": RealPlayer.overall,
    "rating": RealPlayer.rating,
    "goals": RealPlayer.goals,
    "assists": RealPlayer.assists,
    "minutes": RealPlayer.minutes,
    "age": RealPlayer.age,
    "name": RealPlayer.name,
}
MATCH_STATUSES: Final = ("scheduled", "completed")


def _envelope(**payload: Any) -> dict[str, Any]:
    return {
        "data_origin": "synthetic",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": WORLD_DISCLAIMER,
        **payload,
    }


def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int, **extra: Any) -> dict[str, Any]:
    return _envelope(items=items, page=page, page_size=page_size, total=total, pages=(total + page_size - 1) // page_size if page_size else 0, **extra)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _training_row(row: RealTrainingSession) -> dict[str, Any]:
    """One demo session: what was run, how long, how hard, and the load that follows from both."""
    return {
        "id": row.id,
        "player_slug": row.player_slug,
        "player_name": row.player_name,
        "player_path": web_path("player", row.player_slug),
        "position": row.position,
        "season": row.season,
        "date": row.session_date,
        "drill_slug": row.drill_slug,
        "drill_title": row.drill_title,
        "drill_path": web_path("drill", row.drill_slug),
        "category": row.category,
        "difficulty": row.difficulty,
        "duration_min": row.duration_min,
        "rpe": row.rpe,
        "load_units": row.load_units,
        "status": row.status,
        "summary": row.summary,
    }


def _training_totals(rows: Sequence[RealTrainingSession]) -> dict[str, Any]:
    minutes = sum(row.duration_min for row in rows)
    return {
        "sessions": len(rows),
        "total_minutes": minutes,
        "total_load": sum(row.load_units for row in rows),
        "categories": sorted({row.category for row in rows}),
        "drills": sorted({row.drill_slug for row in rows}),
        "load_formula": "load_units = duration_min x rpe",
        "mean_rpe": round(sum(row.rpe for row in rows) / len(rows), 2) if rows else 0,
    }


def _one(session: Session, model: Any, ident: str) -> Any:
    """Accept either the public id or the slug — the web layer links by slug, API clients by id."""
    row = session.scalar(select(model).where(or_(model.id == ident, model.slug == ident)))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return row


def _team_brief(team: Team | None) -> dict[str, Any] | None:
    if team is None:
        return None
    return {"id": team.id, "slug": team.slug, "name": team.name, "short_name": team.short_name, "path": web_path("team", team.slug)}


def _player_brief(player: RealPlayer | None) -> dict[str, Any] | None:
    if player is None:
        return None
    return {"id": player.id, "slug": player.slug, "name": player.name, "position": player.position, "path": web_path("player", player.slug)}


def _competition_fields(competition: Competition) -> dict[str, Any]:
    return {
        "id": competition.id,
        "slug": competition.slug,
        "name": competition.name,
        "kind": competition.kind,
        "path": web_path("competition", competition.slug),
    }


def _competition_brief(competition: Competition | None) -> dict[str, Any] | None:
    return None if competition is None else _competition_fields(competition)


def _match_brief(match: RealMatch, teams: dict[str, Team] | None = None) -> dict[str, Any]:
    resolver = teams or {}
    home = resolver.get(match.home_team_id)
    away = resolver.get(match.away_team_id)
    played = match.status == "completed" and match.home_goals is not None and match.away_goals is not None
    return {
        "id": match.id,
        "slug": match.slug,
        "path": web_path("match", match.slug),
        "season": match.season,
        "round_label": match.round_label,
        "kickoff_at": _iso(match.kickoff_at),
        "venue": {"name": match.venue_name, "city": match.venue_city},
        "status": match.status,
        "home": _team_brief(home),
        "away": _team_brief(away),
        "home_goals": match.home_goals if played else None,
        "away_goals": match.away_goals if played else None,
        "score": f"{match.home_goals}-{match.away_goals}" if played else "Data unavailable",
        "summary": match.summary,
        "data_origin": match.data_origin,
        "is_demo_data": match.is_demo_data,
    }


def _player_brief_row(player: RealPlayer) -> dict[str, Any]:
    return {
        "id": player.id,
        "slug": player.slug,
        "path": web_path("player", player.slug),
        "name": player.name,
        "position": player.position,
        "secondary_positions": list(player.secondary_positions or []),
        "age": player.age,
        "nation": player.nation,
        "preferred_foot": player.preferred_foot,
        "height_cm": player.height_cm,
        "season": player.season,
        "overall": player.overall,
        "potential": player.potential,
        "archetype": player.archetype,
        "archetype_match": player.archetype_match,
        "goals": player.goals,
        "assists": player.assists,
        "appearances": player.appearances,
        "starts": player.starts,
        "minutes": player.minutes,
        "rating": player.rating,
        "form": player.form,
        "team_id": player.team_id,
        "data_origin": player.data_origin,
        "is_demo_data": player.is_demo_data,
    }


def _stat_line_row(line: RealPlayerMatchStat, players: dict[str, RealPlayer], matches: dict[str, RealMatch]) -> dict[str, Any]:
    player = players.get(line.player_id)
    match = matches.get(line.match_id)
    return {
        "id": line.id,
        "natural_key": line.natural_key,
        "match_id": line.match_id,
        "match_slug": match.slug if match else None,
        "match_path": web_path("match", match.slug) if match else None,
        "kickoff_at": _iso(match.kickoff_at) if match else None,
        "competition": _competition_brief(match.competition) if match else None,
        "player": _player_brief(player),
        "team_id": line.team_id,
        "role": line.role,
        "position": line.position,
        "minutes": line.minutes,
        "goals": line.goals,
        "assists": line.assists,
        "shots": line.shots,
        "shots_on_target": line.shots_on_target,
        "passes": line.passes,
        "passes_accurate": line.passes_accurate,
        "key_passes": line.key_passes,
        "tackles": line.tackles,
        "interceptions": line.interceptions,
        "duels_won": line.duels_won,
        "saves": line.saves,
        "fouls": line.fouls,
        "yellow_cards": line.yellow_cards,
        "red_cards": line.red_cards,
        "rating": line.rating,
        "data_origin": line.data_origin,
        "is_demo_data": line.is_demo_data,
    }


def _article_row(article: NewsArticle, links: list[NewsArticleLink] | None = None) -> dict[str, Any]:
    return {
        "id": article.id,
        "slug": article.slug,
        "path": web_path("article", article.slug),
        "title": article.title,
        "summary": article.summary,
        "category": article.category,
        "claim_class": article.claim_class,
        "season": article.season,
        "source_name": article.source_name,
        "author": article.author,
        "url": article.url,
        "published_at": _iso(article.published_at),
        "topics": list(article.topics or []),
        "entities": dict(article.entities or {}),
        "entity_links": [
            {
                "type": link.entity_type,
                "slug": link.entity_slug,
                "id": link.entity_id,
                "path": web_path(link.entity_type, link.entity_slug),
            }
            for link in (links or [])
        ],
        "data_origin": article.data_origin,
        "is_demo_data": article.is_demo_data,
    }


def _team_map(session: Session, fixtures: list[RealMatch]) -> dict[str, Team]:
    """Every club named by these fixtures, so a brief never renders half a matchup."""
    ids = {value for fixture in fixtures for value in (fixture.home_team_id, fixture.away_team_id)}
    if not ids:
        return {}
    return {found.id: found for found in session.scalars(select(Team).where(Team.id.in_(ids))).all()}


def _resolve_competition(session: Session, ident: str) -> Competition:
    competition = session.scalar(select(Competition).where(or_(Competition.id == ident, Competition.slug == ident)))
    if competition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return competition


def _resolve_team(session: Session, ident: str) -> Team:
    team = session.scalar(select(Team).where(or_(Team.id == ident, Team.slug == ident)))
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return team


def _parse_date(value: str, *, end_of_day: bool = False) -> dt.datetime:
    """`from_date`/`to_date` arrive as ISO text but must reach the driver as tz-aware datetimes."""
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "bad_date", "message": "Dates must be ISO-8601, e.g. 2026-11-08"},
        ) from exc
    if parsed.tzinfo is None:
        if end_of_day and len(value) <= 10:
            return dt.datetime.combine(parsed.date(), dt.time(23, 59, 59), tzinfo=dt.UTC)
        return parsed.replace(tzinfo=dt.UTC)
    return parsed


@router.get("/status")
def world_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """What is in the world right now — the web layer uses this instead of guessing."""
    limit(request, 60, 60, scope="world_status")
    counts = {
        "competitions": int(db.scalar(select(func.count(Competition.id))) or 0),
        "teams": int(db.scalar(select(func.count(Team.id))) or 0),
        "players": int(db.scalar(select(func.count(RealPlayer.id))) or 0),
        "matches": int(db.scalar(select(func.count(RealMatch.id))) or 0),
        "stat_lines": int(db.scalar(select(func.count(RealPlayerMatchStat.id))) or 0),
        "training_sessions": int(db.scalar(select(func.count(RealTrainingSession.id))) or 0),
        "articles": int(db.scalar(select(func.count(NewsArticle.id))) or 0),
    }
    seasons = sorted({str(row[0]) for row in db.execute(select(RealMatch.season).distinct()).all()})
    categories = sorted({str(row[0]) for row in db.execute(select(NewsArticle.category).distinct()).all()})
    return _envelope(
        version=WORLD_VERSION,
        seed=settings.world_seed,
        auto_sync=settings.world_auto_sync,
        counts=counts,
        seasons=seasons,
        news_categories=categories,
        positions=list(POSITIONS),
        stat_method=STAT_METHOD,
        gate=dict(GATE),
    )


@router.get("/competitions")
def list_competitions(
    request: Request,
    kind: str | None = Query(default=None, max_length=12),
    season: str | None = Query(default=None, max_length=12),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_competitions")
    stmt = select(Competition).order_by(Competition.kind, Competition.name)
    if kind:
        stmt = stmt.where(Competition.kind == kind)
    if season:
        stmt = stmt.where(Competition.season == season)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    team_counts = {str(row[0]): int(row[1]) for row in db.execute(select(Team.competition_id, func.count(Team.id)).group_by(Team.competition_id)).all()}
    entrants = _entrant_map(db)
    items = [
        {
            "id": row.id,
            "slug": row.slug,
            "path": web_path("competition", row.slug),
            "name": row.name,
            "country": row.country,
            "kind": row.kind,
            "tier": row.tier,
            "region": row.region,
            "season": row.season,
            "summary": row.summary,
            "team_count": max(team_counts.get(row.id, 0), len(entrants.get(row.id, ()))),
            "data_origin": row.data_origin,
            "is_demo_data": row.is_demo_data,
        }
        for row in rows
    ]
    kinds = sorted({str(row[0]) for row in db.execute(select(Competition.kind).distinct()).all()})
    return _page(items, total, page, page_size, kinds=kinds)


def _entrant_map(session: Session) -> dict[str, tuple[str, ...]]:
    """Which clubs actually appear in a competition's fixtures.

    A cup has no member clubs (`Team.competition_id` points at its league), so the draw itself is
    the only honest source of who takes part.
    """
    clubs: dict[str, set[str]] = {}
    for competition_id, home_id, away_id in session.execute(select(RealMatch.competition_id, RealMatch.home_team_id, RealMatch.away_team_id)).all():
        clubs.setdefault(str(competition_id), set()).update({str(home_id), str(away_id)})
    return {key: tuple(sorted(value)) for key, value in clubs.items()}


def _movement(db: Session, competition: Competition, season: str, registered: dict[str, Team], played: dict[str, Team]) -> dict[str, Any] | None:
    """Promotion and relegation as the stored rows tell it.

    `registered` is who the competition holds today; `played` is who its fixtures for this season
    name. The difference between the two is the set of clubs that crossed the boundary. The
    direction is the clubs' own: a move to a higher tier is promotion, a move to a lower one is
    relegation, whichever league's page is being read. Each club's old league comes from its own
    fixtures that season and its new league from its current registration.
    """
    moved = [team for team_id, team in registered.items() if team_id not in played]
    moved += [team for team_id, team in played.items() if team_id not in registered]
    if not moved:
        return None
    moved_ids = [team.id for team in moved]
    rows = db.execute(
        select(RealMatch.home_team_id, RealMatch.away_team_id, RealMatch.competition_id)
        .join(Competition, Competition.id == RealMatch.competition_id)
        .where(
            RealMatch.season == season,
            Competition.kind == "league",
            or_(RealMatch.home_team_id.in_(moved_ids), RealMatch.away_team_id.in_(moved_ids)),
        )
    ).all()
    played_in: dict[str, str] = {}
    for home_id, away_id, competition_id in rows:
        for team_id in (home_id, away_id):
            if team_id in moved_ids:
                played_in.setdefault(str(team_id), str(competition_id))
    league_ids = set(played_in.values()) | {team.competition_id for team in moved if team.competition_id}
    leagues = {row.id: row for row in db.scalars(select(Competition).where(Competition.id.in_(league_ids))).all()}

    promoted: list[dict[str, Any]] = []
    relegated: list[dict[str, Any]] = []
    for team in sorted(moved, key=lambda team: team.name):
        old = leagues.get(played_in.get(team.id, ""))
        new = leagues.get(team.competition_id or "")
        if old is None or new is None or old.tier == new.tier:
            # Without both leagues there is no direction to state; the row is still on its season
            # page and no club is silently called promoted or relegated.
            continue
        entry = {"team": _team_brief(team), "from": _competition_brief(old), "to": _competition_brief(new)}
        (promoted if new.tier < old.tier else relegated).append(entry)
    if not promoted and not relegated:
        return None
    return {"season": season, "promoted": promoted, "relegated": relegated}


@router.get("/competitions/{ident}")
def competition_detail(ident: str, request: Request, season: str | None = Query(default=None, max_length=12), db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_competition_detail")
    competition = _one(db, Competition, ident)
    wanted_season = season or competition.season
    registered = {team.id: team for team in db.scalars(select(Team).where(Team.competition_id == competition.id).order_by(Team.name)).all()}
    fixtures = list(db.scalars(select(RealMatch).where(RealMatch.competition_id == competition.id, RealMatch.season == wanted_season).order_by(RealMatch.kickoff_at)).all())
    knockout = competition.kind != "league"
    if knockout:
        # A cup draw, not a membership list: these are the clubs its fixtures name.
        teams = {**registered, **_team_map(db, fixtures)}
        movement = None
    else:
        # The stored season's table names the clubs that played it, not the clubs registered for
        # the next one: membership moves at the boundary. A later season's page has no results to
        # table yet, so it shows the membership registered for it instead.
        entrants = _team_map(db, fixtures) if wanted_season == competition.season else {}
        teams = entrants or registered
        movement = _movement(db, competition, wanted_season, registered, entrants) if entrants else None
    return _envelope(
        competition={
            **_competition_fields(competition),
            "country": competition.country,
            "tier": competition.tier,
            "region": competition.region,
            "season": competition.season,
            "summary": competition.summary,
            "data_origin": competition.data_origin,
            "is_demo_data": competition.is_demo_data,
        },
        season=wanted_season,
        standings=[] if knockout else _standings(teams, fixtures),
        teams=[_team_brief(team) for team in sorted(teams.values(), key=lambda team: team.name)],
        movement=movement,
        fixtures=[_match_brief(fixture, teams) for fixture in fixtures],
        completed=sum(1 for fixture in fixtures if fixture.status == "completed"),
        scheduled=sum(1 for fixture in fixtures if fixture.status != "completed"),
        format_note=(
            "Knockout: entrants come from the drawn fixtures and progression is the bracket itself, so no league table is shown."
            if knockout
            else "Table aggregated from the stored completed fixtures on this request."
        ),
    )


def _standings(teams: dict[str, Team], fixtures: list[RealMatch]) -> list[dict[str, Any]]:
    """Aggregated from stored fixtures only — nothing here is a stored column that could go stale."""
    table: dict[str, dict[str, Any]] = {}

    def side(team_id: str) -> dict[str, Any]:
        return table.setdefault(team_id, {"team_id": team_id, "played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0, "points": 0})

    for match in fixtures:
        if match.status != "completed" or match.home_goals is None or match.away_goals is None:
            continue
        home, away = side(match.home_team_id), side(match.away_team_id)
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += match.home_goals
        home["goals_against"] += match.away_goals
        away["goals_for"] += match.away_goals
        away["goals_against"] += match.home_goals
        if match.home_goals == match.away_goals:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += 1
            away["points"] += 1
        elif match.home_goals > match.away_goals:
            home["won"] += 1
            away["lost"] += 1
            home["points"] += 3
        else:
            away["won"] += 1
            home["lost"] += 1
            away["points"] += 3
    rows = []
    for team_id, row in table.items():
        team = teams.get(team_id)
        rows.append(
            {
                **row,
                "team": _team_brief(team),
                "name": team.name if team else "Data unavailable",
                "goal_difference": row["goals_for"] - row["goals_against"],
            }
        )
    rows.sort(key=lambda row: (-row["points"], -row["goal_difference"], -row["goals_for"], str(row["name"])))
    for position, row in enumerate(rows, start=1):
        row["position"] = position
    return rows


@router.get("/teams")
def list_teams(
    request: Request,
    competition: str | None = Query(default=None, max_length=40),
    season: str | None = Query(default=None, max_length=12),
    nation: str | None = Query(default=None, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_teams")
    stmt = select(Team).order_by(Team.name, Team.id)
    if competition:
        target = _resolve_competition(db, competition)
        stmt = stmt.where(Team.competition_id == target.id)
    if season:
        stmt = stmt.where(Team.season == season)
    if nation:
        stmt = stmt.where(Team.nation == nation)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    items = [
        {
            "id": row.id,
            "slug": row.slug,
            "path": web_path("team", row.slug),
            "name": row.name,
            "short_name": row.short_name,
            "city": row.city,
            "stadium": row.stadium,
            "capacity": row.capacity,
            "manager_name": row.manager_name,
            "formation": row.formation,
            "brand_color": row.brand_color,
            "nation": row.nation,
            "season": row.season,
            "squad_size": row.squad_size,
            "overall": row.overall,
            "competition": _competition_brief(row.competition),
            "data_origin": row.data_origin,
            "is_demo_data": row.is_demo_data,
        }
        for row in rows
    ]
    facets = {
        "seasons": sorted({str(row[0]) for row in db.execute(select(Team.season).distinct()).all()}),
        "nations": sorted({str(row[0]) for row in db.execute(select(Team.nation).distinct()).all()}),
    }
    return _page(items, total, page, page_size, **facets)


@router.get("/teams/{ident}")
def team_detail(ident: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_team_detail")
    team = _one(db, Team, ident)
    players = list(db.scalars(select(RealPlayer).where(RealPlayer.team_id == team.id).order_by(RealPlayer.overall.desc(), RealPlayer.name)).all())
    fixtures = list(db.scalars(select(RealMatch).where(or_(RealMatch.home_team_id == team.id, RealMatch.away_team_id == team.id)).order_by(RealMatch.kickoff_at.desc()).limit(40)).all())
    team_ids = {team.id: team, **_team_map(db, fixtures)}
    players_by_id = {player.id: player for player in players}
    matches_by_id = {match.id: match for match in fixtures}
    recent_match_ids = [match.id for match in fixtures if match.status == "completed"][:5]
    recent_lines = list(
        db.scalars(
            select(RealPlayerMatchStat)
            .where(RealPlayerMatchStat.team_id == team.id, RealPlayerMatchStat.match_id.in_(recent_match_ids or ["-"]))
            .order_by(RealPlayerMatchStat.match_id, RealPlayerMatchStat.minute_rank)
        ).all()
    )
    return _envelope(
        team={
            "id": team.id,
            "slug": team.slug,
            "path": web_path("team", team.slug),
            "name": team.name,
            "short_name": team.short_name,
            "city": team.city,
            "stadium": team.stadium,
            "capacity": team.capacity,
            "manager_name": team.manager_name,
            "formation": team.formation,
            "brand_color": team.brand_color,
            "nation": team.nation,
            "season": team.season,
            "squad_size": team.squad_size,
            "overall": team.overall,
            "summary": team.summary,
            "competition": _competition_brief(team.competition),
            "data_origin": team.data_origin,
            "is_demo_data": team.is_demo_data,
        },
        squad=[_player_brief_row(player) for player in players],
        fixtures=[_match_brief(match, team_ids) for match in fixtures],
        recent_stat_lines=[_stat_line_row(line, players_by_id, matches_by_id) for line in recent_lines],
        squad_notes=[
            f"Overall {team.overall} is the mean of the {len(players)} stored players, not an independent rating.",
            "Every figure is generated demo data; the club exists only inside this dataset.",
        ],
    )


@router.get("/players")
def list_players(
    request: Request,
    position: str | None = Query(default=None, max_length=8),
    team: str | None = Query(default=None, max_length=40),
    competition: str | None = Query(default=None, max_length=40),
    season: str | None = Query(default=None, max_length=12),
    min_overall: int | None = Query(default=None, ge=1, le=99),
    min_rating: float | None = Query(default=None, ge=0.0, le=10.0),
    sort: str = Query(default="overall", max_length=20),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Filter by position / club / competition / rating floor; stable, paginated ordering."""
    limit(request, 120, 60, scope="world_players")
    stmt = select(RealPlayer)
    if position:
        stmt = stmt.where(RealPlayer.position == position.upper()[:8])
    if team:
        target = _resolve_team(db, team)
        stmt = stmt.where(RealPlayer.team_id == target.id)
    if competition:
        target_competition = _resolve_competition(db, competition)
        stmt = stmt.where(RealPlayer.team_id.in_(select(Team.id).where(Team.competition_id == target_competition.id)))
    if season:
        stmt = stmt.where(RealPlayer.season == season)
    if min_overall is not None:
        stmt = stmt.where(RealPlayer.overall >= min_overall)
    if min_rating is not None:
        stmt = stmt.where(RealPlayer.rating >= min_rating)
    column = PLAYER_SORTS.get(sort, RealPlayer.overall)
    direction = column.asc() if order == "asc" else column.desc()
    stmt = stmt.order_by(direction, RealPlayer.slug)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    teams = {found.id: found for found in db.scalars(select(Team).where(Team.id.in_([row.team_id for row in rows] or ["-"]))).all()}
    return _page(
        [{**_player_brief_row(row), "club": _team_brief(teams.get(row.team_id or ""))} for row in rows],
        total,
        page,
        page_size,
        sorts=sorted(PLAYER_SORTS),
        positions=list(POSITIONS),
    )


@router.get("/players/{ident}")
def player_detail(ident: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_player_detail")
    player = _one(db, RealPlayer, ident)
    season_lines = list(
        db.scalars(
            select(RealPlayerMatchStat)
            .join(RealMatch, RealMatch.id == RealPlayerMatchStat.match_id)
            .where(RealPlayerMatchStat.player_id == player.id)
            .order_by(RealMatch.kickoff_at.desc(), RealPlayerMatchStat.id)
            .limit(300)
        ).all()
    )
    matches = {match.id: match for match in db.scalars(select(RealMatch).where(RealMatch.id.in_([line.match_id for line in season_lines] or ["-"]))).all()}
    training = list(db.scalars(select(RealTrainingSession).where(RealTrainingSession.player_id == player.id).order_by(RealTrainingSession.session_date.desc(), RealTrainingSession.drill_slug)).all())
    team = db.get(Team, player.team_id) if player.team_id else None
    return _envelope(
        player={
            **_player_brief_row(player),
            "club": _team_brief(team),
            "competition": _competition_brief(team.competition) if team else None,
            "attributes": dict(player.attributes or {}),
            "derivation_reasons": list(player.derivation_reasons or []),
            "clean_sheets": player.clean_sheets,
            "yellow_cards": player.yellow_cards,
            "red_cards": player.red_cards,
            "summary": player.summary,
            "data_origin": player.data_origin,
            "is_demo_data": player.is_demo_data,
        },
        season_stats={
            "season": player.season,
            "appearances": player.appearances,
            "starts": player.starts,
            "minutes": player.minutes,
            "goals": player.goals,
            "assists": player.assists,
            "clean_sheets": player.clean_sheets,
            "yellow_cards": player.yellow_cards,
            "red_cards": player.red_cards,
            "rating": player.rating,
            "stored_from": "real_player_match_stats",
            "matches_stored": len(season_lines),
            "consistency_check": (
                "totals equal the sum of this player's stat lines"
                if sum(line.goals for line in season_lines) == player.goals and sum(line.minutes for line in season_lines) == player.minutes
                else "totals and stat lines disagree — treat the lines as authoritative"
            ),
        },
        recent_form=[
            {
                "match_id": line.match_id,
                "match_slug": matches[line.match_id].slug,
                "match_path": web_path("match", matches[line.match_id].slug),
                "kickoff_at": _iso(matches[line.match_id].kickoff_at),
                "role": line.role,
                "position": line.position,
                "minutes": line.minutes,
                "goals": line.goals,
                "assists": line.assists,
                "rating": line.rating,
            }
            for line in season_lines[:5]
        ],
        stat_lines=[_stat_line_row(line, {player.id: player}, matches) for line in season_lines],
        training_log=_training_totals(training) | {"items": [_training_row(row) for row in training]},
        method={"rating": STAT_METHOD["rating"], "season_totals": STAT_METHOD["season_totals"]},
    )


@router.get("/training")
def list_training_sessions(
    request: Request,
    player: str | None = Query(default=None, max_length=160),
    team: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=40),
    season: str | None = Query(default=None, max_length=12),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """The demo world's training log (spec §65: 100 sessions).

    Public like the rest of the world, because every row belongs to a generated player. The
    aggregates are computed from the rows that match the filters — not stored — so the totals on
    this page and the items listed under them cannot disagree.
    """
    limit(request, 60, 60, scope="world_training")
    stmt = select(RealTrainingSession)
    if player is not None:
        stmt = stmt.where(RealTrainingSession.player_id == _one(db, RealPlayer, player).id)
    if team is not None:
        resolved = _one(db, Team, team)
        stmt = stmt.where(RealTrainingSession.team_id == resolved.id)
    if category is not None:
        stmt = stmt.where(RealTrainingSession.category == category)
    if season is not None:
        stmt = stmt.where(RealTrainingSession.season == season)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(stmt.order_by(RealTrainingSession.session_date.desc(), RealTrainingSession.player_slug, RealTrainingSession.drill_slug).offset((page - 1) * page_size).limit(page_size)).all()
    )
    categories = sorted({str(row[0]) for row in db.execute(select(RealTrainingSession.category).distinct()).all()})
    return _page(
        [_training_row(row) for row in rows],
        total,
        page,
        page_size,
        filters={"player": player, "team": team, "category": category, "season": season},
        categories=categories,
        page_totals=_training_totals(rows),
        gate={"training_sessions": GATE["training_sessions"]},
    )


@router.get("/matches")
def list_matches(
    request: Request,
    competition: str | None = Query(default=None, max_length=40),
    team: str | None = Query(default=None, max_length=40),
    season: str | None = Query(default=None, max_length=12),
    status_filter: str | None = Query(default=None, alias="status", max_length=12),
    from_date: str | None = Query(default=None, max_length=32),
    to_date: str | None = Query(default=None, max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_matches")
    stmt = select(RealMatch).order_by(RealMatch.kickoff_at.desc(), RealMatch.id)
    if competition:
        target = _resolve_competition(db, competition)
        stmt = stmt.where(RealMatch.competition_id == target.id)
    if team:
        found_team = _resolve_team(db, team)
        stmt = stmt.where(or_(RealMatch.home_team_id == found_team.id, RealMatch.away_team_id == found_team.id))
    if season:
        stmt = stmt.where(RealMatch.season == season)
    if status_filter:
        if status_filter not in MATCH_STATUSES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "bad_status", "message": f"status must be one of {MATCH_STATUSES}"})
        stmt = stmt.where(RealMatch.status == status_filter)
    if from_date:
        stmt = stmt.where(RealMatch.kickoff_at >= _parse_date(from_date))
    if to_date:
        stmt = stmt.where(RealMatch.kickoff_at <= _parse_date(to_date, end_of_day=True))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return _page([_match_brief(row, _team_map(db, rows)) for row in rows], total, page, page_size, statuses=list(MATCH_STATUSES))


@router.get("/matches/{ident}")
def match_detail(ident: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Match centre (spec §54): score, team stats and the per-player lines the score is made of."""
    limit(request, 120, 60, scope="world_match_detail")
    match = _one(db, RealMatch, ident)
    teams = {found.id: found for found in db.scalars(select(Team).where(Team.id.in_([match.home_team_id, match.away_team_id]))).all()}
    lines = list(db.scalars(select(RealPlayerMatchStat).where(RealPlayerMatchStat.match_id == match.id).order_by(RealPlayerMatchStat.minute_rank, RealPlayerMatchStat.id)).all())
    players = {found.id: found for found in db.scalars(select(RealPlayer).where(RealPlayer.id.in_([line.player_id for line in lines] or ["-"]))).all()}
    played = match.status == "completed" and match.home_goals is not None
    line_rows = [_stat_line_row(line, players, {match.id: match}) for line in lines]
    return _envelope(
        match={**_match_brief(match, teams), "stats": dict(match.stats or {}), "competition": _competition_brief(match.competition)},
        line_ups={
            side: {
                "team": _team_brief(teams.get(match.home_team_id if side == "home" else match.away_team_id)),
                "starters": [row for row in line_rows if row["team_id"] == (match.home_team_id if side == "home" else match.away_team_id) and row["role"] == "starter"],
                "substitutes": [row for row in line_rows if row["team_id"] == (match.home_team_id if side == "home" else match.away_team_id) and row["role"] != "starter"],
            }
            for side in ("home", "away")
        },
        stat_lines=line_rows if played else [],
        available=played,
        note=(None if played else "This fixture has not been played in the generated world, so there is no score, line-up or statistic to show."),
        method=STAT_METHOD if played else {},
        goals_check={
            "match_goals": int(match.home_goals or 0) + int(match.away_goals or 0) if played else 0,
            "line_up_goals": sum(row["goals"] for row in line_rows),
        }
        if played
        else {},
    )


@router.get("/news")
def list_news(
    request: Request,
    category: str | None = Query(default=None, max_length=40),
    claim_class: str | None = Query(default=None, max_length=16),
    entity_type: str | None = Query(default=None, max_length=20),
    entity: str | None = Query(default=None, max_length=200),
    season: str | None = Query(default=None, max_length=12),
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Filter by category, by claim class, or by a linked entity (`entity_type=team&entity=viremont-union`)."""
    limit(request, 120, 60, scope="world_news")
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc(), NewsArticle.id)
    if category:
        stmt = stmt.where(NewsArticle.category == category)
    if claim_class:
        stmt = stmt.where(NewsArticle.claim_class == claim_class)
    if season:
        stmt = stmt.where(NewsArticle.season == season)
    if q:
        stmt = stmt.where(NewsArticle.haystack.like(f"%{q.lower()}%"))
    if entity:
        if not entity_type:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "entity_type_required", "message": "Pass entity_type with entity"})
        stmt = stmt.where(NewsArticle.id.in_(select(NewsArticleLink.article_id).where(NewsArticleLink.entity_type == entity_type, NewsArticleLink.entity_slug == entity)))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    links = db.scalars(select(NewsArticleLink).where(NewsArticleLink.article_id.in_([row.id for row in rows] or ["-"]))).all()
    by_article: dict[str, list[NewsArticleLink]] = {}
    for link in links:
        by_article.setdefault(link.article_id, []).append(link)
    return _page(
        [_article_row(row, by_article.get(row.id, [])) for row in rows],
        total,
        page,
        page_size,
        categories=sorted({str(row[0]) for row in db.execute(select(NewsArticle.category).distinct()).all()}),
        claim_classes=["fact", "analysis", "speculation"],
    )


@router.get("/news/{ident}")
def news_detail(ident: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 120, 60, scope="world_news_detail")
    article = _one(db, NewsArticle, ident)
    links = list(db.scalars(select(NewsArticleLink).where(NewsArticleLink.article_id == article.id).order_by(NewsArticleLink.entity_type, NewsArticleLink.entity_slug)).all())
    return _envelope(
        article=_article_row(article, links),
        body=article.body,
        related=[
            {
                "type": link.entity_type,
                "slug": link.entity_slug,
                "id": link.entity_id,
                "path": web_path(link.entity_type, link.entity_slug),
            }
            for link in links
            if link.entity_type != "article"
        ][:20],
        editorial_note="Source is the local generator (`source_name='synthetic-world'`); there is no external citation because nothing was fetched.",
    )


@router.get("/search")
def unified_search(
    request: Request,
    q: str = Query(min_length=1, max_length=120),
    types: str | None = Query(default=None, max_length=80, description="comma-separated: players,teams,competitions,matches,news"),
    limit_rows: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """One query, typed and ranked results across the whole world (spec §56)."""
    limit(request, 60, 60, scope="world_search")
    wanted = [item.strip() for item in (types or "").split(",") if item.strip()] or None
    hits = search_world(db, q, types=wanted, limit=limit_rows)
    return _envelope(
        query=q,
        results=[hit.to_dict() for hit in hits],
        total=len(hits),
        types=sorted({hit.type for hit in hits}),
        note="Ranked by term overlap over the stored world rows only; no provider call and no web fetch.",
    )


__all__ = ["router"]
