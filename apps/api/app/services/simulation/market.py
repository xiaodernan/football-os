"""The transfer market (M6, spec §22): a price, a need, and a squad the engine can see.

Before this module a career carried a budget the product admitted it could not spend. §22 asks for a
market with `Player / Club / Need / Budget / Contract / Age / Potential / Role / Tactical Fit` and the
actions `Buy / Sell / Loan / Release / Contract / Negotiation / Clauses`, so every one of those words
is answered below by a number that was *measured from stored rows* and a formula printed beside it:

* **Player, Club, Age, Potential** — the generated world's own `real_players` and `teams` rows. The
  market moves those rows' players; it never writes a player of its own.
* **Need** — the weakest of the four band indices the engine would play with, so what the market
  offers follows from the club's actual squad rather than from a mood.
* **Budget** — `budget_position` sums this career's own ledger and publishes the arithmetic: the four
  squad-move kinds, and one wage charge per round it played. A fee that is not on the ledger cannot be
  spent, and a balance that does not add up is a defect.
* **Tactical Fit, Role** — the player's band index (the same (mean−28)/68 measurement the engine
  reports for that band) blended with whether that band is the one the club is short in.
* **Contract, Negotiation, Clauses** — a valuation that yields a wage, a length of deal and a release
  clause, a seller that answers an offer by a published rule, and a clause that is the only way into a
  rival's squad.

Two things this module deliberately does not pretend to do. The wage bill it charges is the bill for the
deals *this career made* — the players on the club's stored rows are not charged, because their contracts
belong to the world every career shares, and this is stated rather than left implied. And a deal is not an
opinion about a real transfer window: these are generated clubs, and every response carries the fiction
disclaimer.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import (
    BUDGET_FORMULA,
    MOVE_EFFECT,
    WAGE_EFFECT,
    Career,
    CareerSquadMove,
    CareerWageCharge,
    RealPlayer,
    Team,
    TransferListing,
)
from app.services.simulation.challenges import challenge_by_slug
from app.services.simulation.profile import BAND_ATTRIBUTES, BANDS, band_index, band_of_position, team_profile
from app.services.simulation.squad import (
    IN_KINDS,
    can_field_side,
    current_squad,
    effective_kind,
    moves_as_of,
    squad_as_of,
    squad_state,
)

MARKET_DISCLAIMER: Final = (
    "The market is part of the same fiction as the career: these are generated clubs and generated "
    "players, the prices are arithmetic this project runs on its own rows, and nothing here reports a "
    "real transfer, a real fee or a real contract."
)

# --- the valuation's constants, published rather than hidden ------------------------------------------------
MARKET_SIZE: Final = 12
MAX_NEGOTIATION_ROUNDS: Final = 3
DEFAULT_LOAN_ROUNDS: Final = 4
NEGOTIATION_FLOOR_SHARE: Final = 0.8
RELEASE_CLAUSE_SHARE: Final = 1.5
LOAN_FEE_SHARE: Final = 0.15
SELL_PROCEEDS_SHARE: Final = 0.9
OVERALL_FLOOR: Final = 40
QUALITY_CREDIT: Final = 45_000
HEADROOM_CREDIT: Final = 25_000
WAGE_DIVISOR: Final = 500
PEAK_AGE_END: Final = 27
CONTRACT_MAX_YEARS: Final = 5
CREDIT_ROUND: Final = 5
# Age is the one input a club cannot train, so the curve is stated in bands rather than as a fitted line.
AGE_CURVE: Final = ((16, 20, 0.60), (21, 23, 0.90), (24, 27, 1.00), (28, 31, 0.75), (32, 99, 0.45))

VALUATION_FORMULA: Final = (
    "asking = round_5( ((overall − 40) × 45,000 + max(0, potential − overall) × 25,000) × age_curve ); "
    "age_curve = 0.60 at 16–20, 0.90 at 21–23, 1.00 at 24–27, 0.75 at 28–31, 0.45 at 32 and over; "
    "release_clause = round_5(asking × 1.5); weekly_wage = round_5(asking ÷ 500), and never below the 5-credit round; "
    "contract_years = 5 − max(0, age − 27), clamped to 1–5"
)
NEED_FORMULA: Final = (
    "the weakest of the four band indices this club's side would carry — attack, defence, keeper and midfield, each the "
    "mean of that band's attributes over the selected players rescaled (x−28)/68, the same four numbers the engine reports — "
    "measured from the club's stored squad with this career's transfers applied as of the round; equal indices break alphabetically so the answer is reproducible"
)
FIT_FORMULA: Final = (
    "tactical_fit = 0.5 × the player's own band index (mean of that band's attributes rescaled (x−28)/68, the measurement the engine puts beside that band) "
    "+ 0.5 × 1 when the player's band is the band this club is weakest in, else 0 — so a very good player where you do not need one fits at 0.5, and one where you do reaches 1.0"
)
NEGOTIATION_FORMULA: Final = (
    "the floor a seller will answer is round_5(asking × 0.8); an offer at or above the current price is taken at the current price; "
    "an offer above the floor moves the price to round_5((price + offer) ÷ 2); an offer at or below the floor moves nothing; "
    "after 3 attempts the seller stops answering"
)
RIVAL_FORMULA: Final = (
    "a club in the career's own competition will not sell to a rival: only the release clause in the player's contract moves them "
    f"(clause = asking × {RELEASE_CLAUSE_SHARE}). A loan is a temporary deal the selling club agrees to, so the clause rule binds a permanent move only"
)
LOAN_FORMULA: Final = f"loan fee = round_5(current price × {LOAN_FEE_SHARE}); a loaned player is in the squad until loan_until_round and out of it afterwards, with no row written when the loan simply ends"
SELL_FORMULA: Final = (
    f"proceeds = round_5(asking × {SELL_PROCEEDS_SHARE}) — the market pays 90% of what it lists a player at, because a seller does not set the price of its own exit; "
    "the counterparty is the highest-rated club in the career's competition other than the career's own, ties broken by slug"
)
RELEASE_FORMULA: Final = "release pays no fee and takes the player out of the squad; the contract is not bought out and nothing arrives in the budget"
WAGE_FORMULA: Final = (
    "wage charge for a round = Σ weekly_wage of the deals this career holds at the start of that round "
    "(a buy until it is sold or released, a loan until loan_until_round), written as one row when the round is played; "
    "a career holding no deal of its own is charged nothing and writes no row"
)

RULES: Final[dict[str, str]] = {
    "valuation": VALUATION_FORMULA,
    "need": NEED_FORMULA,
    "tactical_fit": FIT_FORMULA,
    "negotiation": NEGOTIATION_FORMULA,
    "release_clause": RIVAL_FORMULA,
    "loan": LOAN_FORMULA,
    "sell": SELL_FORMULA,
    "release": RELEASE_FORMULA,
    "wages": WAGE_FORMULA,
    "budget": BUDGET_FORMULA,
    "squad": "the eleven is then selected from the club's stored squad with these moves applied, so a signing changes the indices the engine plays with (app/services/simulation/squad.py)",
}


class MarketRefusal(RuntimeError):
    """A deal this market will not do, with the numbers that decided it.

    Every refusal carries its own code and the figures behind it — a buyer told `insufficient_budget`
    is told the price and the balance, because the point of an arithmetic market is that a refusal can
    be checked.
    """

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), **self.detail}


def _credits(value: float) -> int:
    """Round a fee to the nearest 5 credits so a printed figure is the stored figure."""
    return int(round(value / CREDIT_ROUND) * CREDIT_ROUND)


def age_curve(age: int) -> float:
    for low, high, weight in AGE_CURVE:
        if low <= age <= high:
            return weight
    return 0.30


def valuation(player: RealPlayer) -> dict[str, Any]:
    """What this player is worth to a club in this world, from their stored row alone."""
    quality = max(0, int(player.overall) - OVERALL_FLOOR)
    headroom = max(0, int(player.potential) - int(player.overall))
    curve = age_curve(int(player.age))
    asking = _credits((quality * QUALITY_CREDIT + headroom * HEADROOM_CREDIT) * curve)
    return {
        "asking_fee": asking,
        "release_clause": _credits(asking * RELEASE_CLAUSE_SHARE),
        "weekly_wage": max(CREDIT_ROUND, _credits(asking / WAGE_DIVISOR)),
        "contract_years": min(CONTRACT_MAX_YEARS, max(1, CONTRACT_MAX_YEARS - max(0, int(player.age) - PEAK_AGE_END))),
        "quality_points": quality,
        "headroom_points": headroom,
        "age_curve": curve,
        "formula": VALUATION_FORMULA,
    }


def tactical_fit(player: RealPlayer, needed_band: str) -> dict[str, Any]:
    """How much this player answers the need, on the same scale the engine reports bands in."""
    band = band_of_position(player.position)
    index = band_index([player], band) if band else 0.0
    fills = bool(band) and band == needed_band
    return {"band": band, "band_index": round(index, 3), "fills_need": fills, "fit": round(0.5 * index + (0.5 if fills else 0.0), 3)}


def club_need(session: Session, career: Career, *, round_index: int) -> dict[str, Any]:
    """Which band this club is weakest in *as this career plays it*, and the four numbers that said so."""
    overlay = squad_as_of(session, career, round_index)
    try:
        profile = team_profile(session, career.club_id or "", system_slug=career.system_slug or None, squad=overlay)
    except LookupError as error:
        raise MarketRefusal("no_club", str(error), career_slug=career.slug) from None
    bands = {"attack": profile.attack, "defence": profile.defence, "keeper": profile.keeper, "midfield": profile.midfield}
    needed = min(sorted(bands), key=lambda band: bands[band])
    return {
        "needed_band": needed,
        "bands": {band: round(value, 3) for band, value in sorted(bands.items())},
        "positions_in_band": list(BANDS[needed]),
        "judged_on": list(BAND_ATTRIBUTES[needed]),
        "formation": profile.formation,
        "system_slug": profile.system_slug,
        "squad_applied": overlay.summary if overlay else "",
        "formula": NEED_FORMULA,
    }


def market_pool(session: Session, career: Career, *, round_index: int) -> tuple[list[RealPlayer], dict[str, Any]]:
    """Who could be bought: every stored player at another club, minus the ones this career already has."""
    rows = list(
        session.scalars(
            select(RealPlayer).where(RealPlayer.team_id.is_not(None), RealPlayer.team_id != (career.club_id or "")).order_by(RealPlayer.slug)
        ).all()
    )
    mine = {player_id for player_id, kind in squad_state(session, career, round_index).items() if kind in IN_KINDS}
    pool = [player for player in rows if player.id not in mine]
    unstaffed = [player.name for player in pool if not band_of_position(player.position)]
    return pool, {
        "at_other_clubs": len(rows),
        "already_yours": len(mine),
        "offered_from": len(pool),
        "positions_this_model_does_not_staff": len(unstaffed),
        "rule": "a career may buy a player the world stores at another club; a player this career has already signed is not on the market again",
    }


def market_selection(session: Session, career: Career, *, round_index: int, need: dict[str, Any]) -> tuple[list[RealPlayer], dict[str, Any]]:
    """The players on the market this round: the best-rated few in each band, weakest band first.

    No random draw anywhere — the set is a function of the world's rows and this career's squad, which
    is what lets a page say "these 12, and here is why they are these 12".
    """
    pool, account = market_pool(session, career, round_index=round_index)
    per_band = -(-MARKET_SIZE // len(BANDS))
    ordered = [str(need["needed_band"])] + [band for band in sorted(BANDS) if band != need["needed_band"]]
    chosen: list[RealPlayer] = []
    seen: set[str] = set()
    by_band: dict[str, int] = {}
    for band in ordered:
        ranked = sorted(
            [player for player in pool if band_of_position(player.position) == band],
            key=lambda player: (-player.overall, -player.potential, player.slug),
        )
        taken = 0
        for player in ranked[:per_band]:
            if player.id in seen or len(chosen) >= MARKET_SIZE:
                continue
            chosen.append(player)
            seen.add(player.id)
            taken += 1
        by_band[band] = taken
    account |= {
        "slots_per_band": per_band,
        "band_order": ordered,
        "taken_per_band": by_band,
        "size": len(chosen),
        "selection_rule": (
            f"within each band the {per_band} highest overall (ties: higher potential, then slug), with the band this club is weakest in filled first "
            "and the other bands taken in alphabetical order, up to 12 players — no draw, so the same squad offers the same market"
        ),
    }
    return chosen, account


def open_market(session: Session, career: Career) -> dict[str, Any]:
    """Refresh this career's market for the round it is about to play.

    A listing is an offer, so re-listing re-prices it: a negotiated discount does not survive into the
    next round, and the response says how many rows were repriced rather than quietly rewriting them.
    """
    round_index = int(career.rounds_played) + 1
    need = club_need(session, career, round_index=round_index)
    chosen, account = market_selection(session, career, round_index=round_index, need=need)
    existing = {row.player_id: row for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id))}
    created = repriced = withdrawn = kept = 0
    for player in chosen:
        price = valuation(player)
        fit = tactical_fit(player, str(need["needed_band"]))
        row = existing.get(player.id)
        if row is not None and row.status == "signed":
            kept += 1
            continue
        if row is None:
            row = TransferListing(id=new_public_id("tl"), career_id=career.id, player_id=player.id)
            session.add(row)
            created += 1
        else:
            repriced += 1
        row.player_slug = player.slug
        row.player_name = player.name
        row.position = player.position
        row.age = player.age
        row.overall = player.overall
        row.potential = player.potential
        row.from_team_id = player.team_id
        row.from_team_name = session.scalar(select(Team.name).where(Team.id == player.team_id)) or ""
        row.asking_fee = price["asking_fee"]
        row.current_price = price["asking_fee"]
        row.release_clause = price["release_clause"]
        row.contract_years = price["contract_years"]
        row.weekly_wage = price["weekly_wage"]
        row.tactical_fit = fit["fit"]
        row.needed_band = str(need["needed_band"])
        row.status = "open"
        row.listed_round = round_index
        row.negotiations = 0
        row.last_offer = 0
    offered = {player.id for player in chosen}
    for player_id, row in existing.items():
        if player_id not in offered and row.status == "open":
            row.status = "withdrawn"
            withdrawn += 1
    session.commit()
    return {
        "round_index": round_index,
        "created": created,
        "repriced": repriced,
        "withdrawn": withdrawn,
        "kept_signed": kept,
        "negotiation_note": "a re-listed price starts the next round where the valuation put it; a discount you negotiated does not carry across a round",
        **account,
    }


def _listing(session: Session, career: Career, ident: str) -> TransferListing:
    row = session.scalar(
        select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.id == ident)
    ) or session.scalar(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.player_slug == ident))
    if row is None:
        raise MarketRefusal("no_such_listing", f"{ident!r} is not a listing this career was given", career_slug=career.slug)
    return row


def _is_rival(session: Session, career: Career, listing: TransferListing) -> bool:
    """Whether the selling club shares this career's competition, which is what the clause rule turns on."""
    if not (career.competition_id and listing.from_team_id):
        return False
    return bool(session.scalar(select(Team.id).where(Team.id == listing.from_team_id, Team.competition_id == career.competition_id)))


def transferable(session: Session, career: Career) -> dict[str, Any]:
    """Whether this career may change its squad right now, with the rule that says so.

    The refusal a live challenge's `no_transfers` line produces is published here with `enforced: true`
    and the mechanism named, because the market is the thing that does the enforcing. The §21 catalogue
    carries its own copy of that flag and is not edited by this module.
    """
    if career.status != "active":
        return {"ok": False, "code": "career_retired", "message": "this career is retired; its squad is closed", "constraint": "career_status"}
    window = int(career.challenge_window or 0)
    if window and int(career.rounds_played) >= window:
        return {
            "ok": False,
            "code": "window_closed",
            "message": f"the scenario's window closed after {career.rounds_played} of {window} rounds, so its squad is final",
            "constraint": "window",
            "rounds_played": int(career.rounds_played),
            "window_rounds": window,
        }
    challenge = challenge_by_slug(career.challenge_slug) if career.challenge_slug else None
    if challenge is not None and any(constraint.key == "no_transfers" for constraint in challenge.constraints):
        return {
            "ok": False,
            "code": "transfers_forbidden",
            "message": f"{challenge.name} is played without transfers, so this market will not open a deal for it",
            "constraint": "no_transfers",
            "challenge_slug": challenge.slug,
            "enforced": True,
            "enforced_by": "app.services.simulation.market.transferable, checked by every move in this module",
        }
    return {"ok": True, "code": "", "message": "", "constraint": ""}


def _require_transferable(session: Session, career: Career) -> dict[str, Any]:
    verdict = transferable(session, career)
    if not verdict["ok"]:
        detail = {key: value for key, value in verdict.items() if key not in {"ok", "code", "message"}}
        raise MarketRefusal(str(verdict["code"]), str(verdict["message"]), **detail)
    return verdict


def _record_move(
    session: Session,
    career: Career,
    player: RealPlayer,
    *,
    kind: str,
    fee: int,
    round_index: int,
    balance: dict[str, Any],
    listing: TransferListing | None = None,
    counterparty: Team | None = None,
    loan_until: int = 0,
) -> CareerSquadMove:
    """Write one move row, and the balance it left behind, so the ledger adds up by construction.

    The contract terms come from the same valuation the market quoted, which is what makes a *Contract*
    in §22 a stored fact about a deal rather than a page furniture value.
    """
    price = valuation(player)
    incoming = kind in IN_KINDS
    move = CareerSquadMove(
        id=new_public_id("mov"),
        career_id=career.id,
        round_index=round_index,
        kind=kind,
        player_id=player.id,
        player_slug=player.slug,
        player_name=player.name,
        position=player.position,
        fee=fee,
        fee_units=career.budget_units,
        contract_years=int(price["contract_years"]),
        weekly_wage=int(price["weekly_wage"]),
        loan_until_round=loan_until,
        listing_id=listing.id if listing else None,
        counterparty_team_id=counterparty.id if counterparty else (listing.from_team_id if listing else None),
        counterparty_name=counterparty.name if counterparty else (listing.from_team_name if listing else ""),
        budget_after=int(balance["remaining"]) - fee if incoming else int(balance["remaining"]) + fee,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(move)
    return move


def held_deals(session: Session, career_id: str, round_index: int) -> list[CareerSquadMove]:
    """The deals this career stands behind in one round, one row per player, in the order they were made.

    The last move for a player is the one that binds: a signing sold on again is not held, and a loan
    whose rounds have run out is not either — `effective_kind` says so without editing the history.
    """
    latest: dict[str, CareerSquadMove] = {}
    for move in moves_as_of(session, career_id, round_index):
        latest[move.player_id] = move
    return [move for player_id, move in latest.items() if effective_kind(move, round_index) in IN_KINDS]


def wages_as_of(session: Session, career_id: str, round_index: int) -> list[CareerWageCharge]:
    """Every wage row this career had been charged by the end of `round_index`, oldest round first."""
    return list(
        session.scalars(
            select(CareerWageCharge)
            .where(CareerWageCharge.career_id == career_id, CareerWageCharge.round_index <= round_index)
            .order_by(CareerWageCharge.round_index, CareerWageCharge.created_at, CareerWageCharge.id)
        ).all()
    )


def wage_bill(session: Session, career: Career, *, round_index: int) -> dict[str, Any]:
    """What the deals this career holds would cost for one round, named player by player.

    The same figure is published twice over: as the standing rate beside the budget, and as the `fee` of
    the row written when a round is played. Both come out of this one function, so a page that printed
    one and charged the other would be caught by a test rather than by a reader.
    """
    held = held_deals(session, career.id, round_index)
    names = [f"{move.player_name} {move.weekly_wage:,}" for move in sorted(held, key=lambda move: (-move.weekly_wage, move.player_name))]
    return {
        "players": len(held),
        "fee": sum(int(move.weekly_wage) for move in held),
        "detail": " · ".join(names),
        "units": career.budget_units,
        "formula": WAGE_FORMULA,
    }


def budget_position(session: Session, career: Career) -> dict[str, Any]:
    """The budget as an arithmetic: what was stated, what left, what arrived, and what is standing."""
    round_index = int(career.rounds_played) + 1
    moves = moves_as_of(session, career.id, round_index)
    spent = sum(move.fee for move in moves if move.kind in IN_KINDS)
    received = sum(move.fee for move in moves if move.kind == "sell")
    charges = wages_as_of(session, career.id, round_index)
    wages_paid = sum(int(row.fee) for row in charges)
    standing = wage_bill(session, career, round_index=round_index)
    return {
        "budget": int(career.budget),
        "spent": spent,
        "received": received,
        "wages_paid": wages_paid,
        "remaining": int(career.budget) + received - spent - wages_paid,
        "units": career.budget_units,
        "moves": len(moves),
        "wage_rows": len(charges),
        "wage_rounds": sorted({int(row.round_index) for row in charges}),
        "wage_committed_per_week": standing["fee"],
        "wage_players": standing["players"],
        "wage_detail": standing["detail"],
        "wage_note": (
            "charged every round this career plays: the deals it holds cost their agreed weekly wage, and each "
            "round's charge is a row of its own below"
        ),
        "formula": BUDGET_FORMULA,
    }


def pay_wages(session: Session, career: Career, *, round_index: int) -> CareerWageCharge | None:
    """Charge one played round what its deals cost, and write the row that says so.

    Called from the only path that can play a round, after the fixture is stored, so a match a career
    never played is a match it never paid for. A career that holds no deal of its own writes nothing:
    an empty row beside an empty charge would put a figure on the ledger that no deal produced.
    """
    standing = wage_bill(session, career, round_index=round_index)
    if standing["fee"] <= 0:
        return None
    balance = budget_position(session, career)
    charge = CareerWageCharge(
        id=new_public_id("wage"),
        career_id=career.id,
        round_index=round_index,
        fee=int(standing["fee"]),
        fee_units=career.budget_units,
        players=int(standing["players"]),
        detail=str(standing["detail"]),
        budget_after=int(balance["remaining"]) - int(standing["fee"]),
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(charge)
    session.commit()
    session.refresh(charge)
    return charge


def buy(session: Session, career: Career, *, ident: str, use_clause: bool = False) -> tuple[CareerSquadMove, dict[str, Any]]:
    """Sign a listed player for good. The fee leaves the balance before the next round is played."""
    _require_transferable(session, career)
    row = _listing(session, career, ident)
    if row.status != "open":
        raise MarketRefusal("not_on_sale", f"{row.player_name} is no longer on this career's market (status: {row.status})", listing_id=row.id)
    rival = _is_rival(session, career, row)
    if rival and not use_clause:
        raise MarketRefusal(
            "rival_will_not_sell",
            f"{row.from_team_name} shares this career's competition and will not sell to a rival; only the release clause moves them",
            release_clause=row.release_clause,
            current_price=row.current_price,
            formula=RIVAL_FORMULA,
        )
    fee = int(row.release_clause if use_clause else row.current_price)
    balance = budget_position(session, career)
    if fee > int(balance["remaining"]):
        raise MarketRefusal(
            "insufficient_budget",
            f"{fee:,} {career.budget_units} is more than this career has left",
            fee=fee,
            remaining=int(balance["remaining"]),
            formula=BUDGET_FORMULA,
        )
    player = session.get(RealPlayer, row.player_id)
    if player is None:
        raise MarketRefusal("player_gone", f"the row for {row.player_name} is no longer stored, so there is nobody to sign", listing_id=row.id)
    move = _record_move(
        session, career, player, kind="buy", fee=fee, round_index=int(career.rounds_played) + 1, balance=balance, listing=row
    )
    row.status = "signed"
    # The listing keeps the price it was offered at. What actually left the balance is the move row's
    # `fee`, and paying a clause rather than the asking price would otherwise print a *higher* current
    # price beside a deal that is already shut — a market that looks like it rose when you bought.
    session.commit()
    session.refresh(move)
    return move, {"rival": rival, "clause_used": use_clause, "paid_from": "current_price" if not use_clause else "release_clause"}


def loan(session: Session, career: Career, *, ident: str, rounds: int = DEFAULT_LOAN_ROUNDS) -> tuple[CareerSquadMove, dict[str, Any]]:
    """Take a listed player for a stated number of rounds. The club across from you agrees, so no clause binds."""
    _require_transferable(session, career)
    row = _listing(session, career, ident)
    if row.status != "open":
        raise MarketRefusal("not_on_sale", f"{row.player_name} is no longer on this career's market (status: {row.status})", listing_id=row.id)
    rounds = max(1, min(int(rounds), 40))
    round_index = int(career.rounds_played) + 1
    fee = max(CREDIT_ROUND, _credits(int(row.current_price) * LOAN_FEE_SHARE))
    balance = budget_position(session, career)
    if fee > int(balance["remaining"]):
        raise MarketRefusal(
            "insufficient_budget",
            f"a loan costs {fee:,} {career.budget_units} and this career has {int(balance['remaining']):,}",
            fee=fee,
            remaining=int(balance["remaining"]),
            formula=LOAN_FORMULA,
        )
    player = session.get(RealPlayer, row.player_id)
    if player is None:
        raise MarketRefusal("player_gone", f"the row for {row.player_name} is no longer stored, so there is nobody to loan", listing_id=row.id)
    until = round_index + rounds - 1
    move = _record_move(
        session, career, player, kind="loan", fee=fee, round_index=round_index, balance=balance, listing=row, loan_until=until
    )
    row.status = "signed"
    session.commit()
    session.refresh(move)
    return move, {"rounds": rounds, "covers": f"rounds {round_index} to {until} inclusive", "fee_formula": LOAN_FORMULA}


def _outgoing(session: Session, career: Career, ident: str) -> tuple[RealPlayer, list[RealPlayer], dict[str, Any]]:
    """One of this career's own players, the squad that holds them, and the account of how it was read."""
    squad, account = current_squad(session, career)
    player = next((row for row in squad if row.id == ident or row.slug == ident), None)
    if player is None:
        raise MarketRefusal(
            "not_your_player",
            f"{ident!r} is not in this career's squad as it stands in round {account['as_of_round']}",
            career_slug=career.slug,
            squad_size=account["squad_now"],
            as_of_round=account["as_of_round"],
        )
    return player, squad, account


def sell(session: Session, career: Career, *, ident: str) -> tuple[CareerSquadMove, dict[str, Any]]:
    """Sell a squad member into the market. The proceeds arrive and the eleven changes next round."""
    _require_transferable(session, career)
    player, squad, _account = _outgoing(session, career, ident)
    fielding = can_field_side(squad, dropping_id=player.id)
    if not fielding["ok"]:
        raise MarketRefusal("would_not_field_a_side", f"selling {player.name} would leave this career unable to field a side", **fielding)
    price = valuation(player)
    fee = _credits(int(price["asking_fee"]) * SELL_PROCEEDS_SHARE)
    counterparty = session.scalars(
        select(Team).where(Team.competition_id == (career.competition_id or ""), Team.id != (career.club_id or "")).order_by(Team.overall.desc(), Team.slug)
    ).first()
    if counterparty is None:
        raise MarketRefusal("no_buyer", "this career's club has no competition to sell into", competition_id=career.competition_id)
    move = _record_move(
        session,
        career,
        player,
        kind="sell",
        fee=fee,
        round_index=int(career.rounds_played) + 1,
        balance=budget_position(session, career),
        counterparty=counterparty,
    )
    for row in session.scalars(
        select(TransferListing).where(
            TransferListing.career_id == career.id, TransferListing.player_id == player.id, TransferListing.status == "open"
        )
    ):
        row.status = "withdrawn"
    session.commit()
    session.refresh(move)
    return move, {"proceeds_formula": SELL_FORMULA, "valuation": price, "buyer": counterparty.name}


def release(session: Session, career: Career, *, ident: str) -> tuple[CareerSquadMove, dict[str, Any]]:
    """Let a squad member go for nothing. The balance does not move and the eleven does."""
    _require_transferable(session, career)
    player, squad, _account = _outgoing(session, career, ident)
    fielding = can_field_side(squad, dropping_id=player.id)
    if not fielding["ok"]:
        raise MarketRefusal("would_not_field_a_side", f"releasing {player.name} would leave this career unable to field a side", **fielding)
    move = _record_move(
        session,
        career,
        player,
        kind="release",
        fee=0,
        round_index=int(career.rounds_played) + 1,
        balance=budget_position(session, career),
    )
    for row in session.scalars(
        select(TransferListing).where(
            TransferListing.career_id == career.id, TransferListing.player_id == player.id, TransferListing.status == "open"
        )
    ):
        row.status = "withdrawn"
    session.commit()
    session.refresh(move)
    return move, {"fee_formula": RELEASE_FORMULA}


def negotiate(session: Session, career: Career, *, ident: str, offer: int) -> dict[str, Any]:
    """Make the seller an offer, by the rule the response prints beside it."""
    _require_transferable(session, career)
    row = _listing(session, career, ident)
    if row.status != "open":
        raise MarketRefusal("not_on_sale", f"{row.player_name} is no longer on this career's market (status: {row.status})", listing_id=row.id)
    attempts = int(row.negotiations)
    if attempts >= MAX_NEGOTIATION_ROUNDS:
        raise MarketRefusal(
            "negotiation_closed",
            f"{row.from_team_name} has answered {attempts} offers and will not take another; the price stands where it is",
            current_price=int(row.current_price),
            attempts=attempts,
            formula=NEGOTIATION_FORMULA,
        )
    floor = _credits(int(row.asking_fee) * NEGOTIATION_FLOOR_SHARE)
    current = int(row.current_price)
    offer = max(0, int(offer))
    if offer >= current:
        outcome, price = "accepted", current
    elif offer > floor:
        price = max(floor, _credits((current + offer) / 2))
        outcome = "countered"
    else:
        outcome, price = "rejected", current
    row.negotiations = attempts + 1
    row.last_offer = offer
    row.current_price = price
    session.commit()
    session.refresh(row)
    return {
        "outcome": outcome,
        "offer": offer,
        "price": price,
        "floor": floor,
        "asking": int(row.asking_fee),
        "attempts": int(row.negotiations),
        "attempts_left": max(0, MAX_NEGOTIATION_ROUNDS - int(row.negotiations)),
        "player": row.player_name,
        "seller": row.from_team_name,
        "rival": _is_rival(session, career, row),
        "formula": NEGOTIATION_FORMULA,
        "data_origin": "simulation",
        "is_demo_data": True,
        "disclaimer": MARKET_DISCLAIMER,
    }


def squad_rows(squad: list[RealPlayer]) -> list[dict[str, Any]]:
    """The squad as a page reads it: who is here, what the market would list them at, what a sale brings."""
    rows: list[dict[str, Any]] = []
    for player in squad:
        price = valuation(player)
        rows.append(
            {
                "player_id": player.id,
                "slug": player.slug,
                "name": player.name,
                "position": player.position,
                "band": band_of_position(player.position),
                "age": player.age,
                "overall": player.overall,
                "potential": player.potential,
                "asking_fee": price["asking_fee"],
                "sell_proceeds": _credits(int(price["asking_fee"]) * SELL_PROCEEDS_SHARE),
                "weekly_wage": price["weekly_wage"],
                "contract_years": price["contract_years"],
                "player_path": f"/player/{player.slug}",
            }
        )
    return rows


def listing_row(session: Session, career: Career, row: TransferListing, balance: dict[str, Any] | None = None) -> dict[str, Any]:
    standing = balance or budget_position(session, career)
    rival = _is_rival(session, career, row)
    price = int(row.release_clause if rival else row.current_price)
    return {
        "id": row.id,
        "player_id": row.player_id,
        "player_slug": row.player_slug,
        "player_name": row.player_name,
        "player_path": f"/player/{row.player_slug}",
        "position": row.position,
        "band": band_of_position(row.position),
        "age": row.age,
        "overall": row.overall,
        "potential": row.potential,
        "from_team_id": row.from_team_id,
        "from_team_name": row.from_team_name,
        "from_team_path": f"/team/{row.from_team_id}" if row.from_team_id else None,
        "asking_fee": int(row.asking_fee),
        "current_price": int(row.current_price),
        "release_clause": int(row.release_clause),
        "weekly_wage": int(row.weekly_wage),
        "contract_years": int(row.contract_years),
        "tactical_fit": float(row.tactical_fit),
        "needed_band": row.needed_band,
        "status": row.status,
        "listed_round": int(row.listed_round),
        "negotiations": int(row.negotiations),
        "attempts_left": max(0, MAX_NEGOTIATION_ROUNDS - int(row.negotiations)),
        "last_offer": int(row.last_offer),
        "rival": rival,
        "price_to_pay": price,
        "affordable": price <= int(standing["remaining"]),
        "clause_required": rival,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
    }


def move_row(row: CareerSquadMove) -> dict[str, Any]:
    return {
        "id": row.id,
        "round_index": int(row.round_index),
        "kind": row.kind,
        "side": "in" if row.kind in IN_KINDS else "out",
        # Which way the *money* went. A squad move and a wage charge share one ledger, and a reader adds
        # the fee column up, so the sign cannot be left to the reader's guess about `side`.
        "cash": "in" if row.kind == "sell" else "out",
        "player_id": row.player_id,
        "player_slug": row.player_slug,
        "player_name": row.player_name,
        "player_path": f"/player/{row.player_slug}" if row.player_slug else None,
        "position": row.position,
        "fee": int(row.fee),
        "fee_units": row.fee_units,
        "contract_years": int(row.contract_years),
        "weekly_wage": int(row.weekly_wage),
        "loan_until_round": int(row.loan_until_round),
        "counterparty_name": row.counterparty_name,
        "budget_after": int(row.budget_after),
        "effect": MOVE_EFFECT.get(row.kind, ""),
        "detail": "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
    }


def wage_row(charge: CareerWageCharge) -> dict[str, Any]:
    """A wage charge in the ledger's own shape, so one table on the page can print both kinds of row.

    There is no player to link, so the row names what was charged rather than whom. A page that invented
    a player for this row would be printing a person who was never signed.
    """
    return {
        "id": charge.id,
        "round_index": int(charge.round_index),
        "kind": "wage",
        "side": "out",
        "cash": "out",
        "player_id": "",
        "player_slug": "",
        "player_name": f"{charge.players} player{'s' if charge.players != 1 else ''} on wages",
        "player_path": None,
        "position": "",
        "fee": int(charge.fee),
        "fee_units": charge.fee_units,
        "contract_years": 0,
        "weekly_wage": int(charge.fee),
        "loan_until_round": 0,
        "counterparty_name": "",
        "budget_after": int(charge.budget_after),
        "effect": WAGE_EFFECT,
        "detail": charge.detail,
        "created_at": charge.created_at.isoformat() if charge.created_at else None,
        "data_origin": charge.data_origin,
        "is_demo_data": charge.is_demo_data,
    }


def ledger_of(moves: list[dict[str, Any]], charges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The two money tables as one ledger, in the order a reader has to add them up."""
    return sorted(
        [*moves, *charges],
        key=lambda entry: (int(entry["round_index"]), str(entry["created_at"] or ""), str(entry["id"])),
    )


def market_view(session: Session, career: Career) -> dict[str, Any]:
    """Everything the market page reads: the need, the offers, the squad, the ledger, and the rules."""
    round_index = int(career.rounds_played) + 1
    need = club_need(session, career, round_index=round_index)
    listings = list(
        session.scalars(
            select(TransferListing).where(TransferListing.career_id == career.id).order_by(TransferListing.listed_round.desc(), TransferListing.tactical_fit.desc(), TransferListing.player_name)
        ).all()
    )
    rows = list(session.scalars(select(CareerSquadMove).where(CareerSquadMove.career_id == career.id).order_by(CareerSquadMove.round_index, CareerSquadMove.created_at)).all())
    charges = list(session.scalars(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id).order_by(CareerWageCharge.round_index, CareerWageCharge.created_at)).all())
    move_rows = [move_row(row) for row in rows]
    wage_rows = [wage_row(row) for row in charges]
    squad, account = current_squad(session, career)
    balance = budget_position(session, career)
    open_rows = [row for row in listings if row.status == "open"]
    return {
        "career": {
            "slug": career.slug,
            "club_name": career.club_name,
            "club_id": career.club_id,
            "competition_name": career.competition_name,
            "season": career.season,
            "rounds_played": int(career.rounds_played),
            "market_round": round_index,
            "status": career.status,
            "challenge_slug": career.challenge_slug,
        },
        "transfers_allowed": transferable(session, career),
        "market": {
            "round_index": round_index,
            "opened": bool(listings),
            "size": MARKET_SIZE,
            "note": "the offers below are this career's own market; a career that has never opened one sees no rows and an empty `listings`",
        },
        "need": need,
        "budget": balance,
        "squad": {"account": account, "players": squad_rows(squad), "fielding": can_field_side(squad)},
        "listings": [listing_row(session, career, row, balance) for row in open_rows],
        "deals": [listing_row(session, career, row, balance) for row in listings if row.status == "signed"],
        "moves": ledger_of(move_rows, wage_rows),
        "totals": {
            "listed": len(open_rows),
            "signed": sum(1 for row in listings if row.status == "signed"),
            "withdrawn": sum(1 for row in listings if row.status == "withdrawn"),
            "moves": len(rows),
            "wage_rows": len(charges),
        },
        "rules": RULES,
        "constants": {
            "market_size": MARKET_SIZE,
            "negotiation_rounds": MAX_NEGOTIATION_ROUNDS,
            "negotiation_floor_share": NEGOTIATION_FLOOR_SHARE,
            "release_clause_share": RELEASE_CLAUSE_SHARE,
            "loan_fee_share": LOAN_FEE_SHARE,
            "sell_proceeds_share": SELL_PROCEEDS_SHARE,
            "default_loan_rounds": DEFAULT_LOAN_ROUNDS,
            "age_curve": [{"ages": f"{low}-{high}", "weight": weight} for low, high, weight in AGE_CURVE],
        },
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": MARKET_DISCLAIMER,
    }


__all__ = [
    "BUDGET_FORMULA",
    "FIT_FORMULA",
    "MARKET_DISCLAIMER",
    "MARKET_SIZE",
    "MAX_NEGOTIATION_ROUNDS",
    "MOVE_EFFECT",
    "MarketRefusal",
    "NEGOTIATION_FORMULA",
    "RULES",
    "SELL_FORMULA",
    "VALUATION_FORMULA",
    "WAGE_FORMULA",
    "age_curve",
    "budget_position",
    "buy",
    "club_need",
    "held_deals",
    "ledger_of",
    "listing_row",
    "loan",
    "market_pool",
    "market_selection",
    "market_view",
    "move_row",
    "negotiate",
    "open_market",
    "pay_wages",
    "release",
    "sell",
    "squad_rows",
    "tactical_fit",
    "transferable",
    "valuation",
    "wage_bill",
    "wage_row",
    "wages_as_of",
]
