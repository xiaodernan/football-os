"""The Finals — the cup of every club's season, written by arithmetic.

Every completed cup Final in the world, computed fresh on every read: who lifted it, which
fixture produced the most goals, who was the player of the final. No provider, no stored
figure — `real_matches` and `real_player_match_stats` carry it all.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, RealMatch, RealPlayer, RealPlayerMatchStat, Team

STAT_MIN_MINUTES = 1  # every listed final starter is honest sample enough


def _side_brief(team: Team | None) -> dict[str, Any] | None:
    if team is None:
        return None
    return {"id": team.id, "slug": team.slug, "name": team.name, "path": f"/team/{team.slug}"}


def _team_cup(wins: int, cups: list[str], team: Team | None) -> dict[str, Any]:
    return {
        "team": _side_brief(team),
        "cups": wins,
        "names": list(sorted(cups)),
    }


def compute_finals(session: Session) -> dict[str, Any]:
    finals = list(
        session.scalars(
            select(RealMatch)
            .join(Competition, Competition.id == RealMatch.competition_id)
            .where(Competition.kind == "cup", RealMatch.round_label == "Final", RealMatch.status == "completed")
            .order_by(RealMatch.kickoff_at.asc())
        ).all()
    )
    if not finals:
        return {"available": False, "season": {"label": "2026/27", "kind": "7:3"}}

    competitions = {c.id: c for c in session.scalars(select(Competition)).all()}
    teams = {team.id: team for team in session.scalars(select(Team)).all()}
    final_fixtures_ids = [fixture.id for fixture in finals]
    stat_lines = list(
        session.scalars(
            select(RealPlayerMatchStat).where(RealPlayerMatchStat.match_id.in_(final_fixtures_ids))
        ).all()
    )
    players = {player.id: player for player in session.scalars(select(RealPlayer).where(RealPlayer.id.in_({line.player_id for line in stat_lines}))).all()}

    def mvp(fixture_id: str) -> dict[str, Any] | None:
        lines = [line for line in stat_lines if line.match_id == fixture_id]
        if not lines:
            return None
        slugs = {line.player_id: (found.slug if (found := players.get(line.player_id)) else "") for line in lines}
        lines.sort(key=lambda line: (-(line.rating or 0), -(line.goals or 0), -(line.assists or 0), slugs.get(line.player_id, "")))
        line = lines[0]
        player = players.get(line.player_id)
        if player is None:
            return None
        return {
            "id": player.id,
            "slug": player.slug,
            "name": player.name,
            "path": f"/player/{player.slug}",
            "overall": player.overall,
            "position": player.position,
            "rating": round(line.rating or 0, 2),
            "goals": line.goals or 0,
            "assists": line.assists or 0,
        }

    output: list[dict[str, Any]] = []
    by_club: dict[str, list[str]] = defaultdict(list)
    for fixture in finals:
        home = teams.get(fixture.home_team_id)
        away = teams.get(fixture.away_team_id)
        home_goals = fixture.home_goals or 0
        away_goals = fixture.away_goals or 0
        if home_goals > away_goals:
            winner = "home"
            winner_team = home
        elif away_goals > home_goals:
            winner = "away"
            winner_team = away
        else:
            winner = "drawn"
            winner_team = None
        competition = competitions.get(fixture.competition_id) if fixture.competition_id else None
        if winner != "drawn" and winner_team is not None and competition is not None:
            by_club[winner_team.id].append(competition.name)
        output.append(
            {
                "competition": {
                    "id": fixture.competition_id,
                    "name": competition.name if competition else fixture.competition_id,
                    "slug": competition.slug if competition else None,
                    "path": f"/competition/{competition.slug}" if competition else None,
                },
                "fixture": {
                    "id": fixture.id,
                    "slug": fixture.slug,
                    "path": f"/match/{fixture.slug}",
                    "kickoff": fixture.kickoff_at.isoformat() if fixture.kickoff_at else None,
                    "venue": fixture.venue_name,
                    "city": fixture.venue_city,
                    "season": fixture.season,
                },
                "home": _side_brief(home),
                "away": _side_brief(away),
                "home_goals": home_goals,
                "away_goals": away_goals,
                "winner": winner,
                "winning_team": _side_brief(winner_team),
                "mvp": mvp(fixture.id),
            }
        )

    cup_wins = [
        _team_cup(len(cups), cups, teams.get(club_id))
        for club_id, cups in by_club.items()
    ]
    cup_wins.sort(key=lambda row: (-row["cups"], row["names"], row["team"]["slug"] if row["team"] else ""))

    loudest = max(output, key=lambda row: (row["home_goals"] + row["away_goals"], row["fixture"]["kickoff"] or ""))
    loudest_total = loudest["home_goals"] + loudest["away_goals"]
    total_goals = sum(row["home_goals"] + row["away_goals"] for row in output)

    return {
        "available": True,
        "season": {"label": "2026/27", "kind": "7:3"},
        "finals": output,
        "stats": {
            "finals": len(output),
            "goals": total_goals,
        },
        "loudest": {
            "competition": loudest["competition"],
            "goals": loudest_total,
            "home_goals": loudest["home_goals"],
            "away_goals": loudest["away_goals"],
            "venue": loudest["fixture"]["venue"],
        },
        "cup_wins": cup_wins,
    }


__all__ = ["compute_finals"]
