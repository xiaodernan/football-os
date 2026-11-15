"""The Gazette — the season's paper of record, written from the stored rows alone.

One edition per completed tier-1 matchday. Every fact in an edition — the table after the
round, the loudest fixture, the hot hand, the number of clean sheets — is arithmetic on
`real_matches` under the same seed every read, exactly the way the standings chart is derived.
No figure is authored, composed by a provider, or stored anywhere but the rows themselves.

Reading an edition: `edition` is the matchday number; omitted, it reads the latest the world
has played. `out_of_range` answers `available: false` — the API door turns it into a 422 — never
an invented dateline.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealMatch, Team
from app.services.world.almanac import _top_league
from app.services.world.timeline import _round_of


def _fixture_brief(fixture: RealMatch, teams: dict[str, Team], *, include_score: bool = True) -> dict[str, Any]:
    home = teams.get(fixture.home_team_id)
    away = teams.get(fixture.away_team_id)

    def side(team: Team | None) -> dict[str, Any]:
        if team is None:
            return {"id": None, "slug": None, "name": "Data unavailable", "path": None}
        return {"id": team.id, "slug": team.slug, "name": team.name, "path": f"/team/{team.slug}"}

    home_goals = fixture.home_goals or 0
    away_goals = fixture.away_goals or 0
    return {
        "id": fixture.id,
        "slug": fixture.slug,
        "path": f"/match/{fixture.slug}",
        "kickoff": fixture.kickoff_at.isoformat() if fixture.kickoff_at else None,
        "venue": fixture.venue_name,
        "city": fixture.venue_city,
        "home": side(home),
        "away": side(away),
        **({"home_goals": home_goals, "away_goals": away_goals, "score": f"{home_goals}-{away_goals}"} if include_score else {}),
    }


def _table_snapshot(played: list[RealMatch]) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}

    def row(team_id: str) -> dict[str, Any]:
        return table.setdefault(
            team_id,
            {"team_id": team_id, "played": 0, "won": 0, "drawn": 0, "lost": 0,
             "goals_for": 0, "goals_against": 0, "points": 0},
        )

    for fixture in played:
        if fixture.home_goals is None or fixture.away_goals is None:
            continue
        home = fixture.home_team_id
        away = fixture.away_team_id
        for team_id, on_home in ((home, True), (away, False)):
            stats = row(team_id)
            gf = fixture.home_goals if on_home else fixture.away_goals
            ga = fixture.away_goals if on_home else fixture.home_goals
            stats["played"] += 1
            stats["goals_for"] += gf or 0
            stats["goals_against"] += ga or 0
            if fixture.home_goals == fixture.away_goals:
                stats["drawn"] += 1
                stats["points"] += 1
            elif (on_home and fixture.home_goals > fixture.away_goals) or (not on_home and fixture.away_goals > fixture.home_goals):
                stats["won"] += 1
                stats["points"] += 3
            else:
                stats["lost"] += 1
    return table


def _table_rows(table: dict[str, dict[str, Any]], teams: dict[str, Team]) -> list[dict[str, Any]]:
    rows = sorted(
        table.values(),
        key=lambda r: (-r["points"], -(r["goals_for"] - r["goals_against"]), -r["goals_for"]),
    )
    out: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        team = teams.get(row["team_id"])
        brief = {
            "id": row["team_id"],
            "slug": team.slug if team else None,
            "name": team.name if team else "Data unavailable",
            "path": f"/team/{team.slug}" if team else None,
        }
        out.append(
            {
                "position": position,
                "team": brief,
                "played": row["played"],
                "won": row["won"],
                "drawn": row["drawn"],
                "lost": row["lost"],
                "goals_for": row["goals_for"],
                "goals_against": row["goals_against"],
                "goal_difference": row["goals_for"] - row["goals_against"],
                "points": row["points"],
            }
        )
    return out


def compute_gazette(session: Session, edition: int | None = None) -> dict[str, Any]:
    league = _top_league(session)
    if league is None:
        return {"available": False, "season": {"label": "2026/27", "kind": "7:3"}}

    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    fixtures = list(
        session.scalars(
            select(RealMatch)
            .where(RealMatch.competition_id == league.id, RealMatch.status == "completed")
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

    by_matchday: dict[int, list[RealMatch]] = defaultdict(list)
    for fixture in fixtures:
        number = _round_of(fixture.round_label)
        if number is not None:
            by_matchday[number].append(fixture)

    if not by_matchday:
        return {
            "available": False,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
        }

    latest = max(by_matchday)
    edition_value = edition if edition is not None else latest
    if edition_value < 1 or edition_value > latest:
        return {
            "available": False,
            "out_of_range": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": league.name,
            "competition_slug": league.slug,
            "total_editions": latest,
        }

    round_fixtures = sorted(by_matchday[edition_value], key=lambda f: f.kickoff_at or 0)
    played_so_far = [fixture for number in sorted(by_matchday) if number <= edition_value for fixture in by_matchday[number]]
    table = _table_snapshot(played_so_far)
    table_rows = _table_rows(table, teams)
    leader = table_rows[0] if table_rows else None
    runner = table_rows[1] if len(table_rows) > 1 else None

    goals = sum((fixture.home_goals or 0) + (fixture.away_goals or 0) for fixture in round_fixtures)
    draws = sum(1 for fixture in round_fixtures if fixture.home_goals == fixture.away_goals)
    clean_sheets = sum(
        1 for fixture in round_fixtures
        if fixture.away_goals == 0 or fixture.home_goals == 0
    )
    loudest = max(round_fixtures, key=lambda f: ((f.home_goals or 0) + (f.away_goals or 0), f.kickoff_at or 0))

    # the hot hand: the club that put the most past anyone this round (own goal for either side counted for its side)
    by_club: dict[str, int] = defaultdict(int)
    for fixture in round_fixtures:
        by_club[fixture.home_team_id] += fixture.home_goals or 0
        by_club[fixture.away_team_id] += fixture.away_goals or 0
    def hot_hand_key(item: tuple[str, int]) -> tuple[int, str]:
        team = teams.get(item[0])
        return item[1], team.slug if team else ""

    hot_team_id, hot_goals = max(by_club.items(), key=hot_hand_key)
    hot_team = teams.get(hot_team_id)

    season_average = sum(
        (fixture.home_goals or 0) + (fixture.away_goals or 0) for fixture in fixtures
    ) / len(by_matchday)

    kickoffs = [fixture.kickoff_at for fixture in round_fixtures if fixture.kickoff_at]
    published_at = max(kickoffs).isoformat() if kickoffs else None

    return {
        "available": True,
        "season": {"label": "2026/27", "kind": "7:3"},
        "edition": edition_value,
        "total_editions": latest,
        "published_at": published_at,
        "competition": {"name": league.name, "slug": league.slug, "path": f"/competition/{league.slug}"},
        "scorecard": [_fixture_brief(fixture, teams) for fixture in round_fixtures],
        "table_after": table_rows,
        "table_leader": leader,
        "table_gap": (leader["points"] - runner["points"]) if (leader and runner) else 0,
        "lead": _fixture_brief(loudest, teams),
        "hot_hand": {
            "team": (
                {"slug": hot_team.slug, "name": hot_team.name, "path": f"/team/{hot_team.slug}", "id": hot_team.id}
                if hot_team
                else None
            ),
            "goals": hot_goals,
        },
        "number": {
            "goals_this_round": goals,
            "draws": draws,
            "clean_sheets": clean_sheets,
            "season_average_goals": round(season_average, 2),
            "fixtures": len(round_fixtures),
        },
        "archive": list(range(1, latest + 1)),
    }


__all__ = ["compute_gazette"]
