"""The boundary's youth intake (M13 Phase 8 item 29).

A boundary that can retire a player must be able to add one. This module promotes from the world's
existing young players -- it never invents a player row -- and the academy's own ranks decide who is
eligible: a candidate is judged against the club's eleven by the same `academy_class` that answers the
academy page, and only `selected` or `next_in_line` candidates are signed. A promotion costs no fee,
carries the valuation's wage and contract length for the player's career-clock age, and stores its
expiry exactly as a signing does, so `expire_contracts` and the contract book treat it like any other
permanent deal.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import Career, CareerSquadMove, RealPlayer, Team
from app.services.simulation.academy import YOUTH_AGE_MAX, judge_candidates
from app.services.simulation.ageing import closed_seasons, effective_age
from app.services.simulation.profile import band_of_position

#: A single boundary signs at most this many players, however many retired: a class, not a rebuild.
MAX_YOUTH_INTAKE: Final = 4
#: How many world players are judged per boundary. The pool is sorted before it is cut, so this is a
#: bound on the academy ranking, not a random sample.
YOUTH_POOL_LIMIT: Final = 80

YOUTH_INTAKE_FORMULA: Final = (
    "youth intake = one world player at or under 21 on the career's clock, for each retiree at the "
    "boundary (at most 4); candidates are ranked by the academy's own band ranks against the club's "
    "eleven and only `selected` or `next_in_line` are signed, preferring the band the retiree vacated; "
    "fee = 0, wage and contract years = the valuation at the career-clock age, and "
    "expiry_round = round_index + contract_years × season_rounds − 1"
)


def youth_intake(
    session: Session,
    career: Career,
    *,
    round_index: int,
    season_rounds: int,
    retired: list[dict[str, Any]],
) -> dict[str, Any]:
    """Promote young world players to replace the players the boundary just retired.

    Returns the rows written and the reason nothing was written, so a boundary that retires nobody and
    a boundary whose class is empty are told apart. A challenge career, a season with no length and a
    retired list of zero all answer with `promoted = []` rather than inventing a signing.
    """
    from app.services.simulation.market import budget_position, valuation, wage_bill
    from app.services.simulation.squad import current_squad

    if int(career.challenge_window or 0) > 0:
        return _result(round_index, "a challenge career has no boundary after its window", promoted=[])
    if not retired:
        return _result(round_index, "no player retired at this boundary, so there is nothing to replace", promoted=[])
    if int(season_rounds) <= 0:
        return _result(round_index, "this career has no season length, so an intake contract has no last round", promoted=[])

    squad, _account = current_squad(session, career)
    present = {player.id for player in squad}
    offset = closed_seasons(session, career)
    vacated = [band_of_position(str(row.get("position") or "")) for row in retired]
    pool = [
        player
        for player in session.scalars(select(RealPlayer).where(RealPlayer.age <= YOUTH_AGE_MAX))
        if player.id not in present
    ]
    pool.sort(
        key=lambda player: (
            0 if band_of_position(player.position) in vacated else 1,
            -int(player.overall),
            -int(player.potential),
            player.slug,
        )
    )
    candidates = pool[:YOUTH_POOL_LIMIT]
    if not candidates:
        return _result(round_index, f"no world player at or under {YOUTH_AGE_MAX} is outside this squad", promoted=[])

    judged = {row["player_id"]: row for row in judge_candidates(session, career, squad, candidates)}
    rank = {"selected": 0, "next_in_line": 1, "off_the_pace": 2}
    eligible = [player for player in candidates if judged.get(player.id, {}).get("verdict") in ("selected", "next_in_line")]
    if not eligible:
        return _result(
            round_index,
            "every young candidate the academy judged was off the pace for this eleven",
            promoted=[],
            checked=len(candidates),
            eligible=0,
        )
    eligible.sort(
        key=lambda player: (
            0 if band_of_position(player.position) in vacated else 1,
            rank.get(str(judged[player.id]["verdict"]), 3),
            -int(player.overall),
            -int(player.potential),
            player.slug,
        )
    )
    replacements = {band_of_position(str(row.get("position") or "")): str(row.get("player_name") or "") for row in retired}
    balance = int(budget_position(session, career)["remaining"])
    standing = int(wage_bill(session, career, round_index=int(round_index))["fee"])
    ceiling = int(career.wage_ceiling or 0)
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for player in eligible:
        if len(promoted) >= min(len(retired), MAX_YOUTH_INTAKE):
            break
        price = valuation(player, age=effective_age(player, offset))
        wage = int(price["weekly_wage"])
        if ceiling > 0 and standing + wage > ceiling:
            skipped.append({"player_name": player.name, "reason": "the wage after this promotion would exceed the board's ceiling", "weekly_wage": wage})
            continue
        years = max(1, int(price["contract_years"]))
        expiry = int(round_index) + years * int(season_rounds) - 1
        band = band_of_position(player.position)
        club = session.get(Team, player.team_id) if player.team_id else None
        session.add(
            CareerSquadMove(
                id=new_public_id("mov"),
                career_id=career.id,
                round_index=int(round_index),
                kind="youth",
                player_id=player.id,
                player_slug=player.slug,
                player_name=player.name,
                position=player.position,
                fee=0,
                fee_units=career.budget_units,
                contract_years=years,
                weekly_wage=wage,
                loan_until_round=0,
                expiry_round=expiry,
                counterparty_team_id=club.id if club is not None else None,
                counterparty_name=club.name if club is not None else "",
                budget_after=balance,
                data_origin="simulation",
                is_demo_data=True,
            )
        )
        standing += wage
        promoted.append(
            {
                "player_id": player.id,
                "player_name": player.name,
                "age": effective_age(player, offset),
                "band": band,
                "verdict": str(judged[player.id]["verdict"]),
                "band_rank": judged[player.id]["band_rank"],
                "replaces": replacements.get(band, ""),
                "contract_years": years,
                "weekly_wage": wage,
                "expiry_round": expiry,
            }
        )
    session.flush()
    return {
        "round_index": int(round_index),
        "checked": len(candidates),
        "eligible": len(eligible),
        "promoted": promoted,
        "skipped": skipped,
        "wage_bill_after": standing,
        "formula": YOUTH_INTAKE_FORMULA,
        "note": "the intake reads the world's own players and writes career moves; it never creates a real_players row",
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def _result(round_index: int, reason: str, *, promoted: list[dict[str, Any]], checked: int = 0, eligible: int = 0) -> dict[str, Any]:
    return {
        "round_index": int(round_index),
        "checked": checked,
        "eligible": eligible,
        "promoted": promoted,
        "skipped": [],
        "reason": reason,
        "formula": YOUTH_INTAKE_FORMULA,
        "data_origin": "simulation",
        "is_demo_data": True,
    }
