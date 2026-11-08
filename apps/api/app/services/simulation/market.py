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
  squad-move kinds, one wage charge per round it played, and one board grant per season it closed. A fee
  that is not on the ledger cannot be spent, and a balance that does not add up is a defect.
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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import (
    AWARD_EFFECT,
    AWARD_KINDS,
    BUDGET_FORMULA,
    CUP_PRIZE_EFFECT,
    GATE_EFFECT,
    MOVE_EFFECT,
    OBJECTIVE_BONUS_EFFECT,
    UPKEEP_EFFECT,
    WAGE_EFFECT,
    Career,
    CareerAppearance,
    CareerBudgetAward,
    CareerCupTie,
    CareerFixture,
    CareerGateReceipt,
    CareerSeasonTicket,
    CareerSquadMove,
    CareerStadiumWork,
    CareerTrainingWork,
    CareerUpkeepCharge,
    CareerWageCharge,
    Competition,
    RealMatch,
    RealPlayer,
    Team,
    TransferListing,
)
from app.services.simulation.ageing import RETIRE_KIND, closed_seasons, effective_age
from app.services.simulation.ageing import RETIREMENT_AGE as RETIREMENT_THRESHOLD
from app.services.simulation.challenges import challenge_by_slug
from app.services.simulation.development import TRAINING_LEVEL_BONUS_PCT, TRAINING_MAX_LEVEL
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

# --- the season's signing windows, published as rounds ------------------------------------------------------
#: This project has no calendar beyond its round list, so a transfer window is a range of round numbers: the
#: opening window runs from round 1 to this round, and a second window sits around the season's midpoint.
EARLY_WINDOW_LAST_ROUND: Final = 4
MID_WINDOW_HALF_WIDTH: Final = 1
WINDOW_FORMULA: Final = (
    f"a season opens two signing windows: rounds 1–{EARLY_WINDOW_LAST_ROUND}, and the {2 * MID_WINDOW_HALF_WIDTH + 1} rounds around its "
    f"midpoint (mid − {MID_WINDOW_HALF_WIDTH} to mid + {MID_WINDOW_HALF_WIDTH}, mid = floor(season_rounds ÷ 2)); windows that overlap or "
    "touch are published merged; season_rounds = the challenge's own round window when it has one, else 2 × the competition's other "
    "clubs, the same horizon the season board projects against; rounds are grouped into seasons of that length, so the round a deal "
    "would be made in is round ((rounds_played) mod season_rounds) + 1 of season floor(rounds_played ÷ season_rounds) + 1; a career "
    "with no horizon (0 rounds) has no window to police and reads open; a window judges only the career's own next round — the "
    "generated fixture that round replays is read from the world and never rewritten, so a signing covers the round's eleven "
    "without touching the stored world score; the window counts the rounds played or actually stored in it "
    "from `career_fixtures` (whichever names more), and a move is refused when the round it would be booked "
    "into already has a stored fixture — the stored rows, not the calendar alone, are what decides"
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
LOAN_FORMULA: Final = (
    f"loan fee = round_5(current price × {LOAN_FEE_SHARE}); a loaned player is in the squad until loan_until_round and out of it afterwards, with no row written when the loan simply ends"
)
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
#: The board's wage ceiling is stated when the career is opened, like the budget: the most one round's
#: wage bill may commit. A balance is what is left; this is what may be committed, which sales income
#: cannot widen and a cash-rich career can still run into. 0 means the board set none.
WAGE_CEILING_FORMULA: Final = (
    "career.wage_ceiling is stated when the career is opened, in the budget's units per round (0 = the board "
    "sets no cap); a buy or loan is refused with wage_ceiling_exceeded when the weekly bill after the deal "
    "would exceed it (a bill equal to the ceiling is within it)"
)

#: The three sums the board pays when a season closes. Authored constants, the same kind as the season's
#: promotion and relegation lines: a reader reproduces the grant from the season's own rounds and points.
#: Sized against the market a career spends in — a full season's grant is well short of one good signing,
#: so the money arrives slowly enough to be a decision rather than a reset button.
SEASON_GRANT_PER_ROUND: Final = 8_000
SEASON_GRANT_PER_POINT: Final = 2_500
PROMOTION_GRANT: Final = 150_000
#: A cup round won pays its stage's prize (M13 Phase 8 item 32). The three figures are authored bands,
#: sized against the two incomes a career already has: a second-tier home gate is roughly 77,000 and a
#: season's grant roughly 140,000, so a run to the final (40 + 90 + 220 = 350,000) is a good season's
#: extra income rather than a reset button, and losing the first tie pays nothing.
CUP_PRIZE_BY_STAGE: Final[dict[int, int]] = {1: 40_000, 2: 90_000, 3: 220_000}
CUP_PRIZE_FORMULA: Final = (
    "cup_prize = 40,000 for a quarter-final won + 90,000 for a semi-final won + 220,000 for the final won; a "
    "tie is paid only when it is won, the row lands in `career_budget_awards` with kind `cup_prize` and the "
    "stage it was won in, and a challenge career enters no cup"
)
BUDGET_AWARD_FORMULA: Final = (
    "grant = rounds × 8,000 + points × 2,500, plus 150,000 when the season's verdict is `promoted`; one row per "
    "closed season of an open career, written in the same transaction as the boundary decision it pays for, and a "
    "challenge's window is judged by its own reward rather than by a grant"
)
#: What the board pays a season for the targets it met (M13 Phase 9 item 36). A second authored table beside
#: the grant, and the one income a manager decides before the season starts: the objectives they set at the
#: opening are the rows this pays for. Sized against the other board money — the four objectives together pay
#: 145,000, a little under one full season's grant (14 rounds × 8,000 + 25 points × 2,500 = 174,500) — so a
#: season that meets everything the board asked is a good season's extra income, not a reset button.
#: Points are what the verdict itself reads, so they are priced highest of the three sums; a win target is
#: largely a points target by another name, a goal-difference target is the margin around them, and an
#: unbeaten run is a streak rather than a sum — the one kind the board cannot project — so it is priced
#: above all three.
OBJECTIVE_BONUS_BY_KIND: Final[dict[str, int]] = {
    "wins": 30_000,
    "points": 40_000,
    "goal_difference": 25_000,
    "unbeaten": 50_000,
}
OBJECTIVE_BONUS_FORMULA: Final = (
    "objective_bonus = 30,000 for a wins objective met + 40,000 for a points objective + 25,000 for a "
    "goal_difference objective + 50,000 for an unbeaten objective; met means actual ≥ target, a target of zero "
    "or less pays nothing because nothing had to be met, one row per met objective lands in "
    "`career_budget_awards` with kind `objective_bonus` and the objective's kind as its stage, and a "
    "challenge's window is judged by the challenge's own reward rather than by a bonus"
)

#: The gate's authored price per seat, by the competition's tier. Tier 1 is the top flight; a cup's tier
#: is 0 and pays what a second-tier league pays. Sized from the same wage arithmetic the market charges:
#: a second-tier gate roughly covers a matchweek's wages, a top-flight gate roughly covers a top-flight
#: one, so the loop is "play to pay" rather than "play to get rich".
GATE_TICKET_PRICE_TIER_1: Final = 3
GATE_TICKET_PRICE_TIER_2: Final = 2
#: The share of the home ground a round on the career's own rotation sells, chosen deterministically from
#: the fixture seed. The world's own generated fixtures carry an attendance; only rotation rounds need this.
GATE_ROTATION_ATTENDANCE_FLOOR: Final = 62
GATE_ROTATION_ATTENDANCE_CEILING: Final = 99
#: A ground responds to the two things a career can change: the tier it plays in and the form it carries.
#: The stored capacity is the world's authored figure and is never rewritten; the gate reads an *effective*
#: capacity for this career, so a promoted club sells more seats without editing a shared row.
GATE_TIER_CAPACITY: Final[dict[int, float]] = {1: 1.25, 2: 1.10}
GATE_FORM_WINDOW: Final = 5
GATE_FORM_SHARE: Final = 0.10

#: The manager's ticket price (M13 Phase 10 item 44). 100 is the competition's own price; the setting
#: moves in steps of five between half and double it, so a decision is one visible number rather than a
#: slider with invisible precision. The demand curve is downward-sloping and slightly convex: a cheaper
#: seat fills more of the ground, a dearer one sells fewer, and the revenue maximum is around 120% —
#: modest enough to be believable for football, where a supporter's Saturday is not easily substituted.
TICKET_PRICE_MIN_PCT: Final = 50
TICKET_PRICE_MAX_PCT: Final = 200
TICKET_PRICE_STEP_PCT: Final = 5
TICKET_PRICE_NEUTRAL_PCT: Final = 100
TICKET_DEMAND_LINEAR: Final = 0.50
TICKET_DEMAND_QUADRATIC: Final = 0.50
TICKET_DEMAND_FLOOR: Final = 0.20
TICKET_PRICE_FORMULA: Final = (
    "attendance = min(effective_capacity, base × form_factor × demand_factor); "
    "d = (price_pct − 100) / 100; demand_factor = max(0.20, 1 − 0.50·d − 0.50·d²); "
    "gate_receipt = round(attendance × ticket_price × price_pct / 100); price_pct is the manager's "
    "setting between 50 and 200 in steps of 5, where 100 is the competition's own price. A cheaper "
    "seat fills more of the ground up to its capacity, a dearer one sells fewer, and every receipt "
    "stores the price and demand it was paid on so a later change cannot rewrite its crowd"
)
GATE_FORMULA: Final = (
    "gate_receipt = round(attendance × ticket_price × price_pct / 100); ticket_price = 3 for a tier-1 "
    "league and 2 for a tier-2 league or a cup; effective_capacity = stored capacity × tier factor "
    "(1.25 in tier 1, 1.10 in tier 2, 1.00 otherwise); attendance = min(effective_capacity, base × "
    "form_factor × demand_factor), where base is the world fixture's stored figure or, for a round "
    "played on the career's own rotation, effective_capacity × (62 + seed mod 38)%, form_factor = "
    "0.90 + 0.20 × form over the last 5 results (W = 1, D = 0.5, L = 0; 0.5 when none have been "
    "played), and demand_factor is stated by `ticket_price`; only a home round earns a gate, and a home "
    "club with no capacity sells nothing"
)


def gate_capacity(club: Team | None, tier: int) -> tuple[int, float]:
    """The seats this career's ground can sell at its current tier, and the factor it applied."""
    factor = GATE_TIER_CAPACITY.get(int(tier), 1.0)
    stored = int(club.capacity or 0) if club is not None else 0
    return int(round(stored * factor)), factor


#: What one bought seat costs (M13 Phase 9 item 37). A tier-2 seat sells for 2 credits a round and a
#: season is about nineteen home rounds plus a cup tie or two, so 120 credits is roughly three seasons of
#: that seat's gate: an improvement the ground itself pays for, not a shortcut to a fortune. Tier 1 earns 3
#: a round, so it pays back in two.
STADIUM_SEAT_COST: Final = 120
STADIUM_MIN_SEATS: Final = 500
STADIUM_MAX_SEATS: Final = 20_000
STADIUM_FORMULA: Final = (
    "stadium_works = a purchase of seats at 120 credits each, between 500 and 20,000 seats at a time, "
    "paid from the balance the market reads and written as a row of its own (kind `stadium`); the built "
    "ground = the club's stored capacity + every bought seat, and the gate reads the club's tier-factor "
    "capacity plus every bought seat, so each seat bought is one more seat sold; a challenge career owns no "
    "ground of its own, because its budget is an authored constraint"
)
STADIUM_EFFECT: Final = (
    "the money leaves the balance as a row of its own, and every later home gate adds the bought seats to the ground"
)

#: What running the ground costs (M13 Phase 10 item 45). A home round pays 25% of a credit for every
#: seat it opens, whether the crowd fills it or not: a 40,000-seat ground costs 10,000 a match, while a
#: full house at a tier-2 price earns 80,000. The rate is deliberately below the cheapest ticket, so a
#: full ground always pays for itself and an empty one is a real loss rather than a rounding error.
STADIUM_UPKEEP_PER_SEAT_PCT: Final = 25
STADIUM_UPKEEP_FORMULA: Final = (
    "upkeep = round(capacity × 25 / 100) credits for every home round, where capacity is the club's "
    "stored seats plus every bought one; a home league round and a home cup tie each pay it once, an away "
    "round and a neutral-venue final pay none, and a challenge career pays none because its scenario pays "
    "no gate either"
)

#: Season tickets (M13 Phase 10 item 46). The block is sold before the season's first round at 85% of
#: the neutral matchday price for every home league round, so the money arrives now and those seats are
#: filled later without being charged again. At most half the ground may be sold this way, in blocks of
#: 100, so a manager cannot extinguish walk-up demand and so the gate still has something to price.
SEASON_TICKET_DISCOUNT_PCT: Final = 85
SEASON_TICKET_MIN_SEATS: Final = 100
SEASON_TICKET_MAX_SHARE_PCT: Final = 50
SEASON_TICKET_FORMULA: Final = (
    "home_rounds = season rounds ÷ 2; full_price = the competition's ticket price × home_rounds; "
    "unit_price = round(full_price × 85 / 100); amount = seats × unit_price, paid before the season's "
    "first round and written as one row per season; at most 50% of the physical ground may be sold, in "
    "blocks of 100; those seats are filled every home league round and are not charged again at the "
    "gate, and a cup tie does not use them"
)
SEASON_TICKET_EFFECT: Final = (
    "the season-ticket money arrives before the first round: those seats are filled all season and are not charged at the gate"
)

#: The training ground (M13 Phase 11 item 47). Each level costs more than the last and makes a world
#: training session count 10% more toward development, up to +50% at level 5.
TRAINING_UPGRADE_BASE_COST: Final = 150_000
TRAINING_FORMULA: Final = (
    "training_ground: level L (0–5) costs 150,000 × (L + 1) credits to leave; each level adds 10% to the "
    "training half of the development curve — effective_minutes = match_minutes + 0.5 × load_units × "
    "(100 + 10L)/100 — so a full ground turns a session into 1.5× the match minutes it did"
)
TRAINING_EFFECT: Final = (
    "the money leaves the balance and every later development row reads the career's training sessions "
    "at the new bonus"
)


def stadium_works_of(session: Session, career_id: str) -> list[CareerStadiumWork]:
    """Every seat this career has bought, oldest first - the ledger and the ground's history in one list."""
    return list(
        session.scalars(
            select(CareerStadiumWork)
            .where(CareerStadiumWork.career_id == career_id)
            .order_by(CareerStadiumWork.round_index, CareerStadiumWork.created_at)
        ).all()
    )


def stadium_seats(session: Session, career: Career) -> int:
    """How many seats this career has added to its ground. Absent is zero, not unknown."""
    return int(
        session.scalar(
            select(func.coalesce(func.sum(CareerStadiumWork.seats), 0)).where(
                CareerStadiumWork.career_id == career.id
            )
        )
        or 0
    )


def ground_capacity(session: Session, career: Career, club: Team | None, tier: int) -> dict[str, Any]:
    """The ground this career plays in: the club's stored seats plus every bought one, and the cap it sets.

    A career that has bought nothing reads exactly the tier-factor capacity item 33 shipped. A career that
    has bought seats adds them to that capacity one for one - the tier factor still measures the club's own
    ground, while a built stand is concrete and does not grow because the club was promoted.
    """
    stored = int(club.capacity or 0) if club is not None else 0
    bought = stadium_seats(session, career)
    tier_capacity, factor = gate_capacity(club, tier)
    built = stored + bought
    effective = tier_capacity + bought
    return {
        "stored": stored,
        "bought": bought,
        "capacity": built,
        "factor": factor,
        "effective": effective,
        "source": (
            f"tier {tier} capacity {tier_capacity:,} ({stored:,} stored ×{factor:.2f}) + {bought:,} bought "
            f"= {effective:,} seats sold"
        ),
    }


def gate_capacity_for(session: Session, career: Career, club: Team | None, tier: int) -> tuple[int, float, int, str]:
    """(effective capacity, factor, bought seats, where the figure came from) - what the gate reads."""
    ground = ground_capacity(session, career, club, tier)
    return int(ground["effective"]), float(ground["factor"]), int(ground["bought"]), str(ground["source"])


def stadium_row(work: CareerStadiumWork) -> dict[str, Any]:
    """One purchase as a page reads it: what was added, what it cost, and the ground either side of it."""
    return {
        "id": work.id,
        "round_index": int(work.round_index),
        "seats": int(work.seats),
        "unit_cost": int(work.unit_cost),
        "amount": int(work.amount),
        "amount_units": work.amount_units,
        "capacity_before": int(work.capacity_before),
        "capacity_after": int(work.capacity_after),
        "budget_after": int(work.budget_after),
        "basis": work.basis,
        "created_at": work.created_at.isoformat() if work.created_at else None,
        "data_origin": work.data_origin,
        "is_demo_data": work.is_demo_data,
    }


def stadium_ledger_row(work: CareerStadiumWork) -> dict[str, Any]:
    """A purchase in the ledger's own shape: money out, no player, and the seats it bought."""
    return {
        "id": work.id,
        "round_index": int(work.round_index),
        "kind": "stadium",
        "side": "out",
        "cash": "out",
        "player_id": "",
        "player_slug": "",
        "player_name": f"stadium, {int(work.seats):,} seats",
        "player_path": None,
        "position": "",
        "fee": int(work.amount),
        "fee_units": work.amount_units,
        "contract_years": 0,
        "weekly_wage": 0,
        "loan_until_round": 0,
        "expiry_round": 0,
        "counterparty_name": "",
        "budget_after": int(work.budget_after),
        "effect": STADIUM_EFFECT,
        "detail": work.basis,
        "created_at": work.created_at.isoformat() if work.created_at else None,
        "data_origin": work.data_origin,
        "is_demo_data": work.is_demo_data,
    }


def stadium_view(session: Session, career: Career) -> dict[str, Any]:
    """The ground this career owns, what another seat costs, and what it has already spent."""
    club = session.get(Team, career.club_id) if career.club_id else None
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    ground = ground_capacity(session, career, club, tier)
    works = stadium_works_of(session, career.id)
    upkeep_works = upkeep_as_of(session, career.id, int(career.rounds_played) + 1)
    reason: str | None = None
    if career.challenge_slug:
        reason = (
            "a challenge career's budget is an authored constraint printed when the run starts, so it owns no "
            "ground of its own"
        )
    elif club is None:
        reason = "this career has no club, so it has no ground to build on"
    return {
        "available": reason is None,
        "reason": reason,
        "club_name": career.club_name,
        "ground": club.stadium if club is not None else "",
        "stored_capacity": int(ground["stored"]),
        "bought_seats": int(ground["bought"]),
        "capacity": int(ground["capacity"]),
        "tier_factor": float(ground["factor"]),
        "gate_capacity": int(ground["effective"]),
        "capacity_source": str(ground["source"]),
        "seat_cost": STADIUM_SEAT_COST,
        "min_seats": STADIUM_MIN_SEATS,
        "max_seats": STADIUM_MAX_SEATS,
        "upkeep_per_seat_pct": STADIUM_UPKEEP_PER_SEAT_PCT,
        "upkeep_per_home_round": int(round(int(ground["capacity"]) * STADIUM_UPKEEP_PER_SEAT_PCT / 100)),
        "spent": sum(int(row.amount) for row in works),
        "rows": len(works),
        "upkeep_spent": sum(int(row.amount) for row in upkeep_works),
        "upkeep_rows": len(upkeep_works),
        "works": [stadium_row(row) for row in works],
        "formula": STADIUM_FORMULA,
        "note": (
            "the capacity is the club's stored seats plus every bought one; once a career has bought any, "
            "the gate reads the tier-factor capacity plus those bought seats, so a stand is concrete and "
            "every seat bought is one more seat sold"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def demand_pct_for(price_pct: int) -> int:
    """The crowd a price setting draws, as a percentage of the neutral crowd (M13 Phase 10 item 44).

    One downward-sloping curve shared by the preview and the gate, so a page cannot promise a crowd the
    receipt will not pay for. The quadratic term makes the curve steepen as the price moves away from
    neutral: a small rise costs few seats, a doubling fills only a fifth of the ground.
    """
    d = (int(price_pct) - TICKET_PRICE_NEUTRAL_PCT) / 100.0
    factor = 1.0 - TICKET_DEMAND_LINEAR * d - TICKET_DEMAND_QUADRATIC * d * d
    return int(round(max(TICKET_DEMAND_FLOOR, factor) * 100))


def ticket_price_view(session: Session, career: Career) -> dict[str, Any]:
    """The manager's price, the demand it draws and the revenue it would index against neutral."""
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    base_price = GATE_TICKET_PRICE_TIER_1 if tier == 1 else GATE_TICKET_PRICE_TIER_2
    price_pct = int(career.ticket_price_pct or TICKET_PRICE_NEUTRAL_PCT)
    demand_pct = demand_pct_for(price_pct)
    settings = range(TICKET_PRICE_MIN_PCT, TICKET_PRICE_MAX_PCT + 1, TICKET_PRICE_STEP_PCT)
    revenue_index = {value: int(round(value * demand_pct_for(value) / 100)) for value in settings}
    best_pct = max(settings, key=lambda value: revenue_index[value])
    reason: str | None = None
    if career.status != "active":
        reason = "this career is retired; its gate keeps the price it last set and admits no new one"
    elif career.challenge_slug:
        reason = (
            "a challenge career's budget is an authored constraint printed when the run starts, and the "
            "scenario pays no gate, so it does not price one"
        )
    elif not career.club_id:
        reason = "this career has no club, so it has no gate to price"
    return {
        "available": reason is None,
        "reason": reason,
        "price_pct": price_pct,
        "min_pct": TICKET_PRICE_MIN_PCT,
        "max_pct": TICKET_PRICE_MAX_PCT,
        "step_pct": TICKET_PRICE_STEP_PCT,
        "neutral_pct": TICKET_PRICE_NEUTRAL_PCT,
        "base_price": base_price,
        "price_units": career.budget_units,
        "demand_pct": demand_pct,
        "revenue_index": revenue_index[price_pct],
        "best_price_pct": best_pct,
        "best_revenue_index": revenue_index[best_pct],
        "formula": TICKET_PRICE_FORMULA,
        "note": (
            "demand_pct is the share of the crowd a neutral price would draw, and revenue_index is "
            "price_pct × demand_pct / 100 with 100 meaning 'the same gate money as a neutral price'; "
            "the revenue-maximising setting is stated beside the manager's own, not hidden"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def set_ticket_price(session: Session, career: Career, *, price_pct: int) -> dict[str, Any]:
    """Set this career's gate price and answer with the view the page prints.

    A retired career prices nothing, a challenge owns no gate to price, and the setting must be one of
    the published steps — a refusal names the bounds and the step that decided it. Changing the price
    does not rewrite a receipt: every receipt stores the price it was actually paid on.
    """
    if career.status != "active":
        raise MarketRefusal("career_retired", "this career is retired; take charge again before pricing the gate")
    if career.challenge_slug:
        raise MarketRefusal(
            "challenge_budget",
            "a challenge career's budget is an authored constraint and its scenario pays no gate, so it does not price one",
        )
    if not career.club_id:
        raise MarketRefusal("no_club", "this career has no club, so it has no gate to price")
    value = int(price_pct)
    if value < TICKET_PRICE_MIN_PCT or value > TICKET_PRICE_MAX_PCT or value % TICKET_PRICE_STEP_PCT:
        raise MarketRefusal(
            "bad_ticket_price",
            (
                f"a ticket price is {TICKET_PRICE_MIN_PCT}–{TICKET_PRICE_MAX_PCT}% of the competition's "
                f"price in steps of {TICKET_PRICE_STEP_PCT}; {value}% is not one of them"
            ),
            price_pct=value,
            min_pct=TICKET_PRICE_MIN_PCT,
            max_pct=TICKET_PRICE_MAX_PCT,
            step_pct=TICKET_PRICE_STEP_PCT,
        )
    career.ticket_price_pct = value
    session.commit()
    session.refresh(career)
    return ticket_price_view(session, career)


def season_tickets_of(session: Session, career_id: str) -> list[CareerSeasonTicket]:
    """Every season-ticket sale this career has made, oldest season first."""
    return list(
        session.scalars(
            select(CareerSeasonTicket)
            .where(CareerSeasonTicket.career_id == career_id)
            .order_by(CareerSeasonTicket.season_index)
        ).all()
    )


def season_ticket_row(row: CareerSeasonTicket) -> dict[str, Any]:
    """One season's sale as a page reads it: the seats, the price and the money it brought forward."""
    return {
        "id": row.id,
        "season_index": int(row.season_index),
        "season": row.season,
        "round_index": int(row.round_index),
        "seats": int(row.seats),
        "home_rounds": int(row.home_rounds),
        "unit_price": int(row.unit_price),
        "amount": int(row.amount),
        "amount_units": row.amount_units,
        "capacity": int(row.capacity),
        "basis": row.basis,
        "budget_after": int(row.budget_after),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
    }


def season_ticket_ledger_row(row: CareerSeasonTicket) -> dict[str, Any]:
    """A season-ticket sale in the ledger's own shape: money in, no player, and the seats it sold."""
    return {
        "id": row.id,
        "round_index": int(row.round_index),
        "kind": "season_tickets",
        "side": "in",
        "cash": "in",
        "player_id": "",
        "player_slug": "",
        "player_name": f"season tickets, {int(row.seats):,} seats",
        "player_path": None,
        "position": "",
        "fee": int(row.amount),
        "fee_units": row.amount_units,
        "contract_years": 0,
        "weekly_wage": 0,
        "loan_until_round": 0,
        "expiry_round": 0,
        "counterparty_name": "",
        "budget_after": int(row.budget_after),
        "effect": SEASON_TICKET_EFFECT,
        "detail": row.basis,
        "season_index": int(row.season_index),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "data_origin": row.data_origin,
        "is_demo_data": row.is_demo_data,
    }


def season_ticket_seats_for(session: Session, career: Career, season_index: int) -> int:
    """The seats this career sold for one season, or zero when it sold none."""
    return int(
        session.scalar(
            select(func.coalesce(func.sum(CareerSeasonTicket.seats), 0)).where(
                CareerSeasonTicket.career_id == career.id,
                CareerSeasonTicket.season_index == int(season_index),
            )
        )
        or 0
    )


def season_ticket_view(
    session: Session,
    career: Career,
    *,
    bounds: dict[str, Any] | None = None,
    capacity: int | None = None,
) -> dict[str, Any]:
    """This season's season-ticket offer, the allocation already sold and the money it brought forward.

    `career_view` already holds this season's bounds and the ground's capacity (from the stadium block),
    so it hands both in: recomputing either here would read the competition's clubs a second time on
    every career page read.
    """
    from app.services.simulation.career import season_bounds

    bounds = bounds if bounds is not None else season_bounds(session, career)
    season_index = int(bounds["index"])
    first_round = int(bounds["first_round"])
    home_rounds = max(0, int(bounds["rounds"]) // 2)
    club = session.get(Team, career.club_id) if career.club_id else None
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    if capacity is None:
        capacity = int(ground_capacity(session, career, club, tier)["capacity"])
    capacity = int(capacity)
    base_price = GATE_TICKET_PRICE_TIER_1 if tier == 1 else GATE_TICKET_PRICE_TIER_2
    full_price = base_price * home_rounds
    unit_price = int(round(full_price * SEASON_TICKET_DISCOUNT_PCT / 100))
    raw_max = capacity * SEASON_TICKET_MAX_SHARE_PCT // 100
    max_seats = (raw_max // SEASON_TICKET_MIN_SEATS) * SEASON_TICKET_MIN_SEATS
    rows = season_tickets_of(session, career.id)
    current = next((row for row in rows if int(row.season_index) == season_index), None)
    reason: str | None = None
    if career.status != "active":
        reason = "this career is retired; its season tickets are closed"
    elif career.challenge_slug:
        reason = "a challenge career's budget is an authored constraint and its scenario has no season to sell"
    elif club is None:
        reason = "this career has no club, so it has no ground to sell"
    elif home_rounds <= 0:
        reason = "this career has no league horizon, so there are no home rounds to cover"
    elif max_seats < SEASON_TICKET_MIN_SEATS:
        reason = (
            f"the ground is too small: half of {capacity:,} seats is under the "
            f"{SEASON_TICKET_MIN_SEATS}-seat minimum"
        )
    elif current is not None:
        reason = f"season {season_index}'s allocation is already sold"
    elif int(career.rounds_played) != first_round - 1:
        reason = "season tickets are sold before the season's first round; this season has already started"
    return {
        "available": reason is None,
        "reason": reason,
        "season_index": season_index,
        "season": str(bounds["season"]),
        "first_round": first_round,
        "home_rounds": home_rounds,
        "capacity": capacity,
        "base_price": base_price,
        "full_price": full_price,
        "unit_price": unit_price,
        "discount_pct": SEASON_TICKET_DISCOUNT_PCT,
        "min_seats": SEASON_TICKET_MIN_SEATS,
        "max_share_pct": SEASON_TICKET_MAX_SHARE_PCT,
        "max_seats": max_seats,
        "price_units": career.budget_units,
        "sold": season_ticket_row(current) if current is not None else None,
        "rows": [season_ticket_row(row) for row in rows],
        "income": sum(int(row.amount) for row in rows),
        "formula": SEASON_TICKET_FORMULA,
        "note": (
            "a season ticket is money now for seats later: those seats are filled every home league round "
            "and are not charged again at the gate; at most half the ground may be sold this way, so the "
            "gate still has walk-up demand to price"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def buy_season_tickets(session: Session, career: Career, *, seats: int) -> tuple[CareerSeasonTicket, dict[str, Any]]:
    """Sell one season's allocation before its first round and write the money as a row of its own.

    The price is fixed by the season's home rounds and the discount, not by the manager's current matchday
    setting: the ticket was bought for the season, so a later change to one match's price cannot reprice
    it. One row per season is a schema property, so a second sale is refused here rather than double-paid.
    """
    from app.services.simulation.career import season_bounds

    if career.status != "active":
        raise MarketRefusal("career_retired", "this career is retired; take charge again before selling tickets")
    if career.challenge_slug:
        raise MarketRefusal(
            "challenge_budget",
            "a challenge career's budget is an authored constraint and its scenario has no season to sell",
        )
    if not career.club_id:
        raise MarketRefusal("no_club", "this career has no club, so it has no ground to sell")
    view = season_ticket_view(session, career)
    if view["sold"] is not None:
        raise MarketRefusal(
            "season_tickets_already_sold",
            f"season {view['season_index']}'s allocation is already sold",
            season_index=view["season_index"],
        )
    if int(career.rounds_played) != int(view["first_round"]) - 1:
        raise MarketRefusal(
            "season_ticket_window_closed",
            str(view["reason"]),
            season_index=view["season_index"],
            first_round=view["first_round"],
            played=int(career.rounds_played),
        )
    if not view["available"]:
        raise MarketRefusal(
            "season_ticket_unavailable",
            str(view["reason"]),
            season_index=view["season_index"],
            max_seats=int(view["max_seats"]),
        )
    value = int(seats)
    if (
        value < SEASON_TICKET_MIN_SEATS
        or value > int(view["max_seats"])
        or value % SEASON_TICKET_MIN_SEATS
    ):
        raise MarketRefusal(
            "bad_season_ticket_seats",
            (
                f"a season-ticket block is {SEASON_TICKET_MIN_SEATS}–{int(view['max_seats'])} seats in "
                f"blocks of {SEASON_TICKET_MIN_SEATS}; {value} is not one of them"
            ),
            seats=value,
            min_seats=SEASON_TICKET_MIN_SEATS,
            max_seats=int(view["max_seats"]),
            step_seats=SEASON_TICKET_MIN_SEATS,
        )
    bounds = season_bounds(session, career)
    amount = value * int(view["unit_price"])
    balance = budget_position(session, career)
    row = CareerSeasonTicket(
        id=new_public_id("seasonticket"),
        career_id=career.id,
        season_index=int(bounds["index"]),
        season=str(bounds["season"]),
        round_index=int(bounds["first_round"]),
        seats=value,
        home_rounds=int(view["home_rounds"]),
        unit_price=int(view["unit_price"]),
        amount=amount,
        amount_units=career.budget_units,
        capacity=int(view["capacity"]),
        basis=(
            f"{value:,} season tickets × {int(view['unit_price'])} {career.budget_units}/seat for "
            f"{int(view['home_rounds'])} home rounds at {SEASON_TICKET_DISCOUNT_PCT}% of "
            f"{int(view['full_price'])}; sold before round {int(bounds['first_round'])}"
        ),
        budget_after=int(balance["remaining"]) + amount,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, season_ticket_view(session, career)


def training_works_of(session: Session, career_id: str) -> list[CareerTrainingWork]:
    """Every level this career has bought for its training ground, oldest first."""
    return list(
        session.scalars(
            select(CareerTrainingWork)
            .where(CareerTrainingWork.career_id == career_id)
            .order_by(CareerTrainingWork.round_index, CareerTrainingWork.created_at)
        ).all()
    )


def training_bonus_pct(level: int) -> int:
    """What a facility level adds to the training half of the development curve."""
    return TRAINING_LEVEL_BONUS_PCT * max(0, min(TRAINING_MAX_LEVEL, int(level)))


def training_row(work: CareerTrainingWork) -> dict[str, Any]:
    """One upgrade as a page reads it: the level either side, the bonus it bought and what it cost."""
    return {
        "id": work.id,
        "round_index": int(work.round_index),
        "level_before": int(work.level_before),
        "level_after": int(work.level_after),
        "bonus_pct_before": int(work.bonus_pct_before),
        "bonus_pct_after": int(work.bonus_pct_after),
        "amount": int(work.amount),
        "amount_units": work.amount_units,
        "basis": work.basis,
        "budget_after": int(work.budget_after),
        "created_at": work.created_at.isoformat() if work.created_at else None,
        "data_origin": work.data_origin,
        "is_demo_data": work.is_demo_data,
    }


def training_ledger_row(work: CareerTrainingWork) -> dict[str, Any]:
    """An upgrade in the ledger's own shape: money out, no player, and the level it bought."""
    return {
        "id": work.id,
        "round_index": int(work.round_index),
        "kind": "training",
        "side": "out",
        "cash": "out",
        "player_id": "",
        "player_slug": "",
        "player_name": f"training ground level {int(work.level_after)}",
        "player_path": None,
        "position": "",
        "fee": int(work.amount),
        "fee_units": work.amount_units,
        "contract_years": 0,
        "weekly_wage": 0,
        "loan_until_round": 0,
        "expiry_round": 0,
        "counterparty_name": "",
        "budget_after": int(work.budget_after),
        "effect": TRAINING_EFFECT,
        "detail": work.basis,
        "level_before": int(work.level_before),
        "level_after": int(work.level_after),
        "created_at": work.created_at.isoformat() if work.created_at else None,
        "data_origin": work.data_origin,
        "is_demo_data": work.is_demo_data,
    }


def training_view(session: Session, career: Career) -> dict[str, Any]:
    """The training ground: its level, the bonus that level means and what the next one costs."""
    level = int(career.training_level or 0)
    rows = training_works_of(session, career.id)
    if career.status != "active":
        reason: str | None = "this career is retired; its training ground is closed"
    elif career.challenge_slug:
        reason = "a challenge career's budget is an authored constraint and its scenario owns no ground"
    elif not career.club_id:
        reason = "this career has no club, so it has no training ground to build"
    elif level >= TRAINING_MAX_LEVEL:
        reason = f"the training ground is at its highest level ({TRAINING_MAX_LEVEL})"
    else:
        reason = None
    at_max = level >= TRAINING_MAX_LEVEL
    return {
        "available": reason is None,
        "reason": reason,
        "level": level,
        "max_level": TRAINING_MAX_LEVEL,
        "bonus_pct": training_bonus_pct(level),
        "next_level": None if at_max else level + 1,
        "next_bonus_pct": None if at_max else training_bonus_pct(level + 1),
        "next_cost": None if at_max else TRAINING_UPGRADE_BASE_COST * (level + 1),
        "spent": sum(int(row.amount) for row in rows),
        "rows": [training_row(row) for row in rows],
        "units": career.budget_units,
        "formula": TRAINING_FORMULA,
        "note": (
            "a training ground is a long investment: the money buys a permanent multiplier on every "
            "training session the career's players do, and the multiplier is applied when a round's "
            "development is written, so a level bought before round N applies from N"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def buy_training_level(
    session: Session, career: Career, *, levels: int = 1
) -> tuple[list[CareerTrainingWork], dict[str, Any]]:
    """Buy one or more levels for the training ground, one ledger row per level."""
    if career.status != "active":
        raise MarketRefusal("career_retired", "this career is retired; take charge again before building")
    if career.challenge_slug:
        raise MarketRefusal(
            "challenge_budget",
            "a challenge career's budget is an authored constraint, so it owns no training ground",
        )
    if not career.club_id:
        raise MarketRefusal("no_club", "this career has no club, so it has no training ground to build")
    current = int(career.training_level or 0)
    if current >= TRAINING_MAX_LEVEL:
        raise MarketRefusal(
            "training_maxed",
            f"the training ground is already at level {TRAINING_MAX_LEVEL}",
            level=current,
            max_level=TRAINING_MAX_LEVEL,
        )
    value = int(levels)
    if value < 1 or value > TRAINING_MAX_LEVEL - current:
        raise MarketRefusal(
            "bad_training_levels",
            f"buy between 1 and {TRAINING_MAX_LEVEL - current} level(s); {value} is not one of them",
            levels=value,
            min_levels=1,
            max_levels=TRAINING_MAX_LEVEL - current,
            level=current,
        )
    costs = [TRAINING_UPGRADE_BASE_COST * (current + offset + 1) for offset in range(value)]
    total = sum(costs)
    position = budget_position(session, career)
    if total > int(position["remaining"]):
        raise MarketRefusal(
            "insufficient_budget",
            f"{value} training-ground level(s) cost {total:,}, more than the "
            f"{int(position['remaining']):,} the balance can spend",
            price=total,
            balance=int(position["remaining"]),
            levels=value,
        )
    rows: list[CareerTrainingWork] = []
    running = int(position["remaining"])
    for offset, cost in enumerate(costs):
        before = current + offset
        after = before + 1
        running -= cost
        rows.append(
            CareerTrainingWork(
                id=new_public_id("training"),
                career_id=career.id,
                round_index=int(career.rounds_played) + 1,
                level_before=before,
                level_after=after,
                bonus_pct_before=training_bonus_pct(before),
                bonus_pct_after=training_bonus_pct(after),
                amount=cost,
                amount_units=career.budget_units,
                basis=(
                    f"training ground level {before} → {after}: {training_bonus_pct(before)}% → "
                    f"{training_bonus_pct(after)}% of a session's match-minute value for {cost:,} "
                    f"{career.budget_units}"
                ),
                budget_after=running,
                data_origin="simulation",
                is_demo_data=True,
            )
        )
    career.training_level = current + value
    session.add_all(rows)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows, training_view(session, career)


def gate_form(session: Session, career: Career, *, before_round: int) -> dict[str, Any]:
    """The form the gate reads: the last five results before `before_round`, as a 0–1 figure.

    A win is 1, a draw 0.5 and a loss 0. No row is 0.5 rather than 0, so a career with no history sells
    the neutral share rather than being punished for a match it has not played.
    """
    rows = list(
        session.scalars(
            select(CareerFixture)
            .where(CareerFixture.career_id == career.id, CareerFixture.round_index < int(before_round))
            .order_by(CareerFixture.round_index.desc(), CareerFixture.id.desc())
            .limit(GATE_FORM_WINDOW)
        ).all()
    )
    points = {"W": 1.0, "D": 0.5, "L": 0.0}
    form = sum(points.get(str(row.outcome), 0.5) for row in rows) / len(rows) if rows else 0.5
    return {
        "played": len(rows),
        "form": round(form, 3),
        "factor": round(1.0 + GATE_FORM_SHARE * (2.0 * form - 1.0), 3),
        "window": GATE_FORM_WINDOW,
        "results": [str(row.outcome) for row in rows],
    }

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
    "wage_ceiling": WAGE_CEILING_FORMULA,
    "window": WINDOW_FORMULA,
    "budget": BUDGET_FORMULA,
    "grant": BUDGET_AWARD_FORMULA,
    "gate": GATE_FORMULA,
    "ticket_price": TICKET_PRICE_FORMULA,
    "cup_prize": CUP_PRIZE_FORMULA,
    "objective_bonus": OBJECTIVE_BONUS_FORMULA,
    "stadium": STADIUM_FORMULA,
    "upkeep": STADIUM_UPKEEP_FORMULA,
    "season_tickets": SEASON_TICKET_FORMULA,
    "training": TRAINING_FORMULA,
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


#: §51's sets for this tier. The status each code answers was, until this landing, decided *in the
#: routers* by membership tests over local copies of exactly these lists — two copies, and they had
#: already drifted: `/transfers` answered `no_such_listing`/`player_gone` 404 while `/scout`'s catch
#: answered the same two 409, because its local set named only `no_club`. `answers.ANSWERS` is now
#: the one copy: the routers look a code up, and a verdict code minted by `transferable()` —
#: `career_retired`, `window_closed`, `transfers_forbidden` — arrives here rather than nowhere.
NOT_FOUND_CODES: Final = frozenset({"no_club", "no_such_listing", "player_gone"})
UNPROCESSABLE_CODES: Final = frozenset(
    {"bad_seats", "bad_ticket_price", "bad_season_ticket_seats", "bad_training_levels"}
)
CONFLICT_CODES: Final = frozenset(
    {
        "challenge_budget",
        "career_retired",
        "insufficient_budget",
        "negotiation_closed",
        "no_buyer",
        "not_on_sale",
        "not_your_player",
        "rival_will_not_sell",
        "season_ticket_unavailable",
        "season_ticket_window_closed",
        "season_tickets_already_sold",
        "training_maxed",
        "transfers_forbidden",
        "transfer_window_closed",
        "wage_ceiling_exceeded",
        "window_closed",
        "would_not_field_a_side",
    }
)


def _credits(value: float) -> int:
    """Round a fee to the nearest 5 credits so a printed figure is the stored figure."""
    return int(round(value / CREDIT_ROUND) * CREDIT_ROUND)


def age_curve(age: int) -> float:
    for low, high, weight in AGE_CURVE:
        if low <= age <= high:
            return weight
    return 0.30


def valuation(player: RealPlayer, *, age: int | None = None) -> dict[str, Any]:
    """What this player is worth to a club in this world, from their stored row alone.

    `age` is the career-scoped age item 28 reads (`stored age + closed seasons`). Omitted, it is the
    world's stored age, which is the right answer for a world page that has no career.
    """
    quality = max(0, int(player.overall) - OVERALL_FLOOR)
    headroom = max(0, int(player.potential) - int(player.overall))
    current_age = int(player.age) if age is None else int(age)
    curve = age_curve(current_age)
    asking = _credits((quality * QUALITY_CREDIT + headroom * HEADROOM_CREDIT) * curve)
    return {
        "asking_fee": asking,
        "release_clause": _credits(asking * RELEASE_CLAUSE_SHARE),
        "weekly_wage": max(CREDIT_ROUND, _credits(asking / WAGE_DIVISOR)),
        "contract_years": min(CONTRACT_MAX_YEARS, max(1, CONTRACT_MAX_YEARS - max(0, current_age - PEAK_AGE_END))),
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
    rows = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id.is_not(None), RealPlayer.team_id != (career.club_id or "")).order_by(RealPlayer.slug)).all())
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
    Opening a market is a market act too, so the same verdict every move answers to is asked here first:
    a closed season window does not price a new round's offers.
    """
    _require_transferable(session, career)
    round_index = int(career.rounds_played) + 1
    age_offset = closed_seasons(session, career)
    need = club_need(session, career, round_index=round_index)
    chosen, account = market_selection(session, career, round_index=round_index, need=need)
    existing = {row.player_id: row for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id))}
    created = repriced = withdrawn = kept = 0
    for player in chosen:
        price = valuation(player, age=int(player.age) + age_offset)
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
        row.age = int(player.age) + age_offset
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
    row = session.scalar(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.id == ident)) or session.scalar(
        select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.player_slug == ident)
    )
    if row is None:
        raise MarketRefusal("no_such_listing", f"{ident!r} is not a listing this career was given", career_slug=career.slug)
    return row


def _is_rival(session: Session, career: Career, listing: TransferListing) -> bool:
    """Whether the selling club shares this career's competition, which is what the clause rule turns on."""
    if not (career.competition_id and listing.from_team_id):
        return False
    return bool(session.scalar(select(Team.id).where(Team.id == listing.from_team_id, Team.competition_id == career.competition_id)))


def season_windows(season_rounds: int) -> list[dict[str, Any]]:
    """A season's windows as round ranges, clipped to the season and merged wherever they overlap or touch."""
    raw = [
        (1, min(EARLY_WINDOW_LAST_ROUND, season_rounds), "the opening window"),
        (
            max(1, season_rounds // 2 - MID_WINDOW_HALF_WIDTH),
            min(season_rounds, season_rounds // 2 + MID_WINDOW_HALF_WIDTH),
            "the mid-season window",
        ),
    ]
    merged: list[dict[str, Any]] = []
    for low, high, label in raw:
        if low > high:
            continue
        if merged and low <= int(merged[-1]["to_round"]) + 1:
            merged[-1]["to_round"] = max(int(merged[-1]["to_round"]), high)
            merged[-1]["label"] = "the season's signing windows, merged"
        else:
            merged.append({"from_round": low, "to_round": high, "label": label})
    return merged


def transfer_window(
    session: Session,
    career: Career,
    *,
    horizon: dict[str, Any] | None = None,
    stored_rounds: list[int] | None = None,
) -> dict[str, Any]:
    """Where this career's next round falls against its season's signing windows.

    The round a deal would be made in is `rounds_played + 1`. Rounds are grouped into seasons of
    `season_rounds` — the horizon the season board projects against — so a career that has played past
    its first season is judged against the next season's windows rather than locked out for good. A
    career with no horizon has no window to police and reads open, which is stated rather than assumed.
    `horizon` lets the career view hand in the season length it already computed.

    The block also counts the window it is inside: `played_in_window` is how many of that window's
    rounds the career has played or has a stored fixture for (whichever names more, so a lagging counter
    cannot hide a stored round), `signing_rounds_left` is how many rounds it can
    still sign in (including the next one), and `window_from_round`/`window_to_round` publish the
    range those counts are measured against. A closed window reports zero for both, because a range
    the deal cannot be made in has no signing rounds left rather than an implied one.
    """
    from app.services.simulation.career import season_horizon

    horizon = horizon if horizon is not None else season_horizon(session, career)
    season_rounds = int(horizon["rounds"])
    next_round = int(career.rounds_played) + 1
    if season_rounds <= 0:
        return {
            "state": "open",
            "round": next_round,
            "round_in_season": 0,
            "season_index": 0,
            "season_rounds": 0,
            "season_source": horizon["source"],
            "windows": [],
            "in_window": "",
            "window_from_round": None,
            "window_to_round": None,
            "played_in_window": 0,
            "signing_rounds_left": 0,
            "opens_at_round": None,
            "opens_at_season": None,
            "opens_in_rounds": 0,
            "formula": WINDOW_FORMULA,
        }
    season_index = (next_round - 1) // season_rounds + 1
    round_in_season = (next_round - 1) % season_rounds + 1
    stored = list(stored_rounds) if stored_rounds is not None else _stored_fixture_rounds(session, career.id)
    windows = season_windows(season_rounds)
    containing = next((window for window in windows if int(window["from_round"]) <= round_in_season <= int(window["to_round"])), None)
    window_from_round: int | None = None
    window_to_round: int | None = None
    played_in_window = 0
    signing_rounds_left = 0
    if containing is not None:
        window_from_round = int(containing["from_round"])
        window_to_round = int(containing["to_round"])
        window_first_lifetime = (season_index - 1) * season_rounds + window_from_round
        window_last_lifetime = window_first_lifetime + (window_to_round - window_from_round)
        stored_in_window = [
            value
            for value in stored
            if window_first_lifetime <= value <= window_last_lifetime
        ]
        counter_played = min(
            max(0, int(career.rounds_played) - window_first_lifetime + 1),
            window_to_round - window_from_round + 1,
        )
        played_in_window = max(counter_played, len(stored_in_window))
        blocked_ahead = sum(1 for value in stored_in_window if value >= next_round)
        signing_rounds_left = max(0, window_to_round - round_in_season + 1 - blocked_ahead)
    opens_at_round: int | None = None
    opens_at_season: int | None = None
    if containing is None:
        forward = next((window for window in windows if int(window["from_round"]) > round_in_season), None)
        if forward is not None:
            opens_at_round, opens_at_season = int(forward["from_round"]), season_index
        elif windows:
            # Past the last window of this season, the next one is the following season's opening round.
            opens_at_round, opens_at_season = int(windows[0]["from_round"]), season_index + 1
    opens_in_rounds = 0
    if opens_at_round is not None and opens_at_season is not None:
        opens_in_rounds = (opens_at_season - 1) * season_rounds + opens_at_round - next_round
    return {
        "state": "open" if containing is not None else "closed",
        "round": next_round,
        "round_in_season": round_in_season,
        "season_index": season_index,
        "season_rounds": season_rounds,
        "season_source": horizon["source"],
        "windows": windows,
        "in_window": str(containing["label"]) if containing is not None else "",
        "window_from_round": window_from_round,
        "window_to_round": window_to_round,
        "played_in_window": played_in_window,
        "signing_rounds_left": signing_rounds_left,
        "opens_at_round": opens_at_round,
        "opens_at_season": opens_at_season,
        "opens_in_rounds": opens_in_rounds,
        "formula": WINDOW_FORMULA,
    }


def transferable(session: Session, career: Career) -> dict[str, Any]:
    """Whether this career may change its squad right now, with the rule that says so.

    The refusal a live challenge's `no_transfers` line produces is published here with `enforced: true`
    and the mechanism named, because the market is the thing that does the enforcing. The §21 catalogue
    carries its own copy of that flag and is not edited by this module.
    """
    if career.status != "active":
        return {"ok": False, "code": "career_retired", "message": "this career is retired; its squad is closed", "constraint": "career_status"}
    window_rounds = int(career.challenge_window or 0)
    if window_rounds and int(career.rounds_played) >= window_rounds:
        return {
            "ok": False,
            "code": "window_closed",
            "message": f"the scenario's window closed after {career.rounds_played} of {window_rounds} rounds, so its squad is final",
            "constraint": "window",
            "rounds_played": int(career.rounds_played),
            "window_rounds": window_rounds,
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
    next_round = int(career.rounds_played) + 1
    stored = _stored_fixture_rounds(session, career.id)
    if next_round in stored:
        return {
            "ok": False,
            "code": "round_already_played",
            "message": (
                f"round {next_round} already has a stored fixture, so a squad move cannot be booked into it; "
                "a signing changes the eleven that round would be played with, and that round is already decided"
            ),
            "constraint": "stored_fixture",
            "round": next_round,
            "rounds_played": int(career.rounds_played),
            "stored_rounds": len(stored),
            "latest_stored_round": max(stored),
        }
    window = transfer_window(session, career)
    if window["state"] == "closed":
        opens_at = f"round {window['opens_at_round']}"
        if window["opens_at_season"] != window["season_index"]:
            opens_at = f"round {window['opens_at_round']} of the next season"
        return {
            "ok": False,
            "code": "transfer_window_closed",
            "message": (
                f"the signing window is closed after round {window['round_in_season']} of this {window['season_rounds']}-round season; "
                f"the next one opens at {opens_at}, {window['opens_in_rounds']} rounds from now"
            ),
            "constraint": "transfer_window",
            "round": window["round"],
            "round_in_season": window["round_in_season"],
            "season_index": window["season_index"],
            "season_rounds": window["season_rounds"],
            "opens_at_round": window["opens_at_round"],
            "opens_at_season": window["opens_at_season"],
            "opens_in_rounds": window["opens_in_rounds"],
            "formula": WINDOW_FORMULA,
        }
    return {"ok": True, "code": "", "message": "", "constraint": ""}


def _require_transferable(session: Session, career: Career) -> dict[str, Any]:
    verdict = transferable(session, career)
    if not verdict["ok"]:
        detail = {key: value for key, value in verdict.items() if key not in {"ok", "code", "message"}}
        raise MarketRefusal(str(verdict["code"]), str(verdict["message"]), **detail)
    return verdict


def _stored_fixture_rounds(session: Session, career_id: str) -> list[int]:
    """The rounds this career already has a fixture row for, in order.

    A round's fixture is written by `play_round` in the same transaction that advances `rounds_played`,
    but an imported or repaired row can sit ahead of the counter. A squad move books into the counter's
    next round, so the stored rows -- not the calendar alone -- are what can refuse it.
    """
    return sorted(
        int(round_index)
        for round_index in session.scalars(
            select(CareerFixture.round_index).where(CareerFixture.career_id == career_id)
        )
    )


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
    contract_years: int | None = None,
    expiry_round: int | None = None,
    age_offset: int = 0,
    weekly_wage: int | None = None,
) -> CareerSquadMove:
    """Write one move row, and the balance it left behind, so the ledger adds up by construction.

    The contract terms come from the same valuation the market quoted, which is what makes a *Contract*
    in §22 a stored fact about a deal rather than a page furniture value.
    """
    price = valuation(player, age=int(player.age) + int(age_offset))
    incoming = kind in IN_KINDS
    years = int(price["contract_years"]) if contract_years is None else int(contract_years)
    term = int(expiry_round or 0)
    if term == 0 and kind in ("buy", "youth", "renew"):
        # The term is fixed here, against the season the deal was signed in. A later promotion changes
        # the length of future seasons, and a contract already agreed must not stretch with it.
        from app.services.simulation.career import season_horizon

        season_rounds = int(season_horizon(session, career)["rounds"])
        if season_rounds > 0 and years > 0:
            term = round_index + years * season_rounds - 1
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
        contract_years=years,
        weekly_wage=int(price["weekly_wage"]) if weekly_wage is None else int(weekly_wage),
        loan_until_round=loan_until,
        expiry_round=term,
        listing_id=listing.id if listing else None,
        counterparty_team_id=counterparty.id if counterparty else (listing.from_team_id if listing else None),
        counterparty_name=counterparty.name if counterparty else (listing.from_team_name if listing else ""),
        budget_after=int(balance["remaining"]) - fee if incoming else int(balance["remaining"]) + fee,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(move)
    return move


def held_deals(session: Session, career_id: str, round_index: int, *, moves: list[CareerSquadMove] | None = None) -> list[CareerSquadMove]:
    """The deals this career stands behind in one round, one row per player, in the order they were made.

    The last move for a player is the one that binds: a signing sold on again is not held, and a loan
    whose rounds have run out is not either — `effective_kind` says so without editing the history.
    `moves` lets a caller that already fetched `moves_as_of` hand the list in rather than query it again.
    """
    latest: dict[str, CareerSquadMove] = {}
    for move in (moves if moves is not None else moves_as_of(session, career_id, round_index)):
        latest[move.player_id] = move
    return [move for player_id, move in latest.items() if effective_kind(move, round_index) in IN_KINDS]


def contract_expiry_round(move: CareerSquadMove, season_rounds: int) -> int | None:
    """The last round a permanent deal covers, from the row's stored term or its older fallback.

    A row written after migration 0049 carries the date it was agreed at; a legacy row carries 0 and is
    projected from `signed_round + contract_years × season_rounds − 1`, the formula this project
    published before the date was stored. A loan's last round is `loan_until_round`, and a move that is
    not a permanent incoming deal has no expiry at all.
    """
    if move.kind not in ("buy", "youth", "renew"):
        return None
    if int(move.expiry_round or 0) > 0:
        return int(move.expiry_round)
    if int(move.contract_years) <= 0 or int(season_rounds) <= 0:
        return None
    return int(move.round_index) + int(move.contract_years) * int(season_rounds) - 1


def expire_contracts(
    session: Session,
    career: Career,
    *,
    round_index: int,
    horizon: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write off every permanent deal whose stored last round has passed, before `round_index` is played.

    The market used to *project* an expiry and never enforce one, so a signed player stayed forever and
    the wage bill never shrank. This is the enforcement, and it runs on the only path that advances a
    career. A deal is expired once: the `expire` row becomes that player's latest move, so the squad
    overlay drops them from this round on and `held_deals` stops charging their wage.

    One authored exception keeps a career playable: if letting the deal lapse would leave the club with
    fewer than eleven players or no goalkeeper, the deal is extended by one season at the same stored
    wage with a `renew` row, and the result says which happened and why. Neither row moves money — a
    contract ending is not a fee and not a wage — so both store the standing balance unchanged.
    """
    from app.services.simulation.career import season_horizon

    horizon = horizon if horizon is not None else season_horizon(session, career)
    season_rounds = int(horizon["rounds"])
    held = held_deals(session, career.id, round_index)
    squad, _account = current_squad(session, career)
    working = list(squad)
    expired: list[dict[str, Any]] = []
    renewed: list[dict[str, Any]] = []
    for move in sorted(held, key=lambda row: (str(row.player_name), str(row.id))):
        kind = effective_kind(move, round_index)
        if kind not in ("buy", "youth"):
            continue
        expiry = contract_expiry_round(move, season_rounds)
        if expiry is None or int(expiry) >= int(round_index):
            continue
        player = next((row for row in working if row.id == move.player_id), None)
        if player is None:
            continue
        fielding = can_field_side(working, dropping_id=player.id)
        balance = budget_position(session, career)
        if not fielding["ok"]:
            new_expiry = int(round_index) + RENEWAL_SEASONS * season_rounds - 1 if season_rounds > 0 else 0
            row = CareerSquadMove(
                id=new_public_id("mov"),
                career_id=career.id,
                round_index=int(round_index),
                kind=RENEWAL_KIND,
                player_id=move.player_id,
                player_slug=move.player_slug,
                player_name=move.player_name,
                position=move.position,
                fee=0,
                fee_units=career.budget_units,
                contract_years=RENEWAL_SEASONS,
                weekly_wage=int(move.weekly_wage),
                loan_until_round=0,
                expiry_round=new_expiry,
                budget_after=int(balance["remaining"]),
                data_origin="simulation",
                is_demo_data=True,
            )
            session.add(row)
            renewed.append(
                {
                    "player_id": move.player_id,
                    "player_name": move.player_name,
                    "round_index": int(round_index),
                    "expired_round": int(expiry),
                    "expiry_round": new_expiry,
                    "reason": "letting the deal lapse would leave the club below eleven players or without a keeper",
                    "players": fielding["players"],
                    "keepers": fielding["keepers"],
                }
            )
            continue
        row = CareerSquadMove(
            id=new_public_id("mov"),
            career_id=career.id,
            round_index=int(round_index),
            kind=EXPIRY_KIND,
            player_id=move.player_id,
            player_slug=move.player_slug,
            player_name=move.player_name,
            position=move.position,
            fee=0,
            fee_units=career.budget_units,
            contract_years=int(move.contract_years),
            weekly_wage=int(move.weekly_wage),
            loan_until_round=0,
            expiry_round=int(expiry),
            budget_after=int(balance["remaining"]),
            data_origin="simulation",
            is_demo_data=True,
        )
        session.add(row)
        working.remove(player)
        expired.append(
            {
                "player_id": move.player_id,
                "player_name": move.player_name,
                "round_index": int(round_index),
                "expiry_round": int(expiry),
                "weekly_wage": int(move.weekly_wage),
            }
        )
    session.flush()
    return {
        "checked": len(held),
        "expired": expired,
        "renewed": renewed,
        "round_index": int(round_index),
        "season_rounds": season_rounds,
        "formula": CONTRACT_FORMULA,
    }


def wages_as_of(session: Session, career_id: str, round_index: int) -> list[CareerWageCharge]:
    """Every wage row this career had been charged by the end of `round_index`, oldest round first."""
    return list(
        session.scalars(
            select(CareerWageCharge)
            .where(CareerWageCharge.career_id == career_id, CareerWageCharge.round_index <= round_index)
            .order_by(CareerWageCharge.round_index, CareerWageCharge.created_at, CareerWageCharge.id)
        ).all()
    )


def awards_of(session: Session, career_id: str) -> list[CareerBudgetAward]:
    """Every grant the board has paid this career, season order — the money beside each boundary."""
    return list(
        session.scalars(
            select(CareerBudgetAward).where(CareerBudgetAward.career_id == career_id).order_by(CareerBudgetAward.season_index, CareerBudgetAward.id)
        ).all()
    )


def awards_as_of(session: Session, career_id: str, round_index: int) -> list[CareerBudgetAward]:
    """Every sum the board had paid this career by the end of `round_index`, oldest round first."""
    return list(
        session.scalars(
            select(CareerBudgetAward)
            .where(CareerBudgetAward.career_id == career_id, CareerBudgetAward.round_index <= round_index)
            .order_by(CareerBudgetAward.round_index, CareerBudgetAward.created_at, CareerBudgetAward.id)
        ).all()
    )


def receipts_as_of(session: Session, career_id: str, round_index: int) -> list[CareerGateReceipt]:
    """Every gate this career had earned by the end of `round_index`, oldest round first."""
    return list(
        session.scalars(
            select(CareerGateReceipt)
            .where(CareerGateReceipt.career_id == career_id, CareerGateReceipt.round_index <= round_index)
            .order_by(CareerGateReceipt.round_index, CareerGateReceipt.created_at, CareerGateReceipt.id)
        ).all()
    )


def upkeep_as_of(session: Session, career_id: str, round_index: int) -> list[CareerUpkeepCharge]:
    """Every ground cost this career had paid by the end of `round_index`, oldest round first."""
    return list(
        session.scalars(
            select(CareerUpkeepCharge)
            .where(CareerUpkeepCharge.career_id == career_id, CareerUpkeepCharge.round_index <= round_index)
            .order_by(CareerUpkeepCharge.round_index, CareerUpkeepCharge.created_at, CareerUpkeepCharge.id)
        ).all()
    )


def wage_bill(session: Session, career: Career, *, round_index: int, held: list[CareerSquadMove] | None = None) -> dict[str, Any]:
    """What the deals this career holds would cost for one round, named player by player.

    The same figure is published twice over: as the standing rate beside the budget, and as the `fee` of
    the row written when a round is played. Both come out of this one function, so a page that printed
    one and charged the other would be caught by a test rather than by a reader. `held` lets a caller that
    already resolved the deals hand them in rather than query them again.
    """
    held = held if held is not None else held_deals(session, career.id, round_index)
    names = [f"{move.player_name} {move.weekly_wage:,}" for move in sorted(held, key=lambda move: (-move.weekly_wage, move.player_name))]
    return {
        "players": len(held),
        "fee": sum(int(move.weekly_wage) for move in held),
        "detail": " · ".join(names),
        "units": career.budget_units,
        "formula": WAGE_FORMULA,
    }


def budget_position(
    session: Session,
    career: Career,
    *,
    moves: list[CareerSquadMove] | None = None,
    charges: list[CareerWageCharge] | None = None,
    awards: list[CareerBudgetAward] | None = None,
    receipts: list[CareerGateReceipt] | None = None,
    works: list[CareerStadiumWork] | None = None,
    upkeep: list[CareerUpkeepCharge] | None = None,
    season_tickets: list[CareerSeasonTicket] | None = None,
    training: list[CareerTrainingWork] | None = None,
) -> dict[str, Any]:
    """The budget as an arithmetic: what was stated, what left, what arrived, and what is standing.

    `moves`/`charges`/`awards`/`receipts` let a caller that already fetched the ledger hand the rows in
    rather than query them again — the same figures, one fewer round trip each.
    """
    round_index = int(career.rounds_played) + 1
    moves = moves if moves is not None else moves_as_of(session, career.id, round_index)
    spent = sum(move.fee for move in moves if move.kind in IN_KINDS)
    received_sales = sum(move.fee for move in moves if move.kind == "sell")
    charges = charges if charges is not None else wages_as_of(session, career.id, round_index)
    wages_paid = sum(int(row.fee) for row in charges)
    awards = awards if awards is not None else awards_as_of(session, career.id, round_index)
    # Three kinds share the award table (items 32 and 36): the board's season grant, a cup round's prize and
    # the bonus a met objective pays. They are split here rather than in the table because the balance is one
    # arithmetic and a reader must be able to see which income moved it.
    grants = [row for row in awards if str(row.kind) == "season_grant"]
    prize_rows = [row for row in awards if str(row.kind) == "cup_prize"]
    bonus_rows = [row for row in awards if str(row.kind) == "objective_bonus"]
    granted = sum(int(row.amount) for row in grants)
    received_cup = sum(int(row.amount) for row in prize_rows)
    received_objectives = sum(int(row.amount) for row in bonus_rows)
    receipts = receipts if receipts is not None else receipts_as_of(session, career.id, round_index)
    received_gate = sum(int(row.amount) for row in receipts)
    gate_cup_rows = [row for row in receipts if row.tie_id]
    received_gate_cup = sum(int(row.amount) for row in gate_cup_rows)
    works = works if works is not None else stadium_works_of(session, career.id)
    stadium_spent = sum(int(row.amount) for row in works)
    upkeep = upkeep if upkeep is not None else upkeep_as_of(session, career.id, round_index)
    upkeep_spent = sum(int(row.amount) for row in upkeep)
    season_tickets = (
        season_tickets
        if season_tickets is not None
        else [row for row in season_tickets_of(session, career.id) if int(row.round_index) <= round_index]
    )
    season_ticket_income = sum(int(row.amount) for row in season_tickets)
    training = training if training is not None else training_works_of(session, career.id)
    training_spent = sum(int(row.amount) for row in training)
    received = received_sales + received_gate + received_cup
    standing = wage_bill(session, career, round_index=round_index, held=held_deals(session, career.id, round_index, moves=moves))
    return {
        "budget": int(career.budget),
        "spent": spent,
        "received": received,
        "received_sales": received_sales,
        "received_gate": received_gate,
        "gate_rows": len(receipts),
        "received_gate_cup": received_gate_cup,
        "gate_cup_rows": len(gate_cup_rows),
        "gate_detail": " · ".join(
            (
                f"cup tie after round {int(row.round_index)}: {int(row.amount):,}"
                if row.tie_id
                else f"round {int(row.round_index)}: {int(row.amount):,}"
            )
            for row in receipts
        ),
        "received_cup": received_cup,
        "cup_rows": len(prize_rows),
        "cup_detail": " · ".join(f"{row.stage}: {int(row.amount):,}" for row in prize_rows),
        "granted": granted,
        "grant_rows": len(grants),
        "grant_detail": " · ".join(f"season {int(row.season_index)}: {int(row.amount):,}" for row in grants),
        "received_objectives": received_objectives,
        "objective_rows": len(bonus_rows),
        "objective_detail": " · ".join(
            f"season {int(row.season_index)} {row.stage}: {int(row.amount):,}"
            for row in sorted(bonus_rows, key=lambda row: (int(row.season_index), str(row.stage)))
        ),
        "award_rows": len(awards),
        "wages_paid": wages_paid,
        "stadium_spent": stadium_spent,
        "stadium_rows": len(works),
        "stadium_detail": " · ".join(
            f"round {int(row.round_index)}: +{int(row.seats):,} seats for {int(row.amount):,}" for row in works
        ),
        "upkeep_spent": upkeep_spent,
        "upkeep_rows": len(upkeep),
        "upkeep_detail": " · ".join(
            (
                f"cup tie after round {int(row.round_index)}: {int(row.amount):,}"
                if row.tie_id
                else f"round {int(row.round_index)}: {int(row.amount):,}"
            )
            for row in upkeep
        ),
        "season_ticket_income": season_ticket_income,
        "season_ticket_rows": len(season_tickets),
        "season_ticket_detail": " · ".join(
            f"season {int(row.season_index)}: {int(row.seats):,} seats for {int(row.amount):,}"
            for row in season_tickets
        ),
        "training_spent": training_spent,
        "training_rows": len(training),
        "training_detail": " · ".join(
            f"level {int(row.level_before)} → {int(row.level_after)}: {int(row.amount):,}"
            for row in training
        ),
        "remaining": (
            int(career.budget)
            + received
            + granted
            + received_objectives
            + season_ticket_income
            - spent
            - wages_paid
            - stadium_spent
            - upkeep_spent
            - training_spent
        ),
        "units": career.budget_units,
        "moves": len(moves),
        "wage_rows": len(charges),
        "wage_rounds": sorted({int(row.round_index) for row in charges}),
        "wage_committed_per_week": standing["fee"],
        "wage_players": standing["players"],
        "wage_detail": standing["detail"],
        "wage_ceiling": int(career.wage_ceiling),
        "wage_headroom": wage_headroom(int(career.wage_ceiling), int(standing["fee"])),
        "wage_note": ("charged every round this career plays: the deals it holds cost their agreed weekly wage, and each round's charge is a row of its own below"),
        "formula": BUDGET_FORMULA,
    }


#: The affordability arithmetic, published beside the numbers so a reader can reproduce it.
AFFORDABILITY_FORMULA: Final = (
    "wage_runway_rounds = max(0, floor(remaining ÷ wage_committed_per_week)) when the weekly bill is "
    "positive; a signing is affordable when remaining − price ≥ 0, and its new runway is computed on the "
    "balance after the fee against the wage bill the signing would add; when the board's wage ceiling is "
    "set, a signing is also wage-affordable only when the new bill is at or under it"
)

#: The budget timeline's arithmetic: opening balance plus each ledger row's delta, in round order.
TIMELINE_FORMULA: Final = (
    "balance starts at career.budget and moves by each ledger row in round order (a round's moves and any stand "
    "bought for it first, by the time each was written, then its gate receipt and the ground upkeep it pays, "
    "then its wage charge, a boundary's grant after all three, then the objective bonuses "
    "that boundary paid, in objective-kind order, and a cup tie's own money last): sell +fee, buy/loan −fee, "
    "release 0, stadium −amount, gate +amount, upkeep −amount, wage −fee, grant +amount, objective bonus +amount, cup prize "
    "+amount; each row's "
    "stored budget_after is compared with the running figure and any disagreement is counted"
)

#: The contract book's arithmetic, and how close to expiry a deal is called "soon".
CONTRACT_FORMULA: Final = (
    "expiry_round is stored when a permanent deal is signed as signed_round + contract_years × the season length "
    "then in force − 1, or is the loan's agreed loan_until_round; rounds_remaining = max(0, expiry_round − "
    "current_round + 1); a permanent deal whose expiry_round has passed is written off with an `expire` row "
    "before the next round is played, and if that departure would leave the club unable to field eleven with a "
    "keeper the deal is instead extended by one season at the same wage with a `renew` row; a row written before "
    "migration 0049 carries expiry_round 0 and is projected from its stored terms until it is re-signed"
)
EXPIRY_WARNING_ROUNDS: Final = 3

#: The move kinds this module writes when a deal's own date decides the squad, rather than a manager's click.
EXPIRY_KIND: Final = "expire"
RENEWAL_KIND: Final = "renew"
RENEWAL_SEASONS: Final = 1
#: What a manager-chosen renewal costs before the wage: a share of the player's asking fee.
RENEWAL_FEE_SHARE: Final = 0.05
RENEWAL_DEMAND_MINUTES_BASE: Final = 0.90
RENEWAL_DEMAND_MINUTES_SPAN: Final = 0.20
RENEWAL_TIER_FACTORS: Final[dict[int, float]] = {1: 1.15, 2: 1.00, 0: 0.90}
RENEWAL_FORMULA: Final = (
    "signing-on fee = round_5(asking × 5% × years); the player's demand = round_5(valuation wage × tier_factor × "
    "minutes_factor), where tier_factor = 1.15 in tier 1, 1.00 in tier 2 and 0.90 in a cup, and minutes_factor = "
    "0.90 + 0.20 × (career appearance minutes ÷ (rounds_played × 90), clamped to 0–1); an offer at or above the "
    "demand is accepted, a lower one is refused with the demand named; expiry_round = the round the renewal is "
    "signed before + years × season_rounds − 1; the deal is refused when the fee exceeds the balance, the bill "
    "after replacing the old wage exceeds the board's ceiling, or the career has no season length to measure the "
    "term against"
)
# `RULES` is declared above the contract section for the ordering of the public table; the renewal
# sentence joins it here, once, rather than being written a second time.
RULES["renewal"] = RENEWAL_FORMULA

#: The age at which the squad profile *flags* a retirement risk. The boundary that actually retires a player
#: reads `ageing.RETIREMENT_AGE` (40), which includes the seasons this career has closed; this flag is a
#: warning on the same career-clock age and ends nothing.
RETIREMENT_AGE: Final = 35


def season_grant(*, rounds: int, points: int, verdict: str, units: str) -> dict[str, Any]:
    """What the board pays for one closed season, in the words the row carries.

    Three authored figures and nothing else, so the `basis` string can be checked against the season's own
    rounds and points without running the code again. A season nobody played adds nothing and writes no row,
    and a challenge's window is the one verdict that pays nothing whatever its record: that run is judged by
    the challenge's own reward, and this is the single place the rule is stated.
    """
    played = max(0, int(rounds))
    earned = max(0, int(points))
    if verdict == "challenge":
        return {
            "rounds": played,
            "points": earned,
            "verdict": verdict,
            "units": units,
            "per_round": SEASON_GRANT_PER_ROUND,
            "per_point": SEASON_GRANT_PER_POINT,
            "promotion": 0,
            "amount": 0,
            "basis": "a challenge's window is judged by the challenge's own reward, so the boundary pays no grant",
            "formula": BUDGET_AWARD_FORMULA,
        }
    promotion = PROMOTION_GRANT if verdict == "promoted" else 0
    parts = [f"{played} round(s) × {SEASON_GRANT_PER_ROUND:,}", f"{earned} point(s) × {SEASON_GRANT_PER_POINT:,}"]
    if promotion:
        parts.append(f"promotion {promotion:,}")
    return {
        "rounds": played,
        "points": earned,
        "verdict": verdict,
        "units": units,
        "per_round": SEASON_GRANT_PER_ROUND,
        "per_point": SEASON_GRANT_PER_POINT,
        "promotion": promotion,
        "amount": played * SEASON_GRANT_PER_ROUND + earned * SEASON_GRANT_PER_POINT + promotion,
        "basis": " + ".join(parts),
        "formula": BUDGET_AWARD_FORMULA,
    }


def objective_bonus_report(*, objectives: list[dict[str, Any]], verdict: str, units: str) -> dict[str, Any]:
    """What the board pays for the objectives a season met, one entry per met objective.

    The verdicts it reads are `objectives_of`'s — the same report the board prints — so the money cannot
    disagree with the prose a manager saw. A challenge's window is judged by the challenge's own reward,
    and a target of zero or less asks for nothing, so neither pays. The single place both rules are stated:
    the boundary pays through this function and the seasons page projects through it.
    """
    if verdict == "challenge":
        return {
            "amount": 0,
            "units": units,
            "rows": [],
            "basis": "a challenge's window is judged by the challenge's own reward, so no objective pays a bonus",
            "formula": OBJECTIVE_BONUS_FORMULA,
        }
    rows: list[dict[str, Any]] = []
    for verdict_row in objectives:
        kind = str(verdict_row.get("kind", ""))
        target = int(verdict_row.get("target", 0))
        amount = int(OBJECTIVE_BONUS_BY_KIND.get(kind, 0))
        if not bool(verdict_row.get("met")) or target <= 0 or amount <= 0:
            continue
        actual = int(verdict_row.get("actual", 0))
        label = str(verdict_row.get("label") or kind)
        rows.append(
            {
                "kind": kind,
                "label": label,
                "target": target,
                "actual": actual,
                "amount": amount,
                "basis": f"{label}: {actual} ≥ {target} pays {amount:,} {units}",
            }
        )
    total = sum(int(row["amount"]) for row in rows)
    return {
        "amount": total,
        "units": units,
        "rows": rows,
        "basis": " + ".join(f"{row['kind']} {int(row['amount']):,}" for row in rows) if rows else "no objective the season met pays a bonus",
        "formula": OBJECTIVE_BONUS_FORMULA,
    }


def wage_runway(remaining: int, weekly_wage: int) -> int | None:
    """How many further rounds the current balance covers the current weekly wage bill.

    `None` when there is no wage obligation at all (the bill is zero), because a career that pays no
    wages has no wage-driven limit rather than an infinite one a page would have to print as a number.
    A balance already below zero yields 0: the runway is spent, which is the same thing the market says
    when it stops spending from a negative balance.
    """
    weekly = int(weekly_wage)
    if weekly <= 0:
        return None
    return max(0, int(remaining) // weekly)


def wage_headroom(ceiling: int, weekly_wage: int) -> int | None:
    """What the current bill leaves under the ceiling, or `None` when the career has no ceiling.

    Signed, not clamped: a bill above the ceiling reports the overrun as a negative number rather than
    pretending the career is exactly at its cap.
    """
    if int(ceiling) <= 0:
        return None
    return int(ceiling) - int(weekly_wage)


def signing_impact(remaining: int, weekly_wage: int, *, price: int, proposed_weekly_wage: int, wage_ceiling: int = 0) -> dict[str, Any]:
    """What one prospective signing would do to the balance and the wage runway, before it is made.

    Pure arithmetic over the figures the ledger already publishes, so a page can answer "can I afford
    this" without writing anything: `fee_affordable` is the balance after the fee staying non-negative,
    and the new runway is that balance against the wage bill the signing would add. When the career has
    a wage ceiling, the same preview also answers the hard cap: `wage_affordable` is the new bill at or
    under it, and `wage_headroom_after` is what would be left. It is a preview of the rules
    `buy`/`loan` enforce, not a second copy of them.
    """
    price = int(price)
    proposed = int(proposed_weekly_wage)
    after_fee = int(remaining) - price
    new_bill = int(weekly_wage) + proposed
    ceiling = int(wage_ceiling)
    return {
        "price": price,
        "proposed_weekly_wage": proposed,
        "fee_affordable": after_fee >= 0,
        "remaining_after_fee": after_fee,
        "new_weekly_wage_bill": new_bill,
        "new_wage_runway_rounds": wage_runway(after_fee, new_bill),
        "wage_ceiling": ceiling,
        "wage_affordable": None if ceiling <= 0 else new_bill <= ceiling,
        "wage_headroom_after": None if ceiling <= 0 else ceiling - new_bill,
    }


def affordability_view(session: Session, career: Career, *, price: int = 0, weekly_wage: int = 0) -> dict[str, Any]:
    """This career's finance standing and what a signing at `price`/`weekly_wage` would do to it.

    Everything is read from `budget_position` — the same arithmetic the transfers page prints — and
    recomputed on the request, so the runway and the signing preview cannot drift from the balance they
    are derived from. With no prospective signing passed, the preview is the arithmetic for a move at
    zero fee and zero wage, which is the standing position itself.
    """
    round_index = int(career.rounds_played) + 1
    moves = moves_as_of(session, career.id, round_index)
    charges = wages_as_of(session, career.id, round_index)
    awards = awards_as_of(session, career.id, round_index)
    receipts = receipts_as_of(session, career.id, round_index)
    works = stadium_works_of(session, career.id)
    upkeep = upkeep_as_of(session, career.id, round_index)
    season_tickets = [
        row for row in season_tickets_of(session, career.id) if int(row.round_index) <= round_index
    ]
    training = training_works_of(session, career.id)
    position = budget_position(
        session,
        career,
        moves=moves,
        charges=charges,
        awards=awards,
        receipts=receipts,
        works=works,
        upkeep=upkeep,
        season_tickets=season_tickets,
        training=training,
    )
    remaining = int(position["remaining"])
    weekly = int(position["wage_committed_per_week"])
    return {
        "remaining": remaining,
        "granted": int(position["granted"]),
        "grant_rows": int(position["grant_rows"]),
        "grant_detail": str(position["grant_detail"]),
        "received_gate": int(position["received_gate"]),
        "gate_rows": int(position["gate_rows"]),
        "gate_detail": str(position["gate_detail"]),
        "received_cup": int(position["received_cup"]),
        "cup_rows": int(position["cup_rows"]),
        "cup_detail": str(position["cup_detail"]),
        "received_objectives": int(position["received_objectives"]),
        "objective_rows": int(position["objective_rows"]),
        "objective_detail": str(position["objective_detail"]),
        "award_rows": int(position["award_rows"]),
        "stadium_spent": int(position["stadium_spent"]),
        "stadium_rows": int(position["stadium_rows"]),
        "stadium_detail": str(position["stadium_detail"]),
        "upkeep_spent": int(position["upkeep_spent"]),
        "upkeep_rows": int(position["upkeep_rows"]),
        "upkeep_detail": str(position["upkeep_detail"]),
        "training_spent": int(position["training_spent"]),
        "training_rows": int(position["training_rows"]),
        "training_detail": str(position["training_detail"]),
        "season_ticket_income": int(position["season_ticket_income"]),
        "season_ticket_rows": int(position["season_ticket_rows"]),
        "season_ticket_detail": str(position["season_ticket_detail"]),
        "weekly_wage_bill": weekly,
        "wage_players": int(position["wage_players"]),
        "wage_runway_rounds": wage_runway(remaining, weekly),
        "wage_ceiling": int(career.wage_ceiling),
        "wage_headroom": wage_headroom(int(career.wage_ceiling), weekly),
        "within_ceiling": int(career.wage_ceiling) <= 0 or weekly <= int(career.wage_ceiling),
        "signing": signing_impact(remaining, weekly, price=price, proposed_weekly_wage=weekly_wage, wage_ceiling=int(career.wage_ceiling)),
        "units": position["units"],
        "formula": AFFORDABILITY_FORMULA,
        "note": (
            "a read-only preview: the runway is how many more rounds the balance covers the wage bill the career "
            "already holds, the ceiling is the board's hard cap on one round's wage bill, and the signing block is "
            "the same arithmetic with one prospective deal added"
        ),
        "timeline": budget_timeline(
            session,
            career,
            limit=8,
            moves=moves,
            charges=charges,
            awards=awards,
            receipts=receipts,
            works=works,
            upkeep=upkeep,
            season_tickets=season_tickets,
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def budget_timeline(
    session: Session,
    career: Career,
    *,
    limit: int = 12,
    moves: list[CareerSquadMove] | None = None,
    charges: list[CareerWageCharge] | None = None,
    awards: list[CareerBudgetAward] | None = None,
    receipts: list[CareerGateReceipt] | None = None,
    works: list[CareerStadiumWork] | None = None,
    upkeep: list[CareerUpkeepCharge] | None = None,
    season_tickets: list[CareerSeasonTicket] | None = None,
    training: list[CareerTrainingWork] | None = None,
) -> dict[str, Any]:
    """The balance over time, recomputed from the ledger rows and checked against each row's stored figure.

    Moves, gate receipts, wage charges and every kind of award are the whole ledger, and each row stores
    the `budget_after` it produced. This walks them in round order (a round's moves before its gate, then
    the wage charge, that boundary's grant and the bonuses it paid, then the cup tie's own money),
    recomputes the running balance from `career.budget`, and counts every row whose stored figure
    disagrees — so a page can print the trajectory and a reader can add the column up to the same total.
    """
    round_index = int(career.rounds_played) + 1
    keyed: list[tuple[tuple[int, int, str, str, str], dict[str, Any]]] = []
    for training_work in training if training is not None else training_works_of(session, career.id):
        keyed.append(
            (
                (int(training_work.round_index), 0, "", str(training_work.created_at or ""), str(training_work.id)),
                {
                    "round_index": int(training_work.round_index),
                    "kind": "training",
                    "label": f"training ground, level {int(training_work.level_after)}",
                    "delta": -int(training_work.amount),
                    "stored_budget_after": int(training_work.budget_after),
                },
            )
        )
    for sale in (
        season_tickets
        if season_tickets is not None
        else [row for row in season_tickets_of(session, career.id) if int(row.round_index) <= round_index]
    ):
        keyed.append(
            (
                (int(sale.round_index), 0, "", str(sale.created_at or ""), str(sale.id)),
                {
                    "round_index": int(sale.round_index),
                    "kind": "season_tickets",
                    "label": f"season tickets, {int(sale.seats):,} seats",
                    "delta": int(sale.amount),
                    "stored_budget_after": int(sale.budget_after),
                },
            )
        )
    for move in (moves if moves is not None else moves_as_of(session, career.id, round_index)):
        kind = str(move.kind)
        delta = int(move.fee) if kind == "sell" else -int(move.fee) if kind in IN_KINDS else 0
        keyed.append(
            (
                (int(move.round_index), 0, "", str(move.created_at or ""), str(move.id)),
                {
                    "round_index": int(move.round_index),
                    "kind": kind,
                    "label": f"{kind} {move.player_name}".strip(),
                    "delta": delta,
                    "stored_budget_after": int(move.budget_after),
                },
            )
        )
    for work in (works if works is not None else stadium_works_of(session, career.id)):
        # A stand is bought before the next round is played, so it shares the round's first slot with its
        # moves and is ordered against them by the time it was written. Its money left the balance then.
        keyed.append(
            (
                (int(work.round_index), 0, "", str(work.created_at or ""), str(work.id)),
                {
                    "round_index": int(work.round_index),
                    "kind": "stadium",
                    "label": f"stadium, +{int(work.seats):,} seats",
                    "delta": -int(work.amount),
                    "stored_budget_after": int(work.budget_after),
                },
            )
        )
    for receipt in (receipts if receipts is not None else receipts_as_of(session, career.id, round_index)):
        # A cup gate and a cup prize share the round the tie was played after, and both were written after
        # that round's league rows — so they sort after its award, at key 4. The tie's own gate precedes
        # its prize by creation time.
        cup = bool(receipt.tie_id)
        keyed.append(
            (
                (int(receipt.round_index), 4 if cup else 1, "", str(receipt.created_at or ""), str(receipt.id)),
                {
                    "round_index": int(receipt.round_index),
                    "kind": "cup_gate" if cup else "gate",
                    "label": f"{'cup ' if cup else ''}gate receipts, {int(receipt.attendance):,} seats",
                    "delta": int(receipt.amount),
                    "stored_budget_after": int(receipt.budget_after),
                },
            )
        )
    for upkeep_charge in (upkeep if upkeep is not None else upkeep_as_of(session, career.id, round_index)):
        # The ground's cost is written immediately after the gate that paid it, and before the wages of
        # the same round, so it shares the gate's slot and is ordered against it by write time.
        cup = bool(upkeep_charge.tie_id)
        keyed.append(
            (
                (
                    int(upkeep_charge.round_index),
                    4 if cup else 1,
                    "",
                    str(upkeep_charge.created_at or ""),
                    str(upkeep_charge.id),
                ),
                {
                    "round_index": int(upkeep_charge.round_index),
                    "kind": "cup_upkeep" if cup else "upkeep",
                    "label": f"{'cup ' if cup else ''}ground upkeep, {int(upkeep_charge.capacity):,} seats",
                    "delta": -int(upkeep_charge.amount),
                    "stored_budget_after": int(upkeep_charge.budget_after),
                },
            )
        )
    for charge in (charges if charges is not None else wages_as_of(session, career.id, round_index)):
        keyed.append(
            (
                (int(charge.round_index), 2, "", str(charge.created_at or ""), str(charge.id)),
                {
                    "round_index": int(charge.round_index),
                    "kind": "wage",
                    "label": f"wages for {int(charge.players)} player(s)",
                    "delta": -int(charge.fee),
                    "stored_budget_after": int(charge.budget_after),
                },
            )
        )
    for award in (awards if awards is not None else awards_as_of(session, career.id, round_index)):
        kind = str(award.kind)
        keyed.append(
            (
                # The grant precedes the bonuses it was paid with; among the bonuses the objective's kind
                # orders them, which is the order `pay_objective_bonuses` writes them in. Ids are random
                # tokens, so without this the running balance would depend on how fast the rows were written.
                (int(award.round_index), 4 if kind == "cup_prize" else 3, str(award.stage) if kind == "objective_bonus" else "", str(award.created_at or ""), str(award.id)),
                {
                    "round_index": int(award.round_index),
                    "kind": kind,
                    "label": (
                        f"board grant for season {int(award.season_index)}"
                        if kind == "season_grant"
                        else f"cup prize, {award.stage}"
                        if kind == "cup_prize"
                        else f"objective bonus, {award.stage}"
                    ),
                    "delta": int(award.amount),
                    "stored_budget_after": int(award.budget_after),
                },
            )
        )
    keyed.sort(key=lambda item: item[0])
    balance = int(career.budget)
    rows: list[dict[str, Any]] = []
    disagreements = 0
    for _key, entry in keyed:
        balance += int(entry["delta"])
        agrees = int(entry["stored_budget_after"]) == balance
        if not agrees:
            disagreements += 1
        rows.append({**entry, "balance": balance, "agrees": agrees})
    shown = rows[-limit:] if limit > 0 else rows
    return {
        "entries": len(rows),
        "entries_shown": len(shown),
        "truncated": len(shown) < len(rows),
        "opening_balance": int(career.budget),
        "closing_balance": balance,
        "disagreements": disagreements,
        "rows": shown,
        "units": career.budget_units,
        "formula": TIMELINE_FORMULA,
        "note": (
            "recomputed in round order from career.budget; a row whose stored budget_after disagrees with the "
            "running figure is counted, not hidden"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def renewal_terms(
    session: Session,
    career: Career,
    player: RealPlayer,
    *,
    years: int | None = None,
) -> dict[str, Any]:
    """What a renewal of `years` costs and what the player asks for it.

    The signing-on fee scales with the term: a five-year commitment costs five times the one-year fee,
    because the club is buying five seasons of the player's registration rather than one. The wage the
    player asks is the valuation wage adjusted by two measured things: the competition's tier (a tier-1
    player has better alternatives) and the share of available minutes the career has actually given
    them (`appearance minutes ÷ (rounds_played × 90)`). A regular asks more than a bench player; an
    unused player asks less. Both are published beside the number.
    """
    price = valuation(player, age=effective_age(player, closed_seasons(session, career)))
    chosen = int(price["contract_years"]) if years is None else int(years)
    minutes = int(
        session.scalar(
            select(func.coalesce(func.sum(CareerAppearance.minutes), 0)).where(
                CareerAppearance.career_id == career.id,
                CareerAppearance.player_id == player.id,
            )
        )
        or 0
    )
    possible = max(1, int(career.rounds_played) * 90)
    share = min(1.0, max(0.0, minutes / possible))
    tier = 0
    if career.competition_id:
        competition = session.get(Competition, career.competition_id)
        tier = int(competition.tier) if competition is not None else 0
    tier_factor = RENEWAL_TIER_FACTORS.get(tier, 1.0)
    minutes_factor = RENEWAL_DEMAND_MINUTES_BASE + RENEWAL_DEMAND_MINUTES_SPAN * share
    demand = max(CREDIT_ROUND, _credits(int(price["weekly_wage"]) * tier_factor * minutes_factor))
    fee_per_year = max(CREDIT_ROUND, _credits(int(price["asking_fee"]) * RENEWAL_FEE_SHARE))
    return {
        "valuation": price,
        "years": chosen,
        "fee": fee_per_year * max(1, chosen),
        "fee_per_year": fee_per_year,
        "demand_wage": demand,
        "minutes": minutes,
        "possible_minutes": possible,
        "minutes_share": round(share, 3),
        "tier": tier,
        "tier_factor": tier_factor,
        "minutes_factor": round(minutes_factor, 3),
        "formula": RENEWAL_FORMULA,
    }


def contract_book(session: Session, career: Career, *, season_rounds: int, age_offset: int = 0) -> dict[str, Any]:
    """The deals this career holds and when their stored terms project them to expire.

    A permanent deal's expiry is the `expiry_round` stored when it was signed; a legacy row without one
    falls back to `signed_round + contract_years × season_rounds − 1`, and a loan's is the
    `loan_until_round` it was agreed at. `rounds_remaining` counts from the round about to be played, and
    a deal inside `EXPIRY_WARNING_ROUNDS` is flagged. Expiry is enforced before the round after the
    stored last one is played; `recent` names the deals that already ended or were extended.
    """
    round_index = int(career.rounds_played) + 1
    held = held_deals(session, career.id, round_index)
    balance = budget_position(session, career)
    standing = wage_bill(session, career, round_index=round_index, held=held)
    ceiling = int(career.wage_ceiling or 0)
    squad, _account = current_squad(session, career)
    ages = sorted(effective_age(player, age_offset) for player in squad)
    rows: list[dict[str, Any]] = []
    for move in held:
        kind = effective_kind(move, round_index)
        if kind in ("loan", "loan_out"):
            expiry: int | None = int(move.loan_until_round or 0) or None
            basis = "the loan's agreed last round"
        elif int(move.expiry_round or 0) > 0:
            expiry = int(move.expiry_round)
            basis = "the expiry round stored when the deal was signed"
        elif int(season_rounds) > 0 and int(move.contract_years) > 0:
            expiry = int(move.round_index) + int(move.contract_years) * int(season_rounds) - 1
            basis = f"legacy row: {int(move.contract_years)} year(s) × {int(season_rounds)} rounds, projected"
        else:
            expiry = None
            basis = "no contract length to project from"
        remaining = max(0, expiry - round_index + 1) if expiry is not None else None
        renewal: dict[str, Any] | None = None
        if kind in ("buy", "youth", "renew"):
            player = session.get(RealPlayer, move.player_id)
            if player is not None:
                terms = renewal_terms(session, career, player)
                fee = int(terms["fee"])
                new_wage = int(terms["demand_wage"])
                new_bill = int(standing["fee"]) - int(move.weekly_wage) + new_wage
                fee_affordable = int(balance["remaining"]) >= fee
                wage_affordable = ceiling <= 0 or new_bill <= ceiling
                renewal = {
                    "years": int(terms["years"]),
                    "weekly_wage": new_wage,
                    "fee": fee,
                    "fee_units": career.budget_units,
                    "balance_after_fee": int(balance["remaining"]) - fee,
                    "wage_bill_after": new_bill,
                    "wage_ceiling": ceiling,
                    "fee_affordable": fee_affordable,
                    "wage_affordable": wage_affordable,
                    "can_renew": fee_affordable and wage_affordable,
                    "demand_wage": new_wage,
                    "fee_per_year": int(terms["fee_per_year"]),
                    "minutes_share": terms["minutes_share"],
                    "tier_factor": terms["tier_factor"],
                    "minutes_factor": terms["minutes_factor"],
                    "formula": RENEWAL_FORMULA,
                }
        rows.append(
            {
                "player_id": move.player_id,
                "player_name": move.player_name,
                "player_slug": move.player_slug,
                "position": move.position,
                "kind": kind,
                "weekly_wage": int(move.weekly_wage),
                "signed_round": int(move.round_index),
                "contract_years": int(move.contract_years),
                "expiry_round": expiry,
                "rounds_remaining": remaining,
                "expiring_soon": remaining is not None and remaining <= EXPIRY_WARNING_ROUNDS,
                "basis": basis,
                "renewal": renewal,
            }
        )
    rows.sort(key=lambda item: (item["rounds_remaining"] is None, item["rounds_remaining"] or 0, str(item["player_name"])))
    expiring = [row for row in rows if row["expiring_soon"]]
    age_profile = {
        "players": len(ages),
        "mean": round(sum(ages) / len(ages), 1) if ages else None,
        "median": ages[len(ages) // 2] if ages else None,
        "bands": {
            "under_21": sum(1 for age in ages if age < 21),
            "21_to_25": sum(1 for age in ages if 21 <= age <= 25),
            "26_to_29": sum(1 for age in ages if 26 <= age <= 29),
            "30_to_33": sum(1 for age in ages if 30 <= age <= 33),
            "34_plus": sum(1 for age in ages if age >= 34),
        },
        "retirement_age": int(RETIREMENT_THRESHOLD),
            "retirement_risk": [
                {"player_name": name, "age": age}
                for name, age in sorted(
                    [
                        (player.name, effective_age(player, age_offset))
                        for player in squad
                        if effective_age(player, age_offset) >= RETIREMENT_AGE
                    ],
                key=lambda row: (-row[1], row[0]),
            )
        ],
            "note": (
                "ages are the world's stored figures plus the seasons this career has closed; a boundary "
                f"retires a player at {RETIREMENT_THRESHOLD} only when the squad would still field eleven with a keeper"
            ),
    }
    # How many players the current squad carries at each position — the depth a manager checks before
    # signing, read from the same squad `age_profile` already walked, so no extra query.
    position_counts: dict[str, int] = {}
    for player in squad:
        position = str(player.position or "unknown")
        position_counts[position] = position_counts.get(position, 0) + 1
    positions = [{"position": position, "players": count} for position, count in sorted(position_counts.items())]
    endings = list(
        session.scalars(
            select(CareerSquadMove)
            .where(CareerSquadMove.career_id == career.id, CareerSquadMove.kind.in_((EXPIRY_KIND, RENEWAL_KIND, RETIRE_KIND)))
            .order_by(CareerSquadMove.round_index.desc(), CareerSquadMove.id.desc())
            .limit(5)
        ).all()
    )
    return {
        "deals": len(rows),
        "expiring_soon": len(expiring),
        "warning_rounds": EXPIRY_WARNING_ROUNDS,
        "current_round": round_index,
        "season_rounds": int(season_rounds),
        "total_weekly_wage": sum(row["weekly_wage"] for row in rows),
        "expiring_weekly_wage": sum(row["weekly_wage"] for row in expiring),
        "rows": rows,
        "recent": [
            {
                "player_id": row.player_id,
                "player_name": row.player_name,
                "kind": row.kind,
                "round_index": int(row.round_index),
                "expiry_round": int(row.expiry_round),
                "weekly_wage": int(row.weekly_wage),
                "effect": MOVE_EFFECT.get(row.kind, ""),
            }
            for row in endings
        ],
        "positions": positions,
        "age_profile": age_profile,
        "units": career.budget_units,
        "formula": CONTRACT_FORMULA,
        "note": (
            "a permanent deal ends before the round after its stored expiry round; if that would leave the club "
            "unable to field eleven with a keeper, it is extended by one season at the same wage instead, and "
            "`recent` names which happened. The club's own stored squad carries no contract of its own"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def _gate_terms(
    session: Session,
    career: Career,
    *,
    club: Team | None,
    tier: int,
    before_round: int,
    world_match_id: str | None,
    seed: int,
    season_ticket_seats: int = 0,
) -> tuple[int, int, int, str, dict[str, Any], int, int, int]:
    """The crowd one home gate is paid on: capacity, attendance, base ticket price, where it came from,
    form, the manager's price setting, the demand that setting drew, and the season-ticket seats among
    the crowd.

    Shared by the league round and the cup tie so the two cannot drift: capacity with the tier factor,
    the world's stored attendance when the fixture is the world's own, otherwise a deterministic share of
    the ground, then the stored form factor and the price's demand factor, capped at the ground.
    """
    capacity, capacity_factor, _bought, capacity_source = gate_capacity_for(session, career, club, tier)
    form = gate_form(session, career, before_round=before_round)
    source = ""
    base = 0
    if world_match_id:
        world_match = session.get(RealMatch, world_match_id)
        if world_match is not None:
            stats = world_match.stats or {}
            base = int(stats.get("attendance") or 0)
            source = "the world fixture's stored attendance"
    if base <= 0:
        share = GATE_ROTATION_ATTENDANCE_FLOOR + int(seed) % (
            GATE_ROTATION_ATTENDANCE_CEILING - GATE_ROTATION_ATTENDANCE_FLOOR + 1
        )
        base = capacity * share // 100
        source = (
            f"{share}% of the {capacity:,}-seat {club.stadium} ({capacity_source})"
            if club is not None
            else "no home ground to sell"
        )
    price_pct = int(career.ticket_price_pct or TICKET_PRICE_NEUTRAL_PCT)
    demand_pct = demand_pct_for(price_pct)
    drawn = min(capacity, int(round(base * float(form["factor"]) * demand_pct / 100))) if capacity > 0 else 0
    season_seats = max(0, min(capacity, int(season_ticket_seats)))
    attendance = min(capacity, max(drawn, season_seats))
    source = (
        f"{source}; form {form['form']:.2f} over {form['played']} round(s) × {form['factor']:.2f}; "
        f"priced at {price_pct}% → demand {demand_pct}%"
        + (f"; {season_seats:,} season-ticket seats are not charged again" if season_seats else "")
    )
    ticket_price = GATE_TICKET_PRICE_TIER_1 if tier == 1 else GATE_TICKET_PRICE_TIER_2
    return capacity, attendance, ticket_price, source, form, price_pct, demand_pct, season_seats


def buy_seats(session: Session, career: Career, *, seats: int) -> tuple[CareerStadiumWork, dict[str, Any]]:
    """Buy more seats for the club's ground (M13 Phase 9 item 37).

    The only path that spends on the ground, so the rules live here: a retired career builds nothing, a
    challenge career owns no ground (its budget is an authored number), the size must be one purchase the
    club can actually make, and the price must fit the balance the market itself reads. The row stores the
    ground either side of the purchase and the `budget_after` it produced, so the timeline adds up.
    """
    if career.status != "active":
        raise MarketRefusal("career_retired", "this career is retired; take charge again before building")
    if career.challenge_slug:
        raise MarketRefusal(
            "challenge_budget",
            "a challenge's budget is an authored constraint printed when the run starts, so it owns no ground of its own",
        )
    wanted = int(seats)
    if wanted < STADIUM_MIN_SEATS or wanted > STADIUM_MAX_SEATS:
        raise MarketRefusal(
            "bad_seats",
            f"a stand is bought between {STADIUM_MIN_SEATS:,} and {STADIUM_MAX_SEATS:,} seats at a time",
            seats=wanted,
            min_seats=STADIUM_MIN_SEATS,
            max_seats=STADIUM_MAX_SEATS,
        )
    club = session.get(Team, career.club_id) if career.club_id else None
    if club is None:
        raise MarketRefusal("no_club", "this career has no club, so it has no ground to build on")
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    ground = ground_capacity(session, career, club, tier)
    price = wanted * STADIUM_SEAT_COST
    position = budget_position(session, career)
    if price > int(position["remaining"]):
        raise MarketRefusal(
            "insufficient_budget",
            f"{wanted:,} seats at {STADIUM_SEAT_COST} credits each is {price:,}, more than the "
            f"{int(position['remaining']):,} the balance can spend",
            price=price,
            balance=int(position["remaining"]),
            seats=wanted,
        )
    current = int(ground["stored"]) + int(ground["bought"])
    work = CareerStadiumWork(
        id=new_public_id("stad"),
        career_id=career.id,
        round_index=int(career.rounds_played) + 1,
        seats=wanted,
        unit_cost=STADIUM_SEAT_COST,
        amount=price,
        amount_units=career.budget_units,
        capacity_before=current,
        capacity_after=current + wanted,
        basis=(
            f"{wanted:,} seats x {STADIUM_SEAT_COST} {career.budget_units}/seat; {club.stadium} grows from "
            f"{current:,} to {current + wanted:,}"
        ),
        budget_after=int(position["remaining"]) - price,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(work)
    session.commit()
    session.refresh(work)
    return work, stadium_view(session, career)


def pay_gate_receipt(session: Session, career: Career, *, fixture: CareerFixture) -> CareerGateReceipt | None:
    """Pay one home round's gate and write the row that says so (M13 Phase 7 item 27).

    Called from `play_round` after the fixture is stored and before the wage charge, so the wage row's
    stored `budget_after` includes the gate the same round earned — the order the timeline reads.
    An away round earns nothing here: in this model the home club takes the gate. A home ground with no
    capacity, or a world fixture with no attendance, writes no row rather than a zero one.
    """
    if career.challenge_slug:
        # A challenge's budget is an authored constraint printed at the start, and its window pays no
        # season grant for the same reason: a gate would silently raise the figure the scenario stated.
        return None
    if str(fixture.side) != "home":
        return None
    club = session.get(Team, career.club_id) if career.club_id else None
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    season_index = closed_seasons(session, career) + 1
    season_seats = season_ticket_seats_for(session, career, season_index)
    _capacity, attendance, ticket_price, source, _form, price_pct, demand_pct, season_seats = _gate_terms(
        session,
        career,
        club=club,
        tier=tier,
        before_round=int(fixture.round_index),
        world_match_id=fixture.world_match_id,
        seed=int(fixture.seed),
        season_ticket_seats=season_seats,
    )
    paid_attendance = max(0, attendance - season_seats)
    amount = int(round(paid_attendance * ticket_price * price_pct / 100))
    if amount <= 0:
        return None
    balance = budget_position(session, career)
    receipt = CareerGateReceipt(
        id=new_public_id("gate"),
        career_id=career.id,
        round_index=int(fixture.round_index),
        fixture_id=fixture.id,
        attendance=attendance,
        ticket_price=ticket_price,
        price_pct=price_pct,
        demand_pct=demand_pct,
        season_ticket_seats=season_seats,
        amount=amount,
        amount_units=career.budget_units,
        basis=(
            f"{paid_attendance:,} paid seats × {ticket_price} {career.budget_units}/seat at {price_pct}% "
            f"({source}); {attendance:,} in the ground"
        ),
        budget_after=int(balance["remaining"]) + amount,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return receipt


def pay_cup_gate(session: Session, career: Career, *, tie: CareerCupTie) -> CareerGateReceipt | None:
    """Pay the gate a home cup tie earned (M13 Phase 9 item 34).

    The same arithmetic as a league home round — capacity with the tier factor, a deterministic share of
    the ground, the competition's ticket price, the stored form factor — with two rules of its own. Only
    the home side takes the gate, and a final is the competition's: a neutral venue pays the career
    nothing. The crowd is always built from capacity rather than the world's stored attendance, because
    the bracket row a later tie replaces was played by other clubs and its crowd is not this tie's.
    """
    if career.challenge_slug:
        return None
    if str(tie.side) != "home" or str(tie.stage) == "Final":
        return None
    club = session.get(Team, career.club_id) if career.club_id else None
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    _capacity, attendance, ticket_price, source, _form, price_pct, demand_pct, _season_seats = _gate_terms(
        session,
        career,
        club=club,
        tier=tier,
        # The tie is played *after* the round its index names, so that round's result is part of the form
        # the crowd responds to; a league round's gate is taken before the round it names.
        before_round=int(tie.round_index) + 1,
        world_match_id=None,
        seed=int(tie.seed),
        season_ticket_seats=0,
    )
    amount = int(round(attendance * ticket_price * price_pct / 100))
    if amount <= 0:
        return None
    balance = budget_position(session, career)
    receipt = CareerGateReceipt(
        id=new_public_id("gate"),
        career_id=career.id,
        round_index=int(tie.round_index),
        tie_id=tie.id,
        attendance=attendance,
        ticket_price=ticket_price,
        price_pct=price_pct,
        demand_pct=demand_pct,
        amount=amount,
        amount_units=career.budget_units,
        basis=(
            f"{attendance:,} seats × {ticket_price} {career.budget_units}/seat at {price_pct}% "
            f"({source}); "
            f"the {tie.cup_name} {tie.stage} at home"
        ),
        budget_after=int(balance["remaining"]) + amount,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return receipt


def pay_upkeep(
    session: Session,
    career: Career,
    *,
    fixture: CareerFixture | None = None,
    tie: CareerCupTie | None = None,
) -> CareerUpkeepCharge | None:
    """Charge one home round the running cost of the ground it opened (M13 Phase 10 item 45).

    Called immediately after the gate, so the gate's money is already in the balance this row leaves.
    Only a home league round or a home cup tie pays; an away round, a neutral-venue final and a
    challenge career pay nothing. The capacity is the physical ground — the club's stored seats plus
    every bought one — not the tier-adjusted figure the gate sells, because upkeep is about the stand,
    not about how many seats the league lets it sell.
    """
    if career.challenge_slug:
        return None
    if fixture is not None:
        if str(fixture.side) != "home":
            return None
        round_index = int(fixture.round_index)
        fixture_id: str | None = fixture.id
        tie_id: str | None = None
        where = f"round {round_index} at home"
    elif tie is not None:
        if str(tie.side) != "home" or str(tie.stage) == "Final":
            return None
        round_index = int(tie.round_index)
        fixture_id = None
        tie_id = tie.id
        where = f"the {tie.cup_name} {tie.stage} at home"
    else:
        raise ValueError("upkeep is charged on a league fixture or a cup tie")
    club = session.get(Team, career.club_id) if career.club_id else None
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    tier = int(competition.tier or 0) if competition is not None else 0
    capacity = int(ground_capacity(session, career, club, tier)["capacity"])
    amount = int(round(capacity * STADIUM_UPKEEP_PER_SEAT_PCT / 100))
    if amount <= 0:
        return None
    balance = budget_position(session, career)
    charge = CareerUpkeepCharge(
        id=new_public_id("upkeep"),
        career_id=career.id,
        round_index=round_index,
        fixture_id=fixture_id,
        tie_id=tie_id,
        capacity=capacity,
        seat_rate_pct=STADIUM_UPKEEP_PER_SEAT_PCT,
        amount=amount,
        amount_units=career.budget_units,
        basis=(
            f"{capacity:,} seats × {STADIUM_UPKEEP_PER_SEAT_PCT}% of a "
            f"{career.budget_units}/seat running rate ({where})"
        ),
        budget_after=int(balance["remaining"]) - amount,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(charge)
    session.commit()
    session.refresh(charge)
    return charge


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


def pay_season_grant(
    session: Session,
    career: Career,
    *,
    season_index: int,
    round_index: int,
    rounds_played: int,
    points: int,
    verdict: str,
) -> CareerBudgetAward | None:
    """Pay one closed season and write the row that says so.

    Called from `close_season` before that call's commit, so a career either has its boundary and its money
    or has neither. A grant of nothing writes no row: a season nobody played has nothing to pay for, and a
    challenge's window is judged by its own reward — both are `season_grant`'s arithmetic, not a second rule
    here, so the page that projects a grant and the boundary that pays one cannot disagree.
    """
    grant = season_grant(rounds=rounds_played, points=points, verdict=verdict, units=career.budget_units)
    if grant["amount"] <= 0:
        return None
    balance = budget_position(session, career)
    award = CareerBudgetAward(
        id=new_public_id("awd"),
        career_id=career.id,
        season_index=int(season_index),
        round_index=int(round_index),
        kind="season_grant",
        amount=int(grant["amount"]),
        amount_units=career.budget_units,
        basis=str(grant["basis"]),
        promotion=int(grant["promotion"]),
        budget_after=int(balance["remaining"]) + int(grant["amount"]),
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(award)
    return award


def pay_objective_bonuses(
    session: Session,
    career: Career,
    *,
    season_index: int,
    round_index: int,
    objectives: list[dict[str, Any]],
    verdict: str,
) -> list[CareerBudgetAward]:
    """Pay one row per objective a closed season met, in the boundary's own transaction (item 36).

    Called from `close_season` after the grant, so the boundary's money arrives as one run of rows in the
    round that ended the season. `stage` is the objective's kind, which is what `uq_career_award_stage`
    holds one row of per season; the rows are written in kind order and `budget_timeline` replays them the
    same way, so each stored `budget_after` is the running balance that order reproduces.
    """
    report = objective_bonus_report(objectives=objectives, verdict=verdict, units=career.budget_units)
    awards: list[CareerBudgetAward] = []
    for item in sorted(report["rows"], key=lambda row: str(row["kind"])):
        # The session runs with autoflush off, so the grant this boundary paid (and the previous bonus)
        # is still pending: flush before reading the balance, or the row would store a running figure
        # that omits its own predecessors and the timeline would count the disagreement.
        session.flush()
        balance = budget_position(session, career)
        award = CareerBudgetAward(
            id=new_public_id("awd"),
            career_id=career.id,
            season_index=int(season_index),
            round_index=int(round_index),
            kind="objective_bonus",
            stage=str(item["kind"])[:80],
            amount=int(item["amount"]),
            amount_units=career.budget_units,
            basis=str(item["basis"]),
            promotion=0,
            budget_after=int(balance["remaining"]) + int(item["amount"]),
            data_origin="simulation",
            is_demo_data=True,
        )
        session.add(award)
        awards.append(award)
    return awards


def pay_cup_prize(session: Session, career: Career, *, tie: CareerCupTie) -> CareerBudgetAward | None:
    """Pay one cup round this career won, and write the row into the award table (item 32).

    The prize is not a grant: the board did not judge the season, the cup paid for a round won. It still
    lives in `career_budget_awards`, because that is the table the balance arithmetic sums and a second
    income table would be a second arithmetic. `stage` names the cup and the round, so the same season can
    hold several prizes and a replay of one round cannot pay twice (`uq_career_award_stage`).
    """
    amount = int(CUP_PRIZE_BY_STAGE.get(int(tie.stage_index), 0))
    if amount <= 0:
        return None
    balance = budget_position(session, career)
    award = CareerBudgetAward(
        id=new_public_id("awd"),
        career_id=career.id,
        season_index=int(tie.season_index),
        round_index=int(tie.round_index),
        kind="cup_prize",
        stage=f"{tie.cup_slug}:{tie.stage}"[:80],
        amount=amount,
        amount_units=career.budget_units,
        basis=f"won the {tie.cup_name} {tie.stage}: {amount:,} {career.budget_units} for the round",
        promotion=0,
        budget_after=int(balance["remaining"]) + amount,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(award)
    session.commit()
    session.refresh(award)
    return award


def _require_wage_headroom(career: Career, balance: dict[str, Any], *, proposed_weekly_wage: int, player_name: str) -> None:
    """Refuse a deal that would take the weekly bill over the board's ceiling.

    `buy` and `loan` both call this after the affordability check, so the two doors cannot answer
    differently about the same cap. A career with no ceiling (`0`) passes; a bill exactly at the
    ceiling is within it.
    """
    ceiling = int(career.wage_ceiling)
    bill = int(balance["wage_committed_per_week"])
    if ceiling <= 0:
        return
    new_bill = bill + int(proposed_weekly_wage)
    if new_bill <= ceiling:
        return
    raise MarketRefusal(
        "wage_ceiling_exceeded",
        f"signing {player_name} would take the weekly wage bill to {new_bill:,} {career.budget_units}, over the board's {ceiling:,} ceiling",
        weekly_wage_bill=bill,
        proposed_weekly_wage=int(proposed_weekly_wage),
        new_weekly_wage_bill=new_bill,
        wage_ceiling=ceiling,
        wage_headroom=max(0, ceiling - bill),
        formula=WAGE_CEILING_FORMULA,
    )


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
    _require_wage_headroom(career, balance, proposed_weekly_wage=int(row.weekly_wage), player_name=row.player_name)
    player = session.get(RealPlayer, row.player_id)
    if player is None:
        raise MarketRefusal("player_gone", f"the row for {row.player_name} is no longer stored, so there is nobody to sign", listing_id=row.id)
    move = _record_move(
        session,
        career,
        player,
        kind="buy",
        fee=fee,
        round_index=int(career.rounds_played) + 1,
        balance=balance,
        listing=row,
        age_offset=closed_seasons(session, career),
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
    _require_wage_headroom(career, balance, proposed_weekly_wage=int(row.weekly_wage), player_name=row.player_name)
    player = session.get(RealPlayer, row.player_id)
    if player is None:
        raise MarketRefusal("player_gone", f"the row for {row.player_name} is no longer stored, so there is nobody to loan", listing_id=row.id)
    until = round_index + rounds - 1
    move = _record_move(
        session,
        career,
        player,
        kind="loan",
        fee=fee,
        round_index=round_index,
        balance=balance,
        listing=row,
        loan_until=until,
        age_offset=closed_seasons(session, career),
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
    age_offset = closed_seasons(session, career)
    price = valuation(player, age=int(player.age) + age_offset)
    fee = _credits(int(price["asking_fee"]) * SELL_PROCEEDS_SHARE)
    counterparty = session.scalars(select(Team).where(Team.competition_id == (career.competition_id or ""), Team.id != (career.club_id or "")).order_by(Team.overall.desc(), Team.slug)).first()
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
        age_offset=age_offset,
    )
    for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.player_id == player.id, TransferListing.status == "open")):
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
    age_offset = closed_seasons(session, career)
    move = _record_move(
        session,
        career,
        player,
        kind="release",
        fee=0,
        round_index=int(career.rounds_played) + 1,
        balance=budget_position(session, career),
        age_offset=age_offset,
    )
    for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.player_id == player.id, TransferListing.status == "open")):
        row.status = "withdrawn"
    session.commit()
    session.refresh(move)
    return move, {"fee_formula": RELEASE_FORMULA}


def renew(
    session: Session,
    career: Career,
    *,
    ident: str,
    years: int | None = None,
    wage: int | None = None,
) -> tuple[CareerSquadMove, dict[str, Any]]:
    """Extend one deal this career already holds, at the terms the contract book quotes.

    A renewal is not a transfer: it does not need an open signing window, because the player is already
    this career's and the deal being changed is its own. It is still an arithmetic deal, so it is refused
    when the renewal fee is more than the balance or when the bill after replacing the old wage would
    exceed the board's ceiling. The new expiry is computed here, once, from the season length in force,
    and stored on the row exactly as a signing's is.
    """
    if career.status != "active":
        raise MarketRefusal("career_retired", "this career is retired; its squad is closed", constraint="career_status")
    player, _squad, _account = _outgoing(session, career, ident)
    round_index = int(career.rounds_played) + 1
    held = held_deals(session, career.id, round_index)
    move = next((row for row in held if row.player_id == player.id), None)
    if move is None:
        raise MarketRefusal(
            "no_contract_to_renew",
            f"{player.name} is in this career's squad but no deal of its own is on the book to renew",
            player_id=player.id,
            player_name=player.name,
        )
    kind = effective_kind(move, round_index)
    if kind in ("loan", "loan_out"):
        raise MarketRefusal(
            "loan_cannot_be_renewed",
            f"{player.name} is on a loan; a loan's last round is agreed with the other club and is not renewed here",
            player_id=player.id,
            kind=kind,
            loan_until_round=int(move.loan_until_round or 0),
        )
    if kind not in ("buy", "youth", "renew"):
        raise MarketRefusal(
            "no_permanent_deal_to_renew",
            f"{player.name}'s latest deal is {kind}, which this career cannot renew here",
            player_id=player.id,
            kind=kind,
        )
    terms = renewal_terms(session, career, player, years=years)
    price = terms["valuation"]
    seasons = int(terms["years"])
    if seasons < 1 or seasons > 5:
        raise MarketRefusal("invalid_renewal_years", "a renewal is between 1 and 5 seasons", years=seasons)
    from app.services.simulation.career import season_horizon

    season_rounds = int(season_horizon(session, career)["rounds"])
    if season_rounds <= 0:
        raise MarketRefusal("no_season_horizon", "this career has no season length, so a renewal has no last round", career_slug=career.slug)
    fee = int(terms["fee"])
    balance = budget_position(session, career)
    if int(balance["remaining"]) < fee:
        raise MarketRefusal(
            "insufficient_budget",
            f"the renewal fee is {fee:,} {career.budget_units} and the balance is {int(balance['remaining']):,}",
            fee=fee,
            remaining=int(balance["remaining"]),
            units=career.budget_units,
        )
    demand = int(terms["demand_wage"])
    if wage is not None and int(wage) < demand:
        raise MarketRefusal(
            "renewal_refused",
            f"{player.name} asks {demand:,} {career.budget_units} a week for {seasons} season(s); the offer was {int(wage):,}",
            demanded_wage=demand,
            offered_wage=int(wage),
            years=seasons,
            minutes_share=terms["minutes_share"],
            tier_factor=terms["tier_factor"],
            minutes_factor=terms["minutes_factor"],
            formula=RENEWAL_FORMULA,
        )
    new_wage = int(wage) if wage is not None else demand
    standing = wage_bill(session, career, round_index=round_index, held=held)
    new_bill = int(standing["fee"]) - int(move.weekly_wage) + new_wage
    ceiling = int(career.wage_ceiling or 0)
    if ceiling > 0 and new_bill > ceiling:
        raise MarketRefusal(
            "wage_ceiling_exceeded",
            f"the bill after this renewal would be {new_bill:,} against a ceiling of {ceiling:,}",
            wage_bill_before=int(standing["fee"]),
            proposed_weekly_wage=new_wage,
            wage_bill_after=new_bill,
            wage_ceiling=ceiling,
            headroom=ceiling - int(standing["fee"]),
        )
    expiry = round_index + seasons * season_rounds - 1
    row = _record_move(
        session,
        career,
        player,
        kind="renew",
        fee=fee,
        round_index=round_index,
        balance=balance,
        contract_years=seasons,
        expiry_round=expiry,
        age_offset=closed_seasons(session, career),
        weekly_wage=new_wage,
    )
    session.commit()
    session.refresh(row)
    return row, {
        "fee_formula": RENEWAL_FORMULA,
        "valuation": price,
        "previous": {
            "contract_years": int(move.contract_years),
            "weekly_wage": int(move.weekly_wage),
            "expiry_round": int(move.expiry_round or 0),
        },
        "expiry_round": expiry,
        "demand_wage": demand,
        "offered_wage": int(wage) if wage is not None else demand,
        "minutes_share": terms["minutes_share"],
        "tier_factor": terms["tier_factor"],
        "minutes_factor": terms["minutes_factor"],
        "fee_per_year": int(terms["fee_per_year"]),
        "wage_bill_after": new_bill,
    }


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


def squad_rows(squad: list[RealPlayer], *, age_offset: int = 0) -> list[dict[str, Any]]:
    """The squad as a page reads it: who is here, what the market would list them at, what a sale brings."""
    rows: list[dict[str, Any]] = []
    for player in squad:
        age = int(player.age) + max(0, int(age_offset))
        price = valuation(player, age=age)
        rows.append(
            {
                "player_id": player.id,
                "slug": player.slug,
                "name": player.name,
                "position": player.position,
                "band": band_of_position(player.position),
                "age": age,
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
        # What this offer would do to the balance and the wage runway, from the same arithmetic the
        # affordability block publishes: `fee_affordable` here is exactly `affordable` above, the runway
        # is the balance after the fee against the bill the signing would add, and `wage_affordable`
        # answers the board's hard cap on that bill.
        "signing": signing_impact(
            int(standing["remaining"]),
            int(standing["wage_committed_per_week"]),
            price=price,
            proposed_weekly_wage=int(row.weekly_wage),
            wage_ceiling=int(career.wage_ceiling),
        ),
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
        # The stored last round a permanent deal's own terms name, so the ledger row and the deal book
        # cannot disagree about it. A loan's end is `loan_until_round`; this one is zero for it.
        "expiry_round": int(row.expiry_round or 0),
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


def award_row(award: CareerBudgetAward) -> dict[str, Any]:
    """A board grant in the ledger's own shape, so one table prints money in as well as out.

    A grant buys nobody, so the row names the boundary that paid it rather than a player. `season_index`
    and `promotion` travel with it because the `basis` string only reads as arithmetic once a reader can
    see which season and which verdict produced it.
    """
    kind = str(award.kind)
    if kind == "cup_prize":
        name = f"cup prize, {award.stage}"
    elif kind == "objective_bonus":
        name = f"objective bonus, {award.stage}"
    else:
        name = f"board grant for season {int(award.season_index)}"
    return {
        "id": award.id,
        "round_index": int(award.round_index),
        "kind": award.kind,
        "side": "in",
        "cash": "in",
        "player_id": "",
        "player_slug": "",
        "player_name": name,
        "player_path": None,
        "position": "",
        "fee": int(award.amount),
        "fee_units": award.amount_units,
        "contract_years": 0,
        "weekly_wage": 0,
        "loan_until_round": 0,
        "counterparty_name": "",
        "budget_after": int(award.budget_after),
        "effect": CUP_PRIZE_EFFECT if kind == "cup_prize" else OBJECTIVE_BONUS_EFFECT if kind == "objective_bonus" else AWARD_EFFECT,
        "detail": award.basis,
        "season_index": int(award.season_index),
        "stage": award.stage,
        "promotion": int(award.promotion),
        "created_at": award.created_at.isoformat() if award.created_at else None,
        "data_origin": award.data_origin,
        "is_demo_data": award.is_demo_data,
    }


def gate_row(receipt: CareerGateReceipt) -> dict[str, Any]:
    """A home gate in the ledger's own shape: money in, no player, and the attendance it was paid on."""
    cup = bool(receipt.tie_id)
    return {
        "id": receipt.id,
        "round_index": int(receipt.round_index),
        "tie_id": receipt.tie_id,
        "competition": "cup" if cup else "league",
        "kind": "gate",
        "side": "in",
        "cash": "in",
        "player_id": "",
        "player_slug": "",
        "player_name": f"{'cup ' if cup else ''}gate receipts, {int(receipt.attendance):,} seats",
        "player_path": None,
        "position": "",
        "fee": int(receipt.amount),
        "fee_units": receipt.amount_units,
        "contract_years": 0,
        "weekly_wage": 0,
        "loan_until_round": 0,
        "expiry_round": 0,
        "counterparty_name": "",
        "budget_after": int(receipt.budget_after),
        "effect": GATE_EFFECT,
        "detail": receipt.basis,
        "attendance": int(receipt.attendance),
        "ticket_price": int(receipt.ticket_price),
        "price_pct": int(receipt.price_pct),
        "demand_pct": int(receipt.demand_pct),
        "season_ticket_seats": int(receipt.season_ticket_seats),
        "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
        "data_origin": receipt.data_origin,
        "is_demo_data": receipt.is_demo_data,
    }


def upkeep_ledger_row(charge: CareerUpkeepCharge) -> dict[str, Any]:
    """One ground cost in the ledger's own shape: money out, no player, and the seats that cost it."""
    cup = bool(charge.tie_id)
    return {
        "id": charge.id,
        "round_index": int(charge.round_index),
        "kind": "cup_upkeep" if cup else "upkeep",
        "side": "out",
        "cash": "out",
        "player_id": "",
        "player_slug": "",
        "player_name": f"{'cup ' if cup else ''}ground upkeep, {int(charge.capacity):,} seats",
        "player_path": None,
        "position": "",
        "fee": int(charge.amount),
        "fee_units": charge.amount_units,
        "contract_years": 0,
        "weekly_wage": 0,
        "loan_until_round": 0,
        "expiry_round": 0,
        "counterparty_name": "",
        "budget_after": int(charge.budget_after),
        "effect": UPKEEP_EFFECT,
        "detail": charge.basis,
        "capacity": int(charge.capacity),
        "seat_rate_pct": int(charge.seat_rate_pct),
        "created_at": charge.created_at.isoformat() if charge.created_at else None,
        "data_origin": charge.data_origin,
        "is_demo_data": charge.is_demo_data,
    }


def ledger_of(
    moves: list[dict[str, Any]],
    charges: list[dict[str, Any]],
    awards: list[dict[str, Any]] | None = None,
    receipts: list[dict[str, Any]] | None = None,
    stadium: list[dict[str, Any]] | None = None,
    upkeep: list[dict[str, Any]] | None = None,
    season_tickets: list[dict[str, Any]] | None = None,
    training: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The money tables as one ledger, in the order a reader has to add them up.

    Within a round a career's moves come before its gate and its wage charge: the moves were made before
    the fixture, the gate was earned by it and the charge was written after it, so the running total only
    matches each row's stored `budget_after` in that order. Ordering by timestamp alone is not enough —
    two rows written in the same instant tie, and the tie-break by id is arbitrary, which made the
    ledger's total disagree with a stored `budget_after` depending on how fast the rows were written. A
    boundary's grant comes after all three, because it is paid for the rounds already played and charged.
    """
    return sorted(
        [
            *moves,
            *charges,
            *(awards or []),
            *(receipts or []),
            *(stadium or []),
            *(upkeep or []),
            *(season_tickets or []),
            *(training or []),
        ],
        key=lambda entry: (
            int(entry["round_index"]),
            _ledger_tier(str(entry.get("kind", ""))),
            _ledger_order(str(entry.get("kind", "")), entry),
            str(entry["created_at"] or ""),
            str(entry["id"]),
        ),
    )


def _ledger_order(kind: str, entry: dict[str, Any]) -> str:
    """Where a row sits among the rows of its own tier, when the tier alone does not order them.

    A boundary's grant and the objective bonuses it paid share tier 3; the grant is written first and the
    bonuses in objective-kind order, which is what the stage stores. Ids are random tokens, so without this
    the running total would depend on how fast the rows were written.
    """
    return str(entry.get("stage", "")) if kind == "objective_bonus" else ""


def _ledger_tier(kind: str) -> int:
    """Where a ledger row sits inside its round: moves, gate, wage, the boundary's money, then a cup tie's.

    A cup gate and a cup prize are written after the round they were played after, so they cannot share
    the league gate's slot without the running total disagreeing with the stored `budget_after`.
    """
    if kind in ("cup_gate", "cup_prize", "cup_upkeep"):
        return 4
    if kind in AWARD_KINDS:
        return 3
    if kind == "wage":
        return 2
    if kind in ("gate", "upkeep"):
        return 1
    return 0


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
    awards = awards_of(session, career.id)
    grants = [row for row in awards if str(row.kind) == "season_grant"]
    prizes = [row for row in awards if str(row.kind) == "cup_prize"]
    bonuses = [row for row in awards if str(row.kind) == "objective_bonus"]
    receipts = receipts_as_of(session, career.id, round_index)
    works = stadium_works_of(session, career.id)
    upkeep = upkeep_as_of(session, career.id, round_index)
    season_tickets = [
        row for row in season_tickets_of(session, career.id) if int(row.round_index) <= round_index
    ]
    training = training_works_of(session, career.id)
    move_rows = [move_row(row) for row in rows]
    wage_rows = [wage_row(row) for row in charges]
    grant_rows = [award_row(row) for row in awards]
    gate_rows = [gate_row(row) for row in receipts]
    stadium_rows = [stadium_ledger_row(row) for row in works]
    upkeep_rows = [upkeep_ledger_row(row) for row in upkeep]
    season_ticket_rows = [season_ticket_ledger_row(row) for row in season_tickets]
    training_rows = [training_ledger_row(row) for row in training]
    squad, account = current_squad(session, career)
    balance = budget_position(
        session,
        career,
        moves=rows,
        charges=charges,
        awards=awards,
        receipts=receipts,
        works=works,
        upkeep=upkeep,
        season_tickets=season_tickets,
        training=training,
    )
    open_rows = [row for row in listings if row.status == "open"]
    window = transfer_window(session, career)
    verdict = transferable(session, career)
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
        "transfers_allowed": verdict,
        "window": window,
        "market": {
            "round_index": round_index,
            "opened": bool(listings),
            "size": MARKET_SIZE,
            "note": "the offers below are this career's own market; a career that has never opened one sees no rows and an empty `listings`",
        },
        "need": need,
        "budget": balance,
        "stadium": stadium_view(session, career),
        "tickets": ticket_price_view(session, career),
        "squad": {
            "account": account,
            "players": squad_rows(squad, age_offset=closed_seasons(session, career)),
            "fielding": can_field_side(squad),
        },
        "listings": [listing_row(session, career, row, balance) for row in open_rows],
        "deals": [listing_row(session, career, row, balance) for row in listings if row.status == "signed"],
        "moves": ledger_of(
            move_rows, wage_rows, grant_rows, gate_rows, stadium_rows, upkeep_rows, season_ticket_rows,
            training_rows,
        ),
        "totals": {
            "listed": len(open_rows),
            "signed": sum(1 for row in listings if row.status == "signed"),
            "withdrawn": sum(1 for row in listings if row.status == "withdrawn"),
            "moves": len(rows),
            "wage_rows": len(charges),
            "grant_rows": len(grants),
            "cup_prize_rows": len(prizes),
            "bonus_rows": len(bonuses),
            "gate_rows": len(receipts),
            "stadium_rows": len(works),
        },
        "rules": RULES,
        "constants": {
            "market_size": MARKET_SIZE,
            "early_window_last_round": EARLY_WINDOW_LAST_ROUND,
            "mid_window_half_width": MID_WINDOW_HALF_WIDTH,
            "negotiation_rounds": MAX_NEGOTIATION_ROUNDS,
            "negotiation_floor_share": NEGOTIATION_FLOOR_SHARE,
            "gate_ticket_price_tier_1": GATE_TICKET_PRICE_TIER_1,
            "gate_ticket_price_tier_2": GATE_TICKET_PRICE_TIER_2,
            "ticket_price_min_pct": TICKET_PRICE_MIN_PCT,
            "ticket_price_max_pct": TICKET_PRICE_MAX_PCT,
            "ticket_price_step_pct": TICKET_PRICE_STEP_PCT,
            "ticket_price_neutral_pct": TICKET_PRICE_NEUTRAL_PCT,
            "gate_rotation_attendance_floor": GATE_ROTATION_ATTENDANCE_FLOOR,
            "gate_rotation_attendance_ceiling": GATE_ROTATION_ATTENDANCE_CEILING,
            "release_clause_share": RELEASE_CLAUSE_SHARE,
            "loan_fee_share": LOAN_FEE_SHARE,
            "sell_proceeds_share": SELL_PROCEEDS_SHARE,
            "default_loan_rounds": DEFAULT_LOAN_ROUNDS,
            "season_grant_per_round": SEASON_GRANT_PER_ROUND,
            "season_grant_per_point": SEASON_GRANT_PER_POINT,
            "promotion_grant": PROMOTION_GRANT,
            "stadium_seat_cost": STADIUM_SEAT_COST,
            "stadium_min_seats": STADIUM_MIN_SEATS,
            "stadium_max_seats": STADIUM_MAX_SEATS,
            "stadium_upkeep_per_seat_pct": STADIUM_UPKEEP_PER_SEAT_PCT,
            "season_ticket_discount_pct": SEASON_TICKET_DISCOUNT_PCT,
            "season_ticket_min_seats": SEASON_TICKET_MIN_SEATS,
            "season_ticket_max_share_pct": SEASON_TICKET_MAX_SHARE_PCT,
            "training_max_level": TRAINING_MAX_LEVEL,
            "training_level_bonus_pct": TRAINING_LEVEL_BONUS_PCT,
            "training_upgrade_base_cost": TRAINING_UPGRADE_BASE_COST,
            "cup_prize_by_stage": {str(stage): amount for stage, amount in sorted(CUP_PRIZE_BY_STAGE.items())},
            "objective_bonus_by_kind": {kind: amount for kind, amount in sorted(OBJECTIVE_BONUS_BY_KIND.items())},
            "age_curve": [{"ages": f"{low}-{high}", "weight": weight} for low, high, weight in AGE_CURVE],
        },
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": MARKET_DISCLAIMER,
    }


__all__ = [
    "AFFORDABILITY_FORMULA",
    "AWARD_EFFECT",
    "AWARD_KINDS",
    "BUDGET_AWARD_FORMULA",
    "BUDGET_FORMULA",
    "CONTRACT_FORMULA",
    "CUP_PRIZE_BY_STAGE",
    "CUP_PRIZE_FORMULA",
    "EARLY_WINDOW_LAST_ROUND",
    "EXPIRY_KIND",
    "EXPIRY_WARNING_ROUNDS",
    "FIT_FORMULA",
    "MARKET_DISCLAIMER",
    "MARKET_SIZE",
    "MAX_NEGOTIATION_ROUNDS",
    "MID_WINDOW_HALF_WIDTH",
    "MOVE_EFFECT",
    "CONFLICT_CODES",
    "MarketRefusal",
    "NEGOTIATION_FORMULA",
    "NOT_FOUND_CODES",
    "OBJECTIVE_BONUS_BY_KIND",
    "OBJECTIVE_BONUS_FORMULA",
    "PROMOTION_GRANT",
    "RENEWAL_KIND",
    "RENEWAL_FEE_SHARE",
    "RENEWAL_FORMULA",
    "RENEWAL_SEASONS",
    "RETIREMENT_AGE",
    "RULES",
    "SEASON_GRANT_PER_POINT",
    "SEASON_GRANT_PER_ROUND",
    "SEASON_TICKET_DISCOUNT_PCT",
    "SEASON_TICKET_FORMULA",
    "SEASON_TICKET_MAX_SHARE_PCT",
    "SEASON_TICKET_MIN_SEATS",
    "SELL_FORMULA",
    "STADIUM_EFFECT",
    "STADIUM_FORMULA",
    "STADIUM_MAX_SEATS",
    "STADIUM_MIN_SEATS",
    "STADIUM_SEAT_COST",
    "STADIUM_UPKEEP_FORMULA",
    "STADIUM_UPKEEP_PER_SEAT_PCT",
    "TICKET_PRICE_FORMULA",
    "TRAINING_EFFECT",
    "TRAINING_FORMULA",
    "TRAINING_UPGRADE_BASE_COST",
    "TICKET_PRICE_MAX_PCT",
    "TICKET_PRICE_MIN_PCT",
    "TICKET_PRICE_NEUTRAL_PCT",
    "TICKET_PRICE_STEP_PCT",
    "TIMELINE_FORMULA",
    "UNPROCESSABLE_CODES",
    "VALUATION_FORMULA",
    "WAGE_CEILING_FORMULA",
    "WAGE_FORMULA",
    "WINDOW_FORMULA",
    "affordability_view",
    "age_curve",
    "award_row",
    "awards_as_of",
    "awards_of",
    "budget_position",
    "budget_timeline",
    "buy",
    "buy_seats",
    "buy_season_tickets",
    "club_need",
    "contract_book",
    "contract_expiry_round",
    "demand_pct_for",
    "expire_contracts",
    "held_deals",
    "ledger_of",
    "listing_row",
    "loan",
    "market_pool",
    "market_selection",
    "market_view",
    "move_row",
    "negotiate",
    "objective_bonus_report",
    "open_market",
    "pay_cup_prize",
    "pay_objective_bonuses",
    "pay_season_grant",
    "pay_wages",
    "release",
    "renew",
    "season_grant",
    "season_ticket_ledger_row",
    "season_ticket_row",
    "season_ticket_seats_for",
    "season_ticket_view",
    "season_tickets_of",
    "sell",
    "season_windows",
    "signing_impact",
    "set_ticket_price",
    "squad_rows",
    "stadium_ledger_row",
    "stadium_row",
    "stadium_seats",
    "stadium_view",
    "stadium_works_of",
    "upkeep_as_of",
    "upkeep_ledger_row",
    "ground_capacity",
    "gate_capacity_for",
    "pay_upkeep",
    "tactical_fit",
    "ticket_price_view",
    "transfer_window",
    "transferable",
    "valuation",
    "wage_bill",
    "wage_headroom",
    "wage_row",
    "wage_runway",
    "wages_as_of",
]
