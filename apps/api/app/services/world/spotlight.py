"""The world's spotlight — three recognitions the world cannot hide from.

Arithmetic on the stored rows, on every read, no provider call, no invented figure.
Same discipline as the rest of the world tier: every number here comes from `real_matches`,
`real_player_match_stats`, `real_players` and `teams` — exactly the way the standings chart is derived.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealMatch, RealPlayer, Team
from app.services.world.almanac import _league_centre, _player_payload, _team_payload

STAT_MIN_APPEARANCES = 10
STAT_MIN_MINUTES = 600
STAT_FIRST_SPARK_MINUTES = 300
HOME_SAMPLE_MIN = 5


def spotlight_hitman(session: Session) -> dict[str, Any]:
    """Best goals per 90 among tier-1 players with a real sample behind them."""
    league_centre = _league_centre(session)
    if not league_centre.get("available"):
        return {"key": "hitman", "available": False}
    league_id = league_centre["league"].id
    team_ids = list(session.scalars(select(Team.id).where(Team.competition_id == league_id)).all())
    players = session.scalars(select(RealPlayer).where(RealPlayer.team_id.in_(team_ids))).all()
    pool = [
        (p, p.goals * 90.0 / p.minutes if p.minutes else 0.0)
        for p in players
        if p.appearances >= STAT_MIN_APPEARANCES and p.minutes >= STAT_MIN_MINUTES
    ]
    if not pool:
        return {"key": "hitman", "available": False}
    player, per_90 = max(pool, key=lambda item: (item[1], item[0].rating, item[0].goals, item[0].slug))
    return {
        "key": "hitman",
        "available": True,
        "player": _player_payload(player, f"{per_90:.2f}"),
        "per_90": round(per_90, 2),
        "goals": player.goals,
        "minutes": player.minutes,
        "competition": league_centre["competition"],
    }


def _completed(session: Session) -> list[RealMatch]:
    fixtures = session.scalars(
        select(RealMatch)
        .where(RealMatch.status == "completed")
        .order_by(RealMatch.kickoff_at.asc())
    ).all()
    return [
        fixture for fixture in fixtures
        if fixture.home_goals is not None and fixture.away_goals is not None
    ]


def spotlight_fortress(session: Session) -> dict[str, Any]:
    """The team that keeps the most home clean sheets across the completed world."""
    fixtures = _completed(session)
    home = [fixture for fixture in fixtures if fixture.competition_id and fixture.kickoff_at]
    stats: dict[str, dict[str, Any]] = {}
    for fixture in home:
        stats.setdefault(fixture.home_team_id, {"played": 0, "clean": 0, "conceded": 0})
        stats[fixture.home_team_id]["played"] += 1
        stats[fixture.home_team_id]["conceded"] += fixture.away_goals or 0
        if (fixture.away_goals or 0) == 0:
            stats[fixture.home_team_id]["clean"] += 1
    if not stats:
        return {"key": "fortress", "available": False}
    ranked = [
        (team_id, row)
        for team_id, row in stats.items()
        if row["played"] >= HOME_SAMPLE_MIN and row["clean"] > 0
    ]
    if not ranked:
        return {"key": "fortress", "available": False}
    team_id, row = max(ranked, key=lambda item: (item[1]["clean"], -item[1]["conceded"], item[1]["played"]))
    team = session.get(Team, team_id)
    return {
        "key": "fortress",
        "available": True,
        "team": _team_payload(team),
        "clean_sheets": row["clean"],
        "played": row["played"],
        "conceded": row["conceded"],
        "competition": None,
    }


def spotlight_new_blood(session: Session) -> dict[str, Any]:
    """Tier-1's youngest player with real minutes behind them — the first spark, not a bench fillers."""
    league_centre = _league_centre(session)
    if not league_centre.get("available"):
        return {"key": "new_blood", "available": False}
    league_id = league_centre["league"].id
    team_ids = session.scalars(select(Team.id).where(Team.competition_id == league_id)).all()
    players = session.scalars(select(RealPlayer).where(RealPlayer.team_id.in_(team_ids))).all()
    pool = [player for player in players if player.minutes >= STAT_FIRST_SPARK_MINUTES]
    if not pool:
        return {"key": "new_blood", "available": False}
    player = min(pool, key=lambda player: (player.age, -player.minutes, player.slug))
    return {
        "key": "new_blood",
        "available": True,
        "player": _player_payload(player, player.minutes),
        "age": player.age,
        "minutes": player.minutes,
        "position": player.position,
        "competition": league_centre["competition"],
    }


def compute_spotlight(session: Session) -> dict[str, Any]:
    """The three recognitions, computed fresh on every read."""
    return {
        "season": {"label": "2026/27", "kind": "7:3"},
        "spotlights": [
            spotlight_hitman(session),
            spotlight_fortress(session),
            spotlight_new_blood(session),
        ],
    }


__all__ = [
    "compute_spotlight",
    "spotlight_hitman",
    "spotlight_fortress",
    "spotlight_new_blood",
]
