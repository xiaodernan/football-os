"""A career's own clock: how many seasons it has closed, and what that does to a player's age.

The world stores one `real_players.age` per player and every career shares it. A career that simply
incremented that column would age every other manager's squad, and a world re-sync would undo it. This
module keeps the clock on the career: a player's *effective* age in this career is the stored age plus
the seasons this career has closed. Nothing here writes a player row.

The boundary that retires players (item 28) reads the same helper, so the age a page prints, the age a
valuation uses and the age a retirement decides on are one number.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Career, CareerSeason, CareerSquadMove, RealPlayer

#: The age at which a career's boundary retires a player. Higher than the age-profile flag (35), which
#: warns about a player rather than ending a career: a squad can carry a 37-year-old and still choose to.
RETIREMENT_AGE: int = 40

#: The move kind the boundary writes when a player's career-clock age reaches `RETIREMENT_AGE`.
RETIRE_KIND: str = "retire"


def closed_seasons(session: Session, career: Career) -> int:
    """How many boundary decisions this career has written — its age offset for the season to come."""
    return int(
        session.scalar(
            select(func.count()).select_from(CareerSeason).where(CareerSeason.career_id == career.id)
        )
        or 0
    )


def effective_age(player: RealPlayer, closed: int) -> int:
    """The player's age in this career: the world's stored age plus the seasons the career has closed."""
    return int(player.age) + max(0, int(closed))


def retire_at_boundary(session: Session, career: Career, *, round_index: int, closed: int) -> dict[str, Any]:
    """Retire this career's squad members whose career-clock age has reached `RETIREMENT_AGE`.

    Called by `close_season` once the boundary row is written, with `closed` counting that row, so the
    age measured here is the age the next season's pages and valuations will use. A retirement is a
    `retire` move at the first round of the coming season: the player played the season that just
    closed and is gone from the squad overlay when the next round is picked. It carries no fee and no
    wage after it, because retiring is neither a sale nor a payment.

    The squad still has to field a side. Candidates are walked oldest first, and one is retained when
    letting them go would leave fewer than eleven players or no goalkeeper; the returned `retained`
    entries say which and why. A challenge career has no season after its window, so nothing is
    retired there — its one row already answers every later boundary.
    """
    # Local imports: `market` and `squad` both import this module, and this is the one place the clock
    # has to reach back into the ledger and the squad overlay.
    from app.services.simulation.market import budget_position, held_deals
    from app.services.simulation.squad import can_field_side, current_squad

    if int(career.challenge_window or 0) > 0:
        return {
            "round_index": int(round_index),
            "retirement_age": int(RETIREMENT_AGE),
            "checked": 0,
            "retired": [],
            "retained": [],
            "note": "a challenge career has one season and no boundary after it, so nothing is retired",
        }
    squad, account = current_squad(session, career)
    balance = int(budget_position(session, career)["remaining"])
    held = {move.player_id: move for move in held_deals(session, career.id, round_index)}
    working = list(squad)
    candidates = sorted(
        (player for player in working if effective_age(player, closed) >= RETIREMENT_AGE),
        key=lambda player: (-effective_age(player, closed), player.slug),
    )
    retired: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for player in candidates:
        age = effective_age(player, closed)
        fielding = can_field_side(working, dropping_id=player.id)
        if not fielding["ok"]:
            retained.append(
                {
                    "player_id": player.id,
                    "player_name": player.name,
                    "age": age,
                    "players": fielding["players"],
                    "keepers": fielding["keepers"],
                    "reason": "retiring this player would leave the club below eleven players or without a keeper",
                }
            )
            continue
        deal = held.get(player.id)
        session.add(
            CareerSquadMove(
                id=new_public_id("mov"),
                career_id=career.id,
                round_index=int(round_index),
                kind=RETIRE_KIND,
                player_id=player.id,
                player_slug=player.slug,
                player_name=player.name,
                position=player.position,
                fee=0,
                fee_units=career.budget_units,
                contract_years=int(deal.contract_years) if deal is not None else 0,
                weekly_wage=int(deal.weekly_wage) if deal is not None else 0,
                loan_until_round=0,
                expiry_round=0,
                budget_after=balance,
                data_origin="simulation",
                is_demo_data=True,
            )
        )
        working.remove(player)
        retired.append(
            {
                "player_id": player.id,
                "player_name": player.name,
                "age": age,
                "weekly_wage": int(deal.weekly_wage) if deal is not None else 0,
                "round_index": int(round_index),
            }
        )
    session.flush()
    return {
        "round_index": int(round_index),
        "retirement_age": int(RETIREMENT_AGE),
        "checked": len(candidates),
        "retired": retired,
        "retained": retained,
        "squad_before": int(account["squad_now"]),
        "squad_after": len(working),
    }
