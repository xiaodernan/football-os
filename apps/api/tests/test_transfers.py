"""M6 §22 transfer market, the service layer: a price from stored rows, a ledger that adds up, an eleven that changes.

Three claims carry this module, and each is tested where it is made:

* **The arithmetic is the product.** Every fee, clause, wage, loan cost and sale proceeds is the number
  the published formula prints, recomputed here from the player's stored row — if the code and the
  sentence ever disagree, one of these tests goes red rather than the reader finding out.
* **The budget is a sum of rows.** A balance is `career.budget` plus what the ledger brought in minus
  what it took out — the four squad-move kinds and one wage charge per round played — and each row stores
  the standing at its own point in the history.
* **A deal reaches the engine.** A signed or released player changes the eleven `team_profile` selects,
  the round played after it is decided by that eleven, and a replay rebuilds the squad *as of that
  round* — so a later deal must never rewrite an older match.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import BUDGET_FORMULA, MOVE_EFFECT, WAGE_EFFECT, Career, CareerSquadMove, CareerWageCharge, RealPlayer, Team, TransferListing, User
from app.services.simulation import career as career_service
from app.services.simulation import market
from app.services.simulation import squad as squad_service
from app.services.simulation.challenges import challenge_by_slug, resolve_challenge_club, start_run
from app.services.simulation.profile import BAND_ATTRIBUTES, BANDS, band_index, band_of_position, team_profile
from app.services.simulation.service import replay_is_identical, run_simulation
from app.services.world import sync_world

BUDGET = 4_000_000
RULE_KEYS = {"valuation", "need", "tactical_fit", "negotiation", "release_clause", "loan", "sell", "release", "wages", "budget", "squad"}


def _round5(value: float) -> int:
    """The rounding the published formulas promise, written out again on purpose."""
    return int(round(value / 5) * 5)


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """The weakest club in the world, the clubs in its competition, and one outside it.

    The weakest club is chosen deliberately: a test that a market's best player enters the eleven could
    otherwise pass without the overlay ever being applied, because an above-average club would have kept
    its own striker. The fixture pins the premise instead of trusting it.
    """
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).order_by(Team.overall, Team.slug).limit(1)).one()
    rivals = list(session.scalars(select(Team).where(Team.competition_id == club.competition_id, Team.id != club.id).order_by(Team.slug)).all())
    outsiders = list(session.scalars(select(Team).where(Team.competition_id != club.competition_id, Team.competition_id.is_not(None)).order_by(Team.slug)).all())
    owner = User(
        id=new_public_id("usr"),
        email=f"market-{club.slug[:8]}@example.test",
        password_hash=hash_password("market-service-test"),
        display_name="Market Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {
        "club_id": club.id,
        "club_name": club.name,
        "rival_ids": [team.id for team in rivals],
        "outsider_id": outsiders[0].id,
        "owner_id": owner.id,
    }
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _career(session: Session, world: dict[str, Any], **kwargs: Any) -> Career:
    return career_service.create_career(
        session,
        owner_id=world["owner_id"],
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name=kwargs.pop("manager_name", "Market Manager"),
        philosophy=kwargs.pop("philosophy", "balanced"),
        system_slug=kwargs.pop("system_slug", ""),
        budget=kwargs.pop("budget", BUDGET),
        objectives=kwargs.pop("objectives", [{"kind": "wins", "target": 1, "label": "win once"}]),
        season="2026",
    )


def _players_of(session: Session, team_id: str) -> list[RealPlayer]:
    return list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == team_id).order_by(RealPlayer.slug)).all())


def _best_of(session: Session, team_ids: list[str], *, band: str) -> RealPlayer:
    rows = [player for team_id in team_ids for player in _players_of(session, team_id) if band_of_position(player.position) == band]
    assert rows, f"no club offered a player in the {band} band"
    return max(rows, key=lambda player: (player.overall, player.potential))


def _club_best(session: Session, club_id: str, *, band: str) -> int:
    return max((player.overall for player in _players_of(session, club_id) if band_of_position(player.position) == band), default=0)


def _listed(session: Session, career: Career, player: RealPlayer) -> TransferListing:
    """A listing for one named player, priced the way `open_market` prices one.

    Used where the test is about a *rule* (a rival will not sell, a clause moves them, a signing enters
    the eleven) rather than about who the market happened to select: the offer has to be a particular
    club's player, and the selection is not allowed to be the thing under test.
    """
    price = market.valuation(player)
    # One row per (career, player) is a database constraint, not a convention: if this career's market
    # already lists the player, the offer on file is the offer to trade against.
    row = session.scalar(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.player_id == player.id))
    if row is not None:
        return row
    row = TransferListing(
        id=new_public_id("tl"),
        career_id=career.id,
        player_id=player.id,
        player_slug=player.slug,
        player_name=player.name,
        position=player.position,
        age=player.age,
        overall=player.overall,
        potential=player.potential,
        from_team_id=player.team_id,
        from_team_name=str(session.scalar(select(Team.name).where(Team.id == player.team_id)) or ""),
        asking_fee=price["asking_fee"],
        current_price=price["asking_fee"],
        release_clause=price["release_clause"],
        contract_years=price["contract_years"],
        weekly_wage=price["weekly_wage"],
        tactical_fit=market.tactical_fit(player, "attack")["fit"],
        needed_band="attack",
        status="open",
        listed_round=1,
        negotiations=0,
        last_offer=0,
    )
    session.add(row)
    session.commit()
    return row


def _sign(session: Session, world: dict[str, Any], career: Career, *, band: str = "attack", rounds: int | None = None) -> RealPlayer:
    """Buy (or loan) the world's best player in one band, and hand back the row that arrived."""
    player = _best_of(session, world["rival_ids"] + [world["outsider_id"]], band=band)
    assert player.overall > _club_best(session, career.club_id or "", band=band), "the fixture club is no longer the weakest, so a signing may not enter its eleven"
    listing = _listed(session, career, player)
    if rounds is None:
        market.buy(session, career, ident=listing.id, use_clause=True)
    else:
        market.loan(session, career, ident=listing.id, rounds=rounds)
    return player


def _fixture_pair(session: Session, career: Career) -> tuple[str, str, int, str]:
    """The home, the away, the seed and the side the career's next round would be played on."""
    plan = career_service.next_fixture_plan(session, career)
    home, away = (career.club_id or "", str(plan["opponent_team_id"])) if plan["side"] == "home" else (str(plan["opponent_team_id"]), career.club_id or "")
    return home, away, int(plan["seed"]), str(plan["side"])


class TestValuation:
    def test_a_price_is_the_arithmetic_the_page_prints(self, session, world) -> None:  # type: ignore[no-untyped-def]
        for player in _players_of(session, world["club_id"])[:5]:
            price = market.valuation(player)
            expected = _round5(((player.overall - 40) * 45_000 + max(0, player.potential - player.overall) * 25_000) * market.age_curve(player.age))
            assert price["asking_fee"] == expected, (player.name, player.overall, player.potential, player.age)
            assert price["release_clause"] == _round5(expected * 1.5)
            assert price["weekly_wage"] == max(5, _round5(expected / 500))
            assert price["quality_points"] == player.overall - 40
            assert price["formula"] == market.VALUATION_FORMULA

    def test_the_age_curve_is_the_published_step_function(self) -> None:  # type: ignore[no-untyped-def]
        assert [market.age_curve(age) for age in (18, 22, 25, 30, 35)] == [0.60, 0.90, 1.00, 0.75, 0.45]
        assert market.age_curve(26) == max(weight for _, _, weight in market.AGE_CURVE), "the peak years are the whole curve's ceiling"
        assert market.age_curve(12) == 0.30, "an age the bands do not cover is named rather than silently defaulted to the peak"

    def test_the_same_player_is_cheaper_at_33_than_at_25(self) -> None:  # type: ignore[no-untyped-def]
        rows = (
            RealPlayer(id="p1", name="Peak", slug="peak-one", position="ST", age=25, overall=60, potential=70, team_id="t1", attributes={}),
            RealPlayer(id="p2", name="Veteran", slug="veteran-one", position="ST", age=33, overall=60, potential=70, team_id="t1", attributes={}),
        )
        peak, veteran = (market.valuation(row)["asking_fee"] for row in rows)
        assert peak > veteran == _round5(peak * 0.45)

    def test_a_contract_shortens_past_the_peak_and_never_exceeds_five_years(self) -> None:  # type: ignore[no-untyped-def]
        lengths = {
            age: market.valuation(RealPlayer(id=f"p{age}", name="x", slug=f"x{age}", position="CM", age=age, overall=55, potential=60, team_id="t", attributes={}))["contract_years"]
            for age in (18, 27, 31, 40)
        }
        assert [lengths[18], lengths[27], lengths[31]] == [5, 5, 1]
        assert lengths[40] == 1, "the clamp is written into the formula, so the floor is the contract's floor too"

    def test_tactical_fit_is_the_same_measurement_the_engine_reports(self, session, world) -> None:  # type: ignore[no-untyped-def]
        player = _best_of(session, [world["club_id"]], band="attack")
        band = band_of_position(player.position)
        fit = market.tactical_fit(player, band)
        assert fit["band"] == band and fit["fills_need"] is True
        assert fit["band_index"] == round(band_index([player], band), 3), "fit reuses the engine's band index instead of inventing a second scale"
        assert fit["fit"] == round(0.5 * fit["band_index"] + 0.5, 3)
        elsewhere = market.tactical_fit(player, "keeper")
        assert elsewhere["fills_need"] is False and abs(fit["fit"] - elsewhere["fit"] - 0.5) < 1e-9, "the same player is worth half a fit more where the club is short"


class TestOpeningTheMarket:
    def test_the_offers_come_from_the_world_and_never_from_your_own_club(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        report = market.open_market(session, career)
        rows = list(session.scalars(select(TransferListing).where(TransferListing.career_id == career.id)).all())
        assert report["created"] == len(rows) == report["size"] == market.MARKET_SIZE
        assert {row.from_team_id for row in rows} <= set(session.scalars(select(Team.id)).all()) - {career.club_id}
        assert career.club_id not in {row.from_team_id for row in rows}, "a career cannot buy a player it already has"
        assert len({row.player_id for row in rows}) == len(rows), "a player cannot be offered twice"
        assert all(row.status == "open" and row.listed_round == 1 for row in rows)

    def test_each_offer_is_priced_from_the_row_behind_it(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.open_market(session, career)
        for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id)):
            player = session.get(RealPlayer, row.player_id)
            price = market.valuation(player)
            assert (row.asking_fee, row.current_price, row.release_clause, row.weekly_wage) == (price["asking_fee"], price["asking_fee"], price["release_clause"], price["weekly_wage"])
            assert (row.overall, row.potential, row.age, row.position, row.player_slug) == (player.overall, player.potential, player.age, player.position, player.slug)
            assert row.from_team_name == str(session.scalar(select(Team.name).where(Team.id == player.team_id)))

    def test_the_same_squad_offers_the_same_market(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """No draw anywhere: the twelve are a function of the world's rows and this career's squad."""
        first, second = _career(session, world), _career(session, world)
        market.open_market(session, first)
        market.open_market(session, second)

        def offered(career: Career) -> list[str]:
            return [row.player_slug for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id).order_by(TransferListing.player_slug)).all()]

        assert offered(first) == offered(second)

    def test_the_band_the_club_is_weakest_in_is_filled_first(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        report = market.open_market(session, career)
        profile = team_profile(session, career.club_id or "")
        bands = {"attack": profile.attack, "defence": profile.defence, "keeper": profile.keeper, "midfield": profile.midfield}
        needed = min(sorted(bands), key=lambda band: bands[band])
        view = market.market_view(session, career)
        assert view["need"]["needed_band"] == needed == report["band_order"][0]
        assert report["taken_per_band"][needed] == market.MARKET_SIZE // len(BANDS)
        assert view["need"]["positions_in_band"] == list(BANDS[needed]) and view["need"]["judged_on"] == list(BAND_ATTRIBUTES[needed])
        assert view["need"]["squad_applied"] == "" and view["need"]["formula"] == market.NEED_FORMULA
        assert {row["band"] for row in view["listings"]} == set(BANDS), "every band is offered for, weakest first"

    def test_relisting_reprices_a_discount_and_drops_a_bought_player_from_the_shelf(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.open_market(session, career)
        rows = list(session.scalars(select(TransferListing).where(TransferListing.career_id == career.id).order_by(TransferListing.player_slug)).all())
        discounted, bought = rows[0], rows[1]
        market.negotiate(session, career, ident=discounted.id, offer=_round5(discounted.asking_fee * 0.81))
        assert discounted.current_price < discounted.asking_fee
        market.buy(session, career, ident=bought.id, use_clause=True)
        report = market.open_market(session, career)
        assert report["created"] >= 1 and report["created"] + report["repriced"] == market.MARKET_SIZE, "the vacated slot is filled, so a round always opens on a full dozen"
        assert report["kept_signed"] == 0, "a permanently bought player left the pool, so there is no signed row left for the shelf to offer"
        session.refresh(discounted)
        assert discounted.current_price == discounted.asking_fee, "a negotiated discount does not survive a re-list"
        assert bought.status == "signed" and bought.current_price == bought.asking_fee, "a closed deal is not re-priced as if it were still an offer"
        open_ids = {row.player_id for row in session.scalars(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.status == "open")).all()}
        assert bought.player_id not in open_ids, "the player you own is not on sale to you"

    def test_a_loan_that_has_expired_is_offered_again_at_its_own_price(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The one route to `kept_signed`: a returning loanee is back in the pool while his row still says signed.

        A re-list must not re-price a deal that already happened. The row is skipped and counted, so the
        report says plainly that the dozen below is a dozen minus him.
        """
        career = _career(session, world)
        market.open_market(session, career)
        # The market is a function of the squad, so the highest-rated player in a band is selected again
        # once he returns to the pool — that is what makes the skip below provable rather than lucky.
        pool, _ = market.market_pool(session, career, round_index=1)
        ranked = sorted((player for player in pool if band_of_position(player.position) == "attack"), key=lambda player: (-player.overall, -player.potential, player.slug))
        returnee = _listed(session, career, ranked[0])
        move, detail = market.loan(session, career, ident=returnee.id, rounds=1)
        assert move.loan_until_round == 1 and "rounds 1 to 1" in detail["covers"]
        career_service.play_round(session, career)
        price_before = returnee.current_price
        report = market.open_market(session, career)
        assert report["round_index"] == 2 and report["kept_signed"] == 1
        assert report["created"] + report["repriced"] == market.MARKET_SIZE - 1, "the returned loanee holds his slot without being re-listed"
        session.refresh(returnee)
        assert returnee.status == "signed" and returnee.current_price == price_before
        state = squad_service.squad_state(session, career, 2)
        assert state[returnee.player_id] == "loan_out", "the loan covers the round it was struck for and no further"

    def test_a_career_that_has_not_opened_a_market_reads_as_empty_not_as_broken(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = market.market_view(session, career)
        assert view["market"]["opened"] is False and view["listings"] == [] and view["moves"] == []
        assert view["market"]["size"] == market.MARKET_SIZE and "never opened one" in view["market"]["note"]
        assert view["budget"]["moves"] == 0 and view["budget"]["remaining"] == BUDGET
        assert view["squad"]["account"]["signed_in"] == 0 and view["squad"]["fielding"]["ok"] is True


class TestLedger:
    def test_the_balance_is_the_sum_of_the_ledger(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        _sign(session, world, career, band="attack")
        career_service.play_round(session, career)
        _sign(session, world, career, band="midfield", rounds=2)
        career_service.play_round(session, career)
        market.sell(session, career, ident=_players_of(session, career.club_id or "")[0].id)
        market.release(session, career, ident=_players_of(session, career.club_id or "")[1].id)

        rows = list(session.scalars(select(CareerSquadMove).where(CareerSquadMove.career_id == career.id).order_by(CareerSquadMove.round_index, CareerSquadMove.created_at)).all())
        charges = list(session.scalars(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id).order_by(CareerWageCharge.round_index)).all())
        assert sorted(row.kind for row in rows) == ["buy", "loan", "release", "sell"]
        assert [row.round_index for row in charges] == [1, 2], "one charge per round played, in the round it was for"
        # The reader's arithmetic: one column, one sign per row, and each row's stored standing has to be
        # what the running total says at that point. This is the whole reason `budget_after` is stored.
        ledger = market.ledger_of([market.move_row(row) for row in rows], [market.wage_row(row) for row in charges])
        standing = BUDGET
        for entry in ledger:
            standing = standing - entry["fee"] if entry["cash"] == "out" else standing + entry["fee"]
            assert entry["budget_after"] == standing, "each row stores the standing it left behind, in the order the ledger is read"
        position = market.budget_position(session, career)
        assert position["remaining"] == standing
        assert position["spent"] == sum(row.fee for row in rows if row.kind in ("buy", "loan")) > 0
        assert position["received"] == sum(row.fee for row in rows if row.kind == "sell") > 0
        assert position["wages_paid"] == sum(row.fee for row in charges) > 0
        assert position["budget"] + position["received"] - position["spent"] - position["wages_paid"] == position["remaining"]
        assert position["formula"] == BUDGET_FORMULA and "wage_charges" in BUDGET_FORMULA
        assert position["units"] == career.budget_units

    def test_a_deal_the_balance_cannot_cover_refuses_with_its_numbers(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world, budget=0)
        market.open_market(session, career)
        listing = next(iter(session.scalars(select(TransferListing).where(TransferListing.career_id == career.id))))
        with pytest.raises(market.MarketRefusal) as refused:
            market.buy(session, career, ident=listing.id, use_clause=True)
        assert refused.value.code == "insufficient_budget"
        assert refused.value.detail["fee"] == listing.release_clause > 0
        assert refused.value.detail["remaining"] == 0
        assert refused.value.to_dict()["formula"] == BUDGET_FORMULA
        assert session.scalar(select(CareerSquadMove.id).where(CareerSquadMove.career_id == career.id)) is None, "a refusal writes no history"
        session.refresh(listing)
        assert listing.status == "open"

    def test_selling_pays_ninety_percent_to_the_best_club_in_the_competition(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        own = _players_of(session, career.club_id or "")[0]
        move, detail = market.sell(session, career, ident=own.id)
        assert move.fee == _round5(market.valuation(own)["asking_fee"] * 0.9) > 0
        assert move.kind == "sell" and move.budget_after == BUDGET + move.fee
        buyer = session.get(Team, move.counterparty_team_id or "")
        assert buyer is not None and buyer.id != career.club_id and buyer.competition_id == career.competition_id
        assert buyer.name == detail["buyer"] and detail["proceeds_formula"] == market.SELL_FORMULA
        assert move.counterparty_name == buyer.name
        assert move.weekly_wage > 0 and 1 <= move.contract_years <= 5, "a deal stores the contract terms it was struck on"


class TestWageBill:
    """§22's *Contract* verb, charged: every round a career plays costs it what its deals agreed.

    The claim these tests exist to hold is narrow and expensive: a wage that is only recorded is a rate
    nobody pays, so the budget a manager reads would be a starting figure rather than a balance. Each
    played round writes one `career_wage_charges` row, and the ledger the page adds up is both tables.
    """

    def test_a_round_with_no_deal_of_this_career_own_writes_no_charge(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        assert session.scalar(select(CareerWageCharge.id).where(CareerWageCharge.career_id == career.id)) is None, (
            "the club's own stored squad came with the job; only deals this career made are charged"
        )
        position = market.budget_position(session, career)
        assert position["remaining"] == BUDGET and position["wages_paid"] == 0 and position["wage_committed_per_week"] == 0
        assert position["wage_rounds"] == [] and position["wage_rows"] == 0

    def test_the_round_a_deal_is_struck_for_is_the_round_it_starts_costing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        player = _best_of(session, [world["outsider_id"]], band="midfield")
        listing = _listed(session, career, player)
        move, _ = market.buy(session, career, ident=listing.id)
        wage = market.valuation(player)["weekly_wage"]
        assert move.weekly_wage == wage, "the deal stores the wage the valuation printed"
        standing = market.budget_position(session, career)
        assert standing["wage_committed_per_week"] == wage and standing["wage_players"] == 1, "the rate is published before it is ever charged"
        assert standing["wages_paid"] == 0 and standing["remaining"] == BUDGET - move.fee, "agreeing a wage does not spend it; playing the round does"
        career_service.play_round(session, career)
        charge = session.scalar(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id))
        assert charge is not None and charge.round_index == 1 and charge.fee == wage and charge.players == 1
        assert charge.fee == standing["wage_committed_per_week"], "the row charged exactly the rate the page had printed"
        after = market.budget_position(session, career)
        assert after["remaining"] == BUDGET - move.fee - wage and after["wages_paid"] == wage and after["wage_rounds"] == [1]
        assert charge.budget_after == after["remaining"]

    def test_a_sold_player_stops_costing_and_a_loan_stops_when_its_rounds_do(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        signed = _best_of(session, [world["outsider_id"]], band="midfield")
        rental = _best_of(session, [world["outsider_id"]], band="attack")
        bought = market.buy(session, career, ident=_listed(session, career, signed).id)[0]
        loaned = market.loan(session, career, ident=_listed(session, career, rental).id, rounds=1)[0]
        assert bought.weekly_wage > 0 and loaned.weekly_wage > 0
        career_service.play_round(session, career)
        first = session.scalar(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id, CareerWageCharge.round_index == 1))
        assert first is not None and first.fee == bought.weekly_wage + loaned.weekly_wage and first.players == 2
        career_service.play_round(session, career)
        second = session.scalar(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id, CareerWageCharge.round_index == 2))
        assert second is not None and second.fee == bought.weekly_wage, "the loan covered one round, and its wage with it — no row was written to end it"
        market.sell(session, career, ident=signed.id)
        career_service.play_round(session, career)
        rounds = [int(row.round_index) for row in session.scalars(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id)).all()]
        assert rounds == [1, 2], "a career holding nothing of its own is charged nothing and writes no row"

    def test_a_charge_names_every_player_it_was_raised_on(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        midfield = _best_of(session, [world["outsider_id"]], band="midfield")
        attack = _best_of(session, [world["outsider_id"]], band="attack")
        market.buy(session, career, ident=_listed(session, career, midfield).id)
        market.buy(session, career, ident=_listed(session, career, attack).id)
        career_service.play_round(session, career)
        charge = session.scalar(select(CareerWageCharge).where(CareerWageCharge.career_id == career.id))
        assert charge is not None and charge.players == 2
        parts = [part.rsplit(" ", 1) for part in charge.detail.split(" · ")]
        assert sorted(name for name, _ in parts) == sorted([midfield.name, attack.name]), "the row says who, not merely how much"
        assert sum(int(value.replace(",", "")) for _, value in parts) == charge.fee, "the names add up to the fee the balance lost"

    def test_the_wage_bill_is_what_makes_the_next_offer_unaffordable(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.open_market(session, career)
        rows = market.market_view(session, career)["listings"]
        first, second = rows[0], rows[1]
        # Budgeted to one credit short of two deals, with a wage in between: the only thing that can tip
        # the second offer from buyable to refused is the round the first deal costs.
        career.budget = first["price_to_pay"] + first["weekly_wage"] + second["price_to_pay"] - 5
        session.commit()
        market.buy(session, career, ident=first["id"], use_clause=first["clause_required"])
        before = market.market_view(session, career)
        assert next(row for row in before["listings"] if row["id"] == second["id"])["affordable"] is True
        career_service.play_round(session, career)
        after = market.market_view(session, career)
        target = next(row for row in after["listings"] if row["id"] == second["id"])
        assert after["budget"]["wages_paid"] == first["weekly_wage"]
        assert target["affordable"] is False, "affordability is judged on the balance the rounds have already cost"
        with pytest.raises(market.MarketRefusal) as refused:
            market.buy(session, career, ident=second["id"], use_clause=target["clause_required"])
        assert refused.value.code == "insufficient_budget"
        assert refused.value.detail["remaining"] == after["budget"]["remaining"] == second["price_to_pay"] - 5


class TestDeals:
    def test_signing_a_player_spends_the_asked_price_and_closes_the_offer(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        outsider = _best_of(session, [world["outsider_id"]], band="midfield")
        listing = _listed(session, career, outsider)
        price = listing.current_price
        move, detail = market.buy(session, career, ident=listing.id)
        assert detail == {"rival": False, "clause_used": False, "paid_from": "current_price"}
        assert (move.kind, move.fee, move.player_id, move.round_index) == ("buy", price, outsider.id, 1)
        assert move.budget_after == BUDGET - price and move.position == outsider.position
        session.refresh(listing)
        assert listing.status == "signed"
        with pytest.raises(market.MarketRefusal) as again:
            market.buy(session, career, ident=listing.id)
        assert again.value.code == "not_on_sale"

    def test_a_rival_will_not_sell_to_a_rival_and_the_clause_is_the_way_in(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        rival_player = _best_of(session, world["rival_ids"], band="attack")
        listing = _listed(session, career, rival_player)
        with pytest.raises(market.MarketRefusal) as refused:
            market.buy(session, career, ident=listing.id)
        assert refused.value.code == "rival_will_not_sell"
        assert refused.value.detail["release_clause"] == listing.release_clause
        assert refused.value.detail["current_price"] == listing.current_price < listing.release_clause
        assert refused.value.to_dict()["formula"] == market.RIVAL_FORMULA
        move, detail = market.buy(session, career, ident=listing.id, use_clause=True)
        assert detail == {"rival": True, "clause_used": True, "paid_from": "release_clause"}
        assert move.fee == listing.release_clause and move.budget_after == BUDGET - move.fee

    def test_a_loan_is_a_temporary_deal_the_seller_agrees_to_so_no_clause_binds(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        rival_player = _best_of(session, world["rival_ids"], band="defence")
        listing = _listed(session, career, rival_player)
        move, detail = market.loan(session, career, ident=listing.id, rounds=2)
        assert move.kind == "loan" and move.fee == max(5, _round5(listing.current_price * 0.15)) < listing.current_price
        assert (move.round_index, move.loan_until_round) == (1, 2) and detail["covers"] == "rounds 1 to 2 inclusive"

        def signed_in(round_index: int) -> bool:
            overlay = squad_service.squad_as_of(session, career, round_index)
            return overlay is not None and any(player.id == rival_player.id for player in overlay.added)

        assert signed_in(1) and signed_in(2)
        assert not signed_in(3), "the loan expired by the rule, not by rewriting history"
        session.refresh(move)
        assert move.kind == "loan", "the row still says what was agreed at the time"
        assert squad_service.effective_kind(move, 3) == "loan_out"

    def test_negotiation_walks_the_ladder_the_response_prints(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        listing = _listed(session, career, _best_of(session, [world["outsider_id"]], band="attack"))
        floor = _round5(listing.asking_fee * 0.8)
        low = market.negotiate(session, career, ident=listing.id, offer=floor - 1)
        assert low["outcome"] == "rejected" and low["price"] == listing.asking_fee and low["floor"] == floor
        countered = market.negotiate(session, career, ident=listing.id, offer=floor + 20_000)
        assert countered["outcome"] == "countered"
        assert countered["price"] == max(floor, _round5((listing.asking_fee + floor + 20_000) / 2)) < listing.asking_fee
        assert countered["attempts"] == 2 and countered["attempts_left"] == 1
        session.refresh(listing)
        accepted = market.negotiate(session, career, ident=listing.id, offer=listing.current_price + 999_999)
        assert accepted["outcome"] == "accepted" and accepted["price"] == listing.current_price
        with pytest.raises(market.MarketRefusal) as closed:
            market.negotiate(session, career, ident=listing.id, offer=floor + 1)
        assert closed.value.code == "negotiation_closed"
        assert closed.value.detail["attempts"] == market.MAX_NEGOTIATION_ROUNDS
        assert closed.value.to_dict()["formula"] == market.NEGOTIATION_FORMULA

    def test_a_side_cannot_be_sold_out_of_being_fieldable(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        squad = _players_of(session, career.club_id or "")
        keeper = next(player for player in squad if player.position == "GK")
        outfield = [player for player in squad if player.position != "GK"]
        assert len(squad) == 15 and len(outfield) == 13
        for player in outfield[:4]:
            market.release(session, career, ident=player.id)
        assert market.budget_position(session, career)["remaining"] == BUDGET, "releasing pays nothing and costs nothing"
        with pytest.raises(market.MarketRefusal) as refused:
            market.sell(session, career, ident=keeper.id)
        assert refused.value.code == "would_not_field_a_side"
        assert refused.value.detail["players"] == 10 and refused.value.detail["needs_players"] == squad_service.MIN_PLAYERS_FOR_XI
        assert refused.value.detail["keepers"] == 1 and refused.value.detail["needs_keepers"] == squad_service.MIN_KEEPERS
        assert "11 players" in refused.value.detail["rule"]
        assert squad_service.can_field_side(_players_of(session, career.club_id or ""))["ok"] is True

    def test_a_retired_career_a_closed_window_and_a_no_transfer_scenario_each_refuse(self, session, world) -> None:  # type: ignore[no-untyped-def]
        retired = _career(session, world)
        retired.status = "retired"
        session.commit()
        assert market.transferable(session, retired)["code"] == "career_retired"

        out_of_window = _career(session, world)
        out_of_window.challenge_window = 3
        out_of_window.rounds_played = 3
        session.commit()
        verdict = market.transferable(session, out_of_window)
        assert verdict["code"] == "window_closed" and verdict["rounds_played"] == verdict["window_rounds"] == 3

        scenario = challenge_by_slug("no-transfer-challenge")
        assert scenario is not None and any(constraint.key == "no_transfers" for constraint in scenario.constraints)
        club, _account = resolve_challenge_club(session, scenario, club=world["club_id"])
        run = start_run(session, scenario, owner_id=world["owner_id"], club=club, manager_name="As You Were", system_slug="", season="2026")
        forbidden = market.transferable(session, run)
        assert forbidden["code"] == "transfers_forbidden" and forbidden["constraint"] == "no_transfers"
        assert forbidden["enforced"] is True and "market.transferable" in forbidden["enforced_by"]
        with pytest.raises(market.MarketRefusal) as refused:
            market.loan(session, run, ident="anything")
        assert refused.value.code == "transfers_forbidden"
        with pytest.raises(market.MarketRefusal) as also_refused:
            market.sell(session, run, ident=_players_of(session, world["club_id"])[0].id)
        assert also_refused.value.code == "transfers_forbidden"

    def test_an_unknown_offer_and_someone_elses_player_are_named_refusals(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        with pytest.raises(market.MarketRefusal) as refused:
            market.buy(session, career, ident="nobody-was-listed")
        assert refused.value.code == "no_such_listing" and refused.value.detail["career_slug"] == career.slug
        with pytest.raises(market.MarketRefusal) as foreign:
            market.sell(session, career, ident=_players_of(session, world["outsider_id"])[0].id)
        assert foreign.value.code == "not_your_player"
        assert foreign.value.detail["squad_size"] == 15 and foreign.value.detail["as_of_round"] == 1


class TestSquadReachesTheEngine:
    def test_a_career_that_never_used_the_market_has_no_overlay_at_all(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        assert squad_service.squad_as_of(session, career, 1) is None
        plain = team_profile(session, career.club_id or "").to_dict()
        composed = team_profile(session, career.club_id or "", squad=squad_service.squad_as_of(session, career, 1)).to_dict()
        assert plain["lineup"] == composed["lineup"] and composed["squad_label"] == ""
        side = _fixture_pair(session, career)[3]
        _fixture, match = career_service.play_round(session, career)
        assert match.report["sides"][side]["squad_label"] == "", "a career that never used the market plays the club the world generated, and says so"

    def test_a_signing_that_outranks_the_clubs_own_players_joins_the_eleven(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = team_profile(session, career.club_id or "")
        player = _sign(session, world, career, band="attack")
        overlay = squad_service.squad_as_of(session, career, 1)
        assert overlay is not None and career.slug in overlay.label and "1 signed in" in overlay.label
        after = team_profile(session, career.club_id or "", squad=overlay)
        assert player.name in [entry[0] for entry in after.lineup], "a player signed for more than anyone the club holds must be selected"
        assert after.squad_label == overlay.label and after.lineup != before.lineup

    def test_a_release_takes_a_selected_player_out_of_the_eleven(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        best_outfield = max((player for player in _players_of(session, career.club_id or "") if player.position != "GK"), key=lambda player: (player.overall, player.slug))
        assert best_outfield.name in [entry[0] for entry in team_profile(session, career.club_id or "").lineup]
        market.release(session, career, ident=best_outfield.id)
        overlay = squad_service.squad_as_of(session, career, 1)
        assert overlay is not None and best_outfield.id in overlay.removed and "1 departed" in overlay.label
        after = team_profile(session, career.club_id or "", squad=overlay)
        assert best_outfield.name not in [entry[0] for entry in after.lineup]

    def test_a_buy_then_sell_cancels_for_the_eleven_and_neither_row_is_edited(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        player = _sign(session, world, career, band="midfield")
        assert squad_service.squad_state(session, career, 1)[player.id] == "buy"
        career_service.play_round(session, career)
        market.sell(session, career, ident=player.id)
        assert squad_service.squad_state(session, career, 2)[player.id] == "sell"
        composed = squad_service.squad_as_of(session, career, 2)
        assert composed is not None and composed.empty and composed.label == "", "in and out by round 2 leaves the club's own squad rows"
        assert composed.carries_load, "but the played round is carried: the same eleven comes into round 2 with load on it"
        rows = list(session.scalars(select(CareerSquadMove).where(CareerSquadMove.career_id == career.id).order_by(CareerSquadMove.round_index)).all())
        assert [row.kind for row in rows] == ["buy", "sell"] and [row.round_index for row in rows] == [1, 2]
        squad, _account = squad_service.current_squad(session, career)
        assert player.id not in {row.id for row in squad} and len(squad) == 15
        overlay = squad_service.squad_as_of(session, career, 1)
        assert overlay is not None and any(row.id == player.id for row in overlay.added), "round 1 still replays with the player who was signed for it"

    def test_a_round_is_played_by_the_eleven_the_market_created(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        home_id, away_id, seed, side = _fixture_pair(session, career)
        player = _sign(session, world, career, band="attack")
        fixture, match = career_service.play_round(session, career)
        report_side = match.report["sides"][side]
        assert report_side["squad_label"].startswith(f"{career.slug} squad as of round 1")
        assert player.name in [entry["player"] for entry in report_side["lineup"]], "the report names the eleven the deal created"
        untouched = run_simulation(session, owner_id=career.owner_id, home_team_id=home_id, away_team_id=away_id, seed=seed)
        assert untouched.digest != match.digest, "the same seed on the same fixture plays a different match once the squad changed"
        assert (fixture.digest, fixture.seed, fixture.round_index) == (match.digest, seed, 1)

    def test_a_replay_rebuilds_the_squad_as_of_that_round_and_a_later_deal_cannot_touch_it(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        _sign(session, world, career, band="attack")
        _fixture, opening_round = career_service.play_round(session, career)
        replay = replay_is_identical(session, opening_round)
        assert replay["possible"] is True and replay["identical"] is True
        assert "1 signed in" in replay["squad"]["applied"] and replay["squad"]["round_index"] == 1

        _sign(session, world, career, band="defence", rounds=3)
        again = replay_is_identical(session, opening_round)
        assert again["identical"] is True and "1 signed in" in again["squad"]["applied"], "round 1 must still replay as the eleven that played it"
        _fixture, second_round = career_service.play_round(session, career)
        later = replay_is_identical(session, second_round)
        assert later["identical"] is True and "2 signed in" in later["squad"]["applied"] and later["squad"]["round_index"] == 2

    def test_a_match_no_recorded_move_explains_still_replays_clean(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        _fixture, match = career_service.play_round(session, career)
        replay = replay_is_identical(session, match)
        assert replay["possible"] is True and replay["identical"] is True
        assert "no squad move before round 1" in replay["squad"]["note"]

    def test_a_ledger_that_no_longer_reproduces_an_eleven_refuses_rather_than_blaming_the_engine(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """A stored report that names an eleven the rows cannot rebuild is reported, not re-derived.

        The move row is deleted here on purpose: this is the shape of a career whose ledger was edited
        underneath a match. Replaying the *club's* squad and calling a different digest an engine fault
        would be a lie about the model, so the answer is `possible: false` and the reason.
        """
        career = _career(session, world)
        side = _fixture_pair(session, career)[3]
        _sign(session, world, career, band="attack")
        _fixture, match = career_service.play_round(session, career)
        for move in session.scalars(select(CareerSquadMove).where(CareerSquadMove.career_id == career.id)).all():
            session.delete(move)
        session.commit()
        replay = replay_is_identical(session, match)
        assert replay["possible"] is False and "no longer the eleven this match picked" in replay["reason"]
        assert replay["reason"].startswith(f"the {side} side's"), "the refusal names the side whose eleven cannot be rebuilt"
        assert "no squad move before round 1" in replay["squad"]["note"]
        assert replay["model_version"] == match.model_version


class TestMarketView:
    def test_the_view_prints_the_rules_it_was_built_on(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.open_market(session, career)
        view = market.market_view(session, career)
        assert set(view["rules"]) == RULE_KEYS and view["rules"]["budget"] == BUDGET_FORMULA
        assert view["constants"]["market_size"] == market.MARKET_SIZE and len(view["constants"]["age_curve"]) == len(market.AGE_CURVE)
        assert view["constants"]["release_clause_share"] == 1.5 and view["constants"]["sell_proceeds_share"] == 0.9
        assert view["data_origin"] == "simulation" and view["is_demo_data"] is True and view["demo_data"] is True
        assert "generated clubs" in view["disclaimer"]
        assert view["career"]["slug"] == career.slug and view["career"]["market_round"] == 1
        assert view["transfers_allowed"]["ok"] is True
        assert view["totals"] == {"listed": market.MARKET_SIZE, "signed": 0, "withdrawn": 0, "moves": 0, "wage_rows": 0}

    def test_an_offer_says_what_it_costs_who_must_be_paid_and_whether_you_can(self, session, world) -> None:  # type: ignore[no-untyped-def]
        poor = _career(session, world, budget=5_000)
        market.open_market(session, poor)
        rows = market.market_view(session, poor)["listings"]
        assert len(rows) == market.MARKET_SIZE
        assert all(row["affordable"] is False for row in rows), "a career with 5,000 credits cannot afford the world's best players"
        assert all(row["price_to_pay"] == (row["release_clause"] if row["rival"] else row["current_price"]) for row in rows)
        assert all(row["clause_required"] == row["rival"] for row in rows)
        assert all(row["attempts_left"] == market.MAX_NEGOTIATION_ROUNDS and row["status"] == "open" for row in rows)
        assert all(row["player_path"] == f"/player/{row['player_slug']}" for row in rows)
        rich = _career(session, world)
        market.open_market(session, rich)
        assert all(row["affordable"] is True for row in market.market_view(session, rich)["listings"])

    def test_a_move_row_carries_the_effect_the_model_promises(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.release(session, career, ident=_players_of(session, career.club_id or "")[0].id)
        row = market.move_row(next(iter(session.scalars(select(CareerSquadMove).where(CareerSquadMove.career_id == career.id)))))
        assert row["kind"] == "release" and row["side"] == "out" and row["fee"] == 0
        assert row["effect"] == MOVE_EFFECT["release"] and row["budget_after"] == BUDGET
        assert set(row) >= {"round_index", "player_slug", "contract_years", "weekly_wage", "counterparty_name", "data_origin", "is_demo_data"}
        assert row["data_origin"] == "simulation" and row["is_demo_data"] is True

    def test_the_career_layer_says_what_the_market_still_does_not_do(self) -> None:  # type: ignore[no-untyped-def]
        limits = career_service.limitations()
        assert set(limits) == {"budget", "wages", "carry_over", "scouting", "philosophy", "table", "objectives"}
        assert "spent, not stated" in limits["budget"] and "/api/v1/transfers" in limits["budget"]
        assert "career_wage_charges" in limits["wages"] and "not charged is the club's own" in limits["wages"]
        assert "no default" in limits["wages"], "the wage bill's own limit is named rather than left out"
        assert "AI Scout" in limits["scouting"] and "not built" in limits["scouting"]
