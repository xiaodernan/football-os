"""M6 §22 transfer market over HTTP: public arithmetic, private deals, and a squad the match report admits to.

The wall is the one every other slice of user state stands behind (spec §61): the *rules* of the market
are public fiction — anyone may read how a price is made — while a career's offers, deals and ledger
belong to the account that opened it, and a foreign slug is a 404 rather than a 403.

What the wire has to prove, beyond the service layer's arithmetic:

* reading never reprices: `GET` is a read, and only `POST /market` moves a price;
* a refusal answers 409 with the figures behind it and 404 with the codes that mean "that is not a thing";
* the market's decisions reach the match: the round played after a signing reports the squad it used.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import BUDGET_FORMULA, Career, Team
from app.services.simulation.market import MARKET_SIZE, MAX_NEGOTIATION_ROUNDS, RULES
from app.services.world import sync_world

API = "/api/v1/transfers"
CAREERS = "/api/v1/careers"
PASSWORD = "strong-pass-1234"
BUDGET = 4_000_000


@pytest.fixture(scope="module")
def club_id() -> str:
    """The weakest club in the generated world: the one whose eleven a market signing certainly joins."""
    session = SessionLocal()
    sync_world(session)
    ident = str(session.scalars(select(Team.id).order_by(Team.overall, Team.slug).limit(1)).one())
    session.close()
    return ident


@contextmanager
def _signed_in() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as other:
        response = other.post(
            "/api/v1/auth/register",
            json={"email": f"rival-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Other Manager", "role": "player", "accepts_data_policy": True},
        )
        assert response.status_code == 201, response.text
        other.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        yield other


def _career(auth_client: TestClient, club: str, **kwargs: Any) -> str:
    response = auth_client.post(
        CAREERS,
        json={
            "club": club,
            "manager_name": "Market Manager",
            "philosophy": "balanced",
            "budget": kwargs.pop("budget", BUDGET),
            "objectives": [{"kind": "wins", "target": 1, "label": "win once"}],
            **kwargs,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["career"]["slug"])


def _opened(auth_client: TestClient, slug: str) -> dict[str, Any]:
    response = auth_client.post(f"{API}/{slug}/market")
    assert response.status_code == 200, response.text
    return dict(response.json())


class TestPublicRules:
    def test_the_arithmetic_is_public(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/rules", headers={"Authorization": ""})
        assert response.status_code == 200
        body = response.json()
        assert set(body["rules"]) == set(RULES) and body["rules"]["budget"] == BUDGET_FORMULA
        assert set(body["move_effects"]) == {"buy", "loan", "sell", "release"}
        assert body["data_origin"] == "simulation" and body["is_demo_data"] is True and "generated clubs" in body["disclaimer"]

    def test_a_careers_market_needs_an_account(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/anything").status_code == 401
        assert client.post(f"{API}/anything/market").status_code == 401
        assert client.post(f"{API}/anything/buy", json={"listing": "x"}).status_code == 401


class TestOwnership:
    def test_another_account_sees_no_market_and_cannot_trade_in_it(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        _opened(auth_client, slug)
        with _signed_in() as other:
            for method, path, payload in (
                ("get", f"{API}/{slug}", None),
                ("post", f"{API}/{slug}/market", None),
                ("post", f"{API}/{slug}/buy", {"listing": "anything"}),
                ("post", f"{API}/{slug}/sell", {"player": "anything"}),
                ("post", f"{API}/{slug}/release", {"player": "anything"}),
                ("post", f"{API}/{slug}/loan", {"listing": "anything"}),
                ("post", f"{API}/{slug}/negotiate", {"listing": "anything", "offer": 1}),
            ):
                response = other.request(method.upper(), path, json=payload)
                assert response.status_code == 404, f"{method!r} {path!r} answered {response.status_code!r}, 404 was required"
                assert response.json()["detail"]["code"] == "not_found"

    def test_an_unknown_career_is_a_404_on_every_door(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        assert auth_client.get(f"{API}/no-such-career").json()["detail"]["code"] == "not_found"
        assert auth_client.post(f"{API}/no-such-career/market").status_code == 404


class TestReadingAndOpening:
    def test_a_career_that_never_opened_a_market_reads_as_empty(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        body = auth_client.get(f"{API}/{slug}").json()
        assert body["market"]["opened"] is False and body["listings"] == [] and body["moves"] == []
        assert body["budget"]["remaining"] == BUDGET and body["budget"]["formula"] == BUDGET_FORMULA
        assert body["transfers_allowed"]["ok"] is True
        assert body["squad"]["account"]["squad_now"] == 15 and body["squad"]["fielding"]["ok"] is True
        assert body["need"]["needed_band"] in {"attack", "midfield", "defence", "keeper"}
        assert body["is_demo_data"] is True and "generated clubs" in body["disclaimer"]

    def test_opening_a_market_lists_the_worlds_best_and_prices_them(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        body = _opened(auth_client, slug)
        assert body["opened"] is True and body["listing_report"]["created"] == MARKET_SIZE
        assert len(body["listings"]) == MARKET_SIZE
        row = body["listings"][0]
        assert {"asking_fee", "current_price", "release_clause", "weekly_wage", "tactical_fit", "player_path"} <= set(row)
        assert row["release_clause"] > row["asking_fee"] > 0 and row["status"] == "open"
        assert all(listing["from_team_id"] != body["career"]["club_id"] for listing in body["listings"])
        assert body["constants"]["market_size"] == MARKET_SIZE

    def test_a_get_never_reprices_and_only_opening_the_market_does(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        listing_id = _opened(auth_client, slug)["listings"][0]["id"]
        discounted = auth_client.post(f"{API}/{slug}/negotiate", json={"listing": listing_id, "offer": 1}).json()
        asking = next(row for row in discounted["listings"] if row["id"] == listing_id)
        assert asking["negotiations"] == 1 and asking["attempts_left"] == MAX_NEGOTIATION_ROUNDS - 1
        for _ in range(3):
            read = auth_client.get(f"{API}/{slug}").json()
            row = next(item for item in read["listings"] if item["id"] == listing_id)
            assert row["current_price"] == asking["current_price"], "loading the page must not move a price"
        reopened = _opened(auth_client, slug)
        row = next((item for item in reopened["listings"] if item["id"] == listing_id), None)
        assert row is None or row["current_price"] == row["asking_fee"], "a re-list starts the round at the valuation"

    def test_negotiating_the_ladder_over_the_wire_reports_the_floor_it_used(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        listing_id = _opened(auth_client, slug)["listings"][0]["id"]
        result = auth_client.post(f"{API}/{slug}/negotiate", json={"listing": listing_id, "offer": 1}).json()["result"]
        assert result["outcome"] == "rejected" and result["price"] == result["asking"]
        assert result["floor"] == int(round(result["asking"] * 0.8 / 5) * 5), "the floor is the published rounding of 80% of the asking fee"
        assert "round_5(asking × 0.8)" in result["formula"]
        assert result["data_origin"] == "simulation" and result["is_demo_data"] is True


class TestTheSeasonWindow:
    """§22's window over the wire: the page prints where the career stands, and a closed window refuses at the door."""

    def test_a_closed_window_is_named_by_the_read_and_refuses_the_post(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        body = auth_client.get(f"{API}/{slug}").json()
        assert body["window"]["state"] == "open" and body["transfers_allowed"]["ok"] is True
        assert body["window"]["round_in_season"] == 1 and body["window"]["windows"], "an open market still publishes its round ranges"
        last_open = int(body["window"]["windows"][-1]["to_round"])
        session = SessionLocal()
        career = session.scalar(select(Career).where(Career.slug == slug))
        assert career is not None
        career.rounds_played = last_open
        session.commit()
        session.close()
        body = auth_client.get(f"{API}/{slug}").json()
        assert body["window"]["state"] == "closed" and body["window"]["opens_at_round"] == 1
        assert body["transfers_allowed"]["code"] == "transfer_window_closed"
        refused = auth_client.post(f"{API}/{slug}/market")
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "transfer_window_closed"
        detail = refused.json()["detail"]
        assert detail["round_in_season"] == last_open + 1 and detail["opens_in_rounds"] == int(body["window"]["season_rounds"]) - last_open
        assert "closed after round" in detail["message"] and "rounds from now" in detail["message"]


class TestTrading:
    def test_buying_spends_the_balance_and_the_ledger_prints_both(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        listing = _opened(auth_client, slug)["listings"][0]
        bought = auth_client.post(f"{API}/{slug}/buy", json={"listing": listing["id"], "use_clause": True}).json()
        assert bought["bought"] is True and bought["move"]["kind"] == "buy"
        assert bought["move"]["fee"] == listing["release_clause"]
        assert bought["budget"]["remaining"] == BUDGET - listing["release_clause"]
        assert bought["budget"]["spent"] == listing["release_clause"]
        assert bought["moves"] == [dict(bought["move"])]
        assert bought["totals"]["signed"] == 1 and bought["totals"]["listed"] == MARKET_SIZE - 1
        assert bought["deals"][0]["player_name"] == listing["player_name"]
        again = auth_client.post(f"{API}/{slug}/buy", json={"listing": listing["id"], "use_clause": True})
        assert again.status_code == 409 and again.json()["detail"]["code"] == "not_on_sale"

    def test_a_loan_is_cheap_and_expires_by_the_rule_it_ships_with(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        listing = _opened(auth_client, slug)["listings"][0]
        loaned = auth_client.post(f"{API}/{slug}/loan", json={"listing": listing["id"], "rounds": 2}).json()
        assert loaned["loaned"] is True and loaned["move"]["kind"] == "loan"
        assert loaned["move"]["fee"] < listing["current_price"] and loaned["move"]["loan_until_round"] == 2
        assert loaned["detail"]["covers"] == "rounds 1 to 2 inclusive"
        assert "loan fee = round_5" in loaned["rules"]["loan"]

    def test_selling_and_releasing_your_own_players_moves_the_squad(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        squad = auth_client.get(f"{API}/{slug}").json()["squad"]["players"]
        sold = auth_client.post(f"{API}/{slug}/sell", json={"player": squad[0]["player_id"]}).json()
        assert sold["sold"] is True and sold["move"]["kind"] == "sell" and sold["move"]["fee"] > 0
        assert sold["budget"]["remaining"] == BUDGET + sold["move"]["fee"]
        assert sold["detail"]["proceeds_formula"] == sold["rules"]["sell"]
        released = auth_client.post(f"{API}/{slug}/release", json={"player": squad[1]["player_id"]}).json()
        assert released["released"] is True and released["move"]["fee"] == 0
        assert released["squad"]["account"]["departed"] == 2 and released["squad"]["account"]["squad_now"] == 13
        assert sorted(move["kind"] for move in released["moves"]) == ["release", "sell"]

    def test_a_refusal_carries_the_numbers_behind_it(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        poor = _career(auth_client, club_id, budget=5_000, manager_name="Poor Manager")
        listing = _opened(auth_client, poor)["listings"][0]
        refused = auth_client.post(f"{API}/{poor}/buy", json={"listing": listing["id"], "use_clause": True})
        assert refused.status_code == 409
        detail = refused.json()["detail"]
        assert detail["code"] == "insufficient_budget"
        assert detail["fee"] == listing["release_clause"] and detail["remaining"] == 5_000
        assert detail["formula"] == BUDGET_FORMULA
        missing = auth_client.post(f"{API}/{poor}/buy", json={"listing": "not-a-listing"})
        assert missing.status_code == 404 and missing.json()["detail"]["code"] == "no_such_listing"
        stranger = auth_client.post(f"{API}/{poor}/release", json={"player": "nobody-here"})
        assert stranger.status_code == 409 and stranger.json()["detail"]["code"] == "not_your_player"

    def test_a_retired_careers_market_is_closed_and_says_why(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        auth_client.post(f"{CAREERS}/{slug}/retire")
        refused = auth_client.post(f"{API}/{slug}/market")
        assert refused.status_code == 409
        assert refused.json()["detail"]["code"] == "career_retired"
        assert auth_client.get(f"{API}/{slug}").json()["transfers_allowed"]["ok"] is False


class TestMarketReachesTheMatch:
    def test_a_round_played_after_a_signing_reports_the_eleven_it_used(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        listing = max(_opened(auth_client, slug)["listings"], key=lambda row: (row["overall"], row["player_slug"]))
        bought = auth_client.post(f"{API}/{slug}/buy", json={"listing": listing["id"], "use_clause": True}).json()
        assert bought["moves"][0]["player_slug"] == listing["player_slug"]
        played = auth_client.post(f"{CAREERS}/{slug}/play").json()
        assert played["played"] is True and played["career"]["rounds_played"] == 1
        report = auth_client.get(f"/api/v1/simulate/{played['match']['slug']}").json()["report"]
        used = report["sides"][played["fixtures"][0]["side"]]
        assert career_squad(slug, str(used["squad_label"])), "the match report says which career's squad played it"
        assert listing["player_name"] in [entry["player"] for entry in used["lineup"]], "the player the career signed is named in the eleven that played"
        assert played["challenge_verdict"] is None and "spent, not stated" in played["limitations"]["budget"]

    def test_a_career_that_never_traded_reports_no_squad_of_its_own(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = _career(auth_client, club_id)
        played = auth_client.post(f"{CAREERS}/{slug}/play").json()
        report = auth_client.get(f"/api/v1/simulate/{played['match']['slug']}").json()["report"]
        assert report["sides"][played["fixtures"][0]["side"]]["squad_label"] == ""
        assert played["limitations"]["budget"], "the sentence about the budget is still printed when it was never spent"


def career_squad(slug: str, label: str) -> bool:
    """The report names the career whose squad it played with, not some other club's."""
    return label.startswith(f"{slug} squad as of round ")
