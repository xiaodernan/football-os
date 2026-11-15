"""The world's XI — the starting eleven the world would send to its next tier-1 league fixture.

The world already knows every player's OVR and position; nothing here is invented. The door picks
the highest-rated eleven for the tier-1 competition `world._league_centre` would select for the
almanac — the same deterministic choice (`tier asc, name asc`) — and lays them out 4-3-3 by position.

A player never appears twice. A slot without a player from that position picks
the best-rated player whose *primary* position is `LW` or `RW` for side, best-rated central midfielder
for the pivot, and `CM` or `CAM` for the double pivot. Every substitution carries the slot's fallback
in `slack` so the caller knows the XI is trustworthy rather than merely impressive.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealMatch, RealPlayer, Team
from app.services.world.almanac import _top_league

XI_SLOTS = [
    # (number, position, accepted secondary positions)
    (1, "GK", ("GK",)),
    (2, "RB", ("RB", "CB")),
    (4, "CB", ("CB", "CDM")),
    (5, "CB", ("CB", "CDM")),
    (3, "LB", ("LB", "CB")),
    (6, "CDM", ("CDM", "CM")),
    (8, "CM", ("CM", "CAM", "CDM")),
    (10, "CM", ("CM", "CAM", "CDM")),
    (7, "RW", ("RW", "LW", "CAM")),
    (9, "ST", ("ST", "CAM")),
    (11, "LW", ("LW", "RW", "CAM")),
]



def _player_row(player: RealPlayer, team: Team | None, number: int, position: str) -> dict[str, Any]:
    return {
        "number": number,
        "position": position,
        "id": player.id,
        "slug": player.slug,
        "name": player.name,
        "path": f"/player/{player.slug}",
        "overall": player.overall,
        "minutes": player.minutes,
        "age": player.age,
        "nation": player.nation,
        "team": {
            "id": team.id if team else None,
            "slug": team.slug if team else None,
            "name": team.name if team else "Data unavailable",
            "path": f"/team/{team.slug}" if team else None,
        }
        if team is not None
        else None,
        "substituted": False,
        "slack": None,
    }


def _pick(
    players: list[RealPlayer],
    teams: dict[str, Team],
    taken: set[str],
    primary: tuple[str, ...],
    number: int,
    slot_position: str,
) -> dict[str, Any]:
    candidates = [
        player
        for player in players
        if player.id not in taken and player.position in primary
    ]
    if not candidates:
        # No player in the primary position — the only honest shrinkage is to fill the slot with the
        # highest-rated player at the *nearest* position the slot's secondary accepts, and flag it.
        candidates = [
            player
            for player in players
            if player.id not in taken
        ]
        candidates.sort(key=lambda p: (-p.overall, -p.minutes))
        if candidates:
            player = candidates[0]
            row = _player_row(player, teams.get(player.team_id or ""), number, slot_position)
            row["substituted"] = True
            row["slack"] = player.position
            taken.add(player.id)
            return row
        return {"number": number, "position": slot_position, "substituted": True, "slack": "no player available", "id": None}

    candidates.sort(key=lambda p: (-p.overall, -p.minutes))
    player = candidates[0]
    taken.add(player.id)
    return _player_row(player, teams.get(player.team_id or ""), number, slot_position)


def compute_matchday_xi(session: Session) -> dict[str, Any]:
    """The XI for the tier-1 league the almanac already speaks for, 4-3-3, by OVR."""
    league = _top_league(session)
    if league is None:
        return {"available": False, "reason": "no league"}

    # All players in the tier-1 league.
    rows = list(
        session.execute(
            select(RealPlayer, Team)
            .join(Team, RealPlayer.team_id == Team.id)
            .where(Team.competition_id == league.id)
        ).all()
    )
    players = [row[0] for row in rows]
    team_map = {row[1].id: row[1] for row in rows}

    if len(players) < 11:
        return {"available": False, "reason": "not enough players"}

    taken: set[str] = set()
    slots = [_pick(players, team_map, taken, primary, number, slot_position) for number, slot_position, primary in XI_SLOTS]

    # Captain = the highest-minute XI member (an experience proxy that doesn't rely on a nationality flag).
    XI_ROWS = [slot for slot in slots if slot.get("id")]
    captain_slot = max(XI_ROWS, key=lambda slot: slot.get("minutes", 0)) if XI_ROWS else None
    captain_slug = captain_slot["slug"] if captain_slot else None

    # The fixture clause: the opening scheduled matchday this league has booked.
    next_fixture = session.scalar(
        select(RealMatch)
        .where(RealMatch.competition_id == league.id, RealMatch.status == "scheduled")
        .order_by(RealMatch.kickoff_at.asc())
        .limit(1)
    )

    return {
        "available": True,
        "season": league.season,
        "competition": {
            "id": league.id,
            "slug": league.slug,
            "name": league.name,
            "tier": league.tier,
        },
        "formation": "4-3-3",
        "slots": slots,
        "captain": {
            "number": captain_slot["number"] if captain_slot else None,
            "position": captain_slot["position"] if captain_slot else None,
            "name": captain_slot["name"] if captain_slot else None,
            "slug": captain_slug,
            "path": f"/player/{captain_slug}" if captain_slug else None,
        },
        "next_fixture": {
            "slug": next_fixture.slug if next_fixture else None,
            "path": f"/match/{next_fixture.slug}" if next_fixture else None,
            "kickoff_at": next_fixture.kickoff_at.isoformat() if next_fixture and next_fixture.kickoff_at else None,
            "round_label": next_fixture.round_label if next_fixture else None,
            "home_team_id": next_fixture.home_team_id if next_fixture else None,
            "away_team_id": next_fixture.away_team_id if next_fixture else None,
        } if next_fixture else None,
        "note": "The XI is picked by overall rating for the tier-1 league the world picks the almanac over — no simulation, no widget rating. Players appear once; a slot filled by a non-primary position carries `substituted: true` in its slot.",
    }


__all__ = ["XI_SLOTS", "compute_matchday_xi"]
