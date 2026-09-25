"""M7 §23's shortlist — a list that stores membership, tested against the figures it refuses to store.

The claim under test is unusual, so the tests are arranged backwards from it. A shortlist answers *who am I
watching*, and every number it prints is re-taken from `real_players` on the request that shows it. A test
that only checked "the list prints 68" would pass even if the module had copied 68 into a column at add-time,
because a copy and its source agree right up to the moment they do not. So the load-bearing tests here change a
stored row underneath a list and assert two things at once: the list moved, and the membership row did not.

What else is here, and why:

* the columns themselves, as a set difference — the only shape of test that notices a fifth being added later;
* every cap refused with its own figures beside the sentence, so a 409 can be checked against a number;
* ownership, checked against a second account that is really a second account (`_account()` opens its own client);
* the re-check of the stored sentence, nested under `recheck` so it can never overwrite what somebody typed;
* the career link, whose need and fit are the market's own, called directly and compared field by field;
* and the integrity gate this tier ships with, given a violation to find before it is cleaned up.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import Career, RealPlayer, ScoutShortlist, ScoutShortlistItem, Team, User
from app.services.scouting import shortlist as shortlist_module
from app.services.scouting.requirements import parse_requirements
from app.services.scouting.search import pool, search
from app.services.scouting.shortlist import (
    MAX_ITEMS,
    MAX_SHORTLISTS,
    NAME_MAX,
    NOTE_MAX,
    QUERY_MAX,
    REFUSALS,
    ShortlistRefusal,
    add_player,
    create_shortlist,
    limitations,
    rules,
    shortlist_counts,
    shortlist_problems,
    shortlist_ready,
    shortlist_view,
)
from app.services.simulation import market
from app.services.world import sync_world, world_ready

SHORTLISTS = "/api/v1/scout/shortlists"
CAREERS = "/api/v1/careers"
PASSWORD = "strong-pass-1234"
SENTENCE = "找一个 22 岁以下的球员"


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world, and the rows this tier has to be able to tell apart."""
    session = SessionLocal()
    try:
        sync_world(session)
        rows = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(rows) > 100 and world_ready(session)
        club = str(session.scalars(select(Team.id).order_by(Team.overall, Team.slug).limit(1)).one())
        youngest = min(rows, key=lambda row: (int(row.age), row.slug))
        oldest = max(rows, key=lambda row: (int(row.age), row.slug))
        return {
            "players": len(rows),
            "club_id": club,
            "youngest": youngest.slug,
            "youngest_age": int(youngest.age),
            "oldest": oldest.slug,
            "oldest_age": int(oldest.age),
            "many": [row.slug for row in rows[: MAX_ITEMS + 3]],
            "second": rows[1].slug,
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Session]:
    """A session over the seeded world, so a subset run never reads an empty pool."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(name: str = "List Manager") -> TestClient:
    """Its own client with its own signed-in account — the only way to test that two managers differ."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"shortlist-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _who(client: TestClient) -> User:
    session = SessionLocal()
    try:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200, response.text
        row = session.scalar(select(User).where(User.id == str(response.json()["id"])))
        assert row is not None
        session.expunge(row)
        return row
    finally:
        session.close()


def _opened(client: TestClient, **body: Any) -> dict[str, Any]:
    response = client.post(SHORTLISTS, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _listed(client: TestClient, ident: str, slug: str, note: str = "") -> dict[str, Any]:
    response = client.post(f"{SHORTLISTS}/{ident}/items", json={"player": slug, "note": note})
    assert response.status_code == 200, response.text
    return response.json()


def _read(client: TestClient, ident: str) -> dict[str, Any]:
    response = client.get(f"{SHORTLISTS}/{ident}")
    assert response.status_code == 200, response.text
    return response.json()


def _career(client: TestClient, world: dict[str, Any]) -> str:
    response = client.post(
        CAREERS,
        json={"club": world["club_id"], "manager_name": "List Manager", "philosophy": "balanced", "budget": 4_000_000, "objectives": [{"kind": "wins", "target": 1, "label": "win once"}]},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["career"]["slug"])


def _row(slug: str) -> RealPlayer:
    session = SessionLocal()
    try:
        player = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
        assert player is not None, slug
        session.expunge(player)
        return player
    finally:
        session.close()


def _mutate(slug: str, **columns: int) -> dict[str, int]:
    """Move a stored player row and hand back what was there, so every test that bends the world undoes it."""
    session = SessionLocal()
    try:
        player = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
        assert player is not None, slug
        before = {key: int(getattr(player, key)) for key in columns}
        for key, value in columns.items():
            setattr(player, key, value)
        session.commit()
        return before
    finally:
        session.close()


def _items_of(session: Session, ident: str) -> list[ScoutShortlistItem]:
    return list(session.scalars(select(ScoutShortlistItem).where(ScoutShortlistItem.shortlist_id == ident).order_by(ScoutShortlistItem.position)))


class TestWhatIsStored:
    """The columns, read as a claim: membership and words here, and nothing that measures a player."""

    def test_a_membership_row_holds_exactly_four_facts_about_a_player(self) -> None:
        assert {column.name for column in ScoutShortlistItem.__table__.columns} == {"id", "shortlist_id", "player_id", "note", "position", "created_at", "updated_at"}

    def test_no_column_of_a_membership_row_measures_a_player(self) -> None:
        measured = {
            "age",
            "overall",
            "potential",
            "headroom",
            "asking_fee",
            "fee",
            "value",
            "rating",
            "minutes",
            "goals",
            "assists",
            "wage",
            "band",
            "foot",
            "preferred_foot",
            "club_id",
            "score",
            "rank",
            "position_code",
        }
        assert measured & {column.name for column in ScoutShortlistItem.__table__.columns} == set()

    def test_a_list_row_holds_a_name_a_sentence_and_two_links(self) -> None:
        assert {column.name for column in ScoutShortlist.__table__.columns} == {
            "id",
            "owner_id",
            "career_id",
            "name",
            "query",
            "role",
            "data_origin",
            "is_demo_data",
            "created_at",
            "updated_at",
        }

    def test_opening_a_list_writes_no_membership_row_at_all(self, world: dict[str, Any]) -> None:
        ident = _opened(_account(), name="Midfield targets", query=SENTENCE)["shortlist"]["id"]
        session = SessionLocal()
        try:
            assert _items_of(session, ident) == []
        finally:
            session.close()

    def test_a_role_is_kept_upper_cased_and_a_sentence_word_for_word(self, world: dict[str, Any]) -> None:
        created = _opened(_account(), name="Wide players", query=SENTENCE, role="rw")
        assert created["shortlist"]["role"] == "RW" and created["shortlist"]["query"] == SENTENCE

    def test_the_stored_words_are_labelled_as_the_account_s_not_as_data(self, world: dict[str, Any]) -> None:
        ident = _opened(_account(), name="Own words")["shortlist"]["id"]
        session = SessionLocal()
        try:
            stored = session.scalar(select(ScoutShortlist).where(ScoutShortlist.id == ident))
        finally:
            session.close()
        assert stored is not None and stored.data_origin == "user" and stored.is_demo_data is False

    def test_two_accounts_may_call_their_lists_the_same_thing(self, world: dict[str, Any]) -> None:
        first, second = _opened(_account("First"), name="Same name")["shortlist"], _opened(_account("Second"), name="Same name")["shortlist"]
        assert first["id"] != second["id"]

    def test_one_account_may_not_and_the_refusal_names_the_name(self, world: dict[str, Any]) -> None:
        client = _account()
        _opened(client, name="Only once")
        refused = client.post(SHORTLISTS, json={"name": "Only once"})
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"]["code"] == "name_taken" and refused.json()["detail"]["name"] == "Only once"


class TestLimits:
    """Every cap is a number the routes refuse on, so every refusal has to print it back."""

    def test_every_refusal_code_is_classified_exactly_once(self) -> None:
        """The route turns a code into an answer through three sets, so a code in none or in two is a bug.

        A new refusal that belongs to no set would quietly answer 409, and one that is in two would answer
        whichever set the route happens to read first — neither is visible in any other test here.
        """
        from app.services.scouting.shortlist import CONFLICT_CODES, NOT_FOUND_CODES, UNPROCESSABLE_CODES

        classified = NOT_FOUND_CODES | UNPROCESSABLE_CODES | CONFLICT_CODES
        assert set(REFUSALS) == set(classified), sorted(set(REFUSALS) - classified)
        assert len(classified) == len(REFUSALS), "a code sits in two of the three sets"
        assert NOT_FOUND_CODES.isdisjoint(UNPROCESSABLE_CODES) and NOT_FOUND_CODES.isdisjoint(CONFLICT_CODES) and UNPROCESSABLE_CODES.isdisjoint(CONFLICT_CODES)

    def test_the_limits_are_published_before_anyone_trips_over_them(self) -> None:
        published = rules()
        assert published["max_shortlists_per_user"] == MAX_SHORTLISTS and published["max_items_per_shortlist"] == MAX_ITEMS
        assert published["name_max"] == NAME_MAX and published["note_max"] == NOTE_MAX and published["query_max"] == QUERY_MAX
        assert published["codes"] == list(REFUSALS)

    def test_an_empty_name_is_refused_with_the_limit_beside_it(self, world: dict[str, Any]) -> None:
        refused = _account().post(SHORTLISTS, json={"name": "   "})
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["code"] == "name_required"

    def test_an_over_long_name_reports_its_own_length(self, world: dict[str, Any]) -> None:
        refused = _account().post(SHORTLISTS, json={"name": "n" * (NAME_MAX + 1)})
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["length"] == NAME_MAX + 1 and refused.json()["detail"]["max"] == NAME_MAX

    def test_a_note_too_long_is_refused_rather_than_cut_off(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Notes")["shortlist"]["id"]
        refused = client.post(f"{SHORTLISTS}/{ident}/items", json={"player": world["youngest"], "note": "x" * (NOTE_MAX + 1)})
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["code"] == "note_too_long" and refused.json()["detail"]["length"] == NOTE_MAX + 1
        session = SessionLocal()
        try:
            assert _items_of(session, ident) == [], "a refusal that stored half a note would leave a sentence nobody typed"
        finally:
            session.close()

    def test_a_list_refuses_its_thirty_first_player(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Full house")["shortlist"]["id"]
        for slug in world["many"][:MAX_ITEMS]:
            _listed(client, ident, slug)
        refused = client.post(f"{SHORTLISTS}/{ident}/items", json={"player": world["second"]})
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"]["code"] == "shortlist_full" and refused.json()["detail"]["held"] == MAX_ITEMS
        assert _read(client, ident)["counts"]["membership_rows"] == MAX_ITEMS

    def test_an_account_refuses_its_twenty_first_list(self, world: dict[str, Any]) -> None:
        client = _account()
        for index in range(MAX_SHORTLISTS):
            _opened(client, name=f"List {index + 1}")
        refused = client.post(SHORTLISTS, json={"name": "One too many"})
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"]["held"] == MAX_SHORTLISTS and refused.json()["detail"]["limit"] == MAX_SHORTLISTS

    def test_a_player_cannot_be_put_on_the_same_list_twice(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Once each")["shortlist"]["id"]
        _listed(client, ident, world["youngest"], note="first word")
        refused = client.post(f"{SHORTLISTS}/{ident}/items", json={"player": world["youngest"], "note": "second word"})
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "already_listed"
        entry = _read(client, ident)["items"][0]
        assert entry["note"] == "first word", "a refused add must not rewrite the note either"
        assert _read(client, ident)["counts"]["membership_rows"] == 1


class TestMembershipIsNotACopy:
    """Move the stored row: the list moves with it, and the membership row does not."""

    def test_every_figure_on_a_read_equals_the_stored_row(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Straight reads")["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        entry = _read(client, ident)["items"][0]["player"]
        player = _row(world["youngest"])
        assert entry["age"] == int(player.age) and entry["overall"] == int(player.overall) and entry["potential"] == int(player.potential)
        assert entry["headroom"] == int(player.potential) - int(player.overall)
        assert entry["preferred_foot"] == player.preferred_foot and entry["position"] == player.position
        assert entry["season"]["minutes"] == int(player.minutes), "a season printed by a list is the row's own season"
        assert entry["valuation"]["asking_fee"] == int(market.valuation(player)["asking_fee"])

    def test_a_changed_row_moves_the_list_and_leaves_the_membership_alone(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Live figures")["shortlist"]["id"]
        _listed(client, ident, world["youngest"], note="watching him")
        before = _read(client, ident)["items"][0]

        player = _row(world["youngest"])
        moved = _mutate(world["youngest"], overall=int(player.overall) + 4, potential=max(int(player.potential), int(player.overall) + 6))
        try:
            after = _read(client, ident)["items"][0]
            assert after["player"]["overall"] == before["player"]["overall"] + 4, "a list still printing the old number had copied it"
            assert after["player"]["headroom"] == after["player"]["potential"] - after["player"]["overall"]
            assert after["player"]["valuation"]["asking_fee"] != before["player"]["valuation"]["asking_fee"], "the fee is priced off the row that moved"
            assert after["note"] == "watching him" and after["position"] == before["position"] and after["added_at"] == before["added_at"]
        finally:
            _mutate(world["youngest"], **moved)
        assert _read(client, ident)["items"][0]["player"]["overall"] == before["player"]["overall"], "and the world is as it was found"

    def test_a_list_and_a_search_print_the_same_numbers_for_one_player(self, world: dict[str, Any]) -> None:
        """Take a player the search itself offered, then ask whether the list says the same about him.

        A search page is capped, so the test starts from the page and lists who is actually on it, rather than
        hoping a chosen row made the cut — a check that compares two empty sets proves nothing to anybody.
        """
        session = SessionLocal()
        try:
            found = search(session, parse_requirements(SENTENCE), limit=MAX_ITEMS)
        finally:
            session.close()
        assert found["candidates"], "an empty page would make the agreement below vacuous"
        client = _account()
        ident = _opened(client, name="Agreeing", query=SENTENCE)["shortlist"]["id"]
        _listed(client, ident, str(found["candidates"][0]["slug"]))
        entry = _read(client, ident)["items"][0]["player"]
        match = next(row for row in found["candidates"] if row["slug"] == entry["slug"])
        for key in ("age", "overall", "potential", "headroom", "preferred_foot", "position", "band", "archetype"):
            assert entry[key] == match[key], f"{key} differs between the list and the search"
        assert entry["valuation"] == match["valuation"], "the same valuation, not a copy of an older one"

    def test_the_read_says_where_its_numbers_came_from(self, world: dict[str, Any]) -> None:
        client = _account()
        view = _read(client, _opened(client, name="Provenance")["shortlist"]["id"])
        assert "real_players" in view["figures_from"]
        assert view["data_origin"] == "synthetic" and view["is_demo_data"] is True
        assert "account" in view["account_content"], "the words are the account's; the footballers are generated"

    def test_a_membership_row_cannot_be_written_for_a_player_who_is_not_in_the_world(self, world: dict[str, Any]) -> None:
        """The schema refuses the hole before any read has to print one — checked by trying to plant it."""
        client = _account()
        ident = _opened(client, name="A dangling row")["shortlist"]["id"]
        session = SessionLocal()
        try:
            session.add(ScoutShortlistItem(id="ssli_planted", shortlist_id=ident, player_id="no_such_player_row", note="planted", position=1))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        finally:
            session.close()
        view = _read(client, ident)
        assert view["counts"]["printed"] == 0 and view["counts"]["membership_rows"] == 0
        assert view["gone_from_the_world"] == []

    def test_the_key_that_forbids_a_ghost_is_written_in_the_schema_not_in_this_code(self) -> None:
        """A list cannot keep a player the world has lost: the foreign key takes his row with him.

        Read off the constraint rather than by deleting somebody out of the shared world — deleting a stored
        player to prove a cascade would leave every later test in this module counting a smaller pool.
        """
        to_players = [key for key in ScoutShortlistItem.__table__.foreign_keys if key.column.table.name == "real_players"]
        assert len(to_players) == 1, to_players
        assert to_players[0].ondelete == "CASCADE"
        assert "gone_from_the_world" in " ".join(shortlist_module.limitations()), "the guard is documented, not merely coded"


class TestRecheckedOnRead:
    """The stored sentence is a question, and every read answers it again for every member."""

    def test_a_player_who_no_longer_answers_the_sentence_says_what_he_lost(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Too old now", query=SENTENCE)["shortlist"]["id"]
        _listed(client, ident, world["oldest"])
        recheck = _read(client, ident)["items"][0]["recheck"]
        assert recheck["asked"] == SENTENCE and recheck["answers"] == []
        assert [item["phrase"] for item in recheck["no_longer_answers"]] == ["22 岁以下"]
        assert _read(client, ident)["counts"]["answered_nothing"] == 1

    def test_a_player_who_still_answers_reports_nothing_lost(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Still answers", query=SENTENCE)["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        recheck = _read(client, ident)["items"][0]["recheck"]
        assert [item["phrase"] for item in recheck["answers"]] == ["22 岁以下"] and recheck["no_longer_answers"] == []
        assert _read(client, ident)["counts"]["answered_everything"] == 1

    def test_a_refused_phrase_of_the_stored_sentence_rides_with_every_member(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Half understood", query="找一个 22 岁以下、擅长推进的球员")["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        _listed(client, ident, world["oldest"])
        for entry in _read(client, ident)["items"]:
            refused = [str(item["phrase"]) for item in entry["recheck"]["refused"]]
            assert len(refused) == 1 and "擅长推进" in refused[0], "a phrase this vocabulary does not know stays named, on every row, in the words it was read in"
            assert entry["recheck"]["filters_applied"] == 1, "the understood half is still applied, and only the understood half"

    def test_a_list_with_no_sentence_checks_nothing_and_says_that(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="No question")["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        entry = _read(client, ident)["items"][0]
        assert entry["recheck"]["asked"] is None and entry["recheck"]["filters_applied"] == 0
        assert "nothing is re-checked" in entry["recheck"]["note"]
        assert _read(client, ident)["counts"]["no_sentence_to_answer"] == 1

    def test_changing_the_question_remakes_every_verdict(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Changed mind", query=SENTENCE)["shortlist"]["id"]
        _listed(client, ident, world["oldest"])
        assert _read(client, ident)["counts"]["answered_nothing"] == 1
        patched = client.patch(f"{SHORTLISTS}/{ident}", json={"query": "找一个 30 岁以上的球员"})
        assert patched.status_code == 200, patched.text
        assert patched.json()["changed"]["query"] == "找一个 30 岁以上的球员"
        assert _read(client, ident)["counts"]["answered_everything"] == 1, "the same membership, a different question, a different answer"

    def test_the_manager_s_note_survives_a_recheck_that_would_otherwise_write_over_it(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="My words", query=SENTENCE)["shortlist"]["id"]
        _listed(client, ident, world["youngest"], note="signed up at seventeen")
        entry = _read(client, ident)["items"][0]
        assert entry["note"] == "signed up at seventeen"
        assert entry["recheck"]["note"] != entry["note"], "a computation about the list's sentence does not own the item's note"


class TestCareerLink:
    """A list may answer to a career, and every figure that depends on one is the market's own."""

    def test_a_linked_career_borrows_the_market_s_need_field_by_field(self, world: dict[str, Any]) -> None:
        client = _account()
        slug = _career(client, world)
        ident = _opened(client, name="For the squad", career=slug)["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        view = _read(client, ident)
        session = SessionLocal()
        try:
            career = session.scalar(select(Career).where(Career.slug == slug))
            assert career is not None
            expected = market.club_need(session, career, round_index=int(career.rounds_played))
            fit = market.tactical_fit(_row(world["youngest"]), str(expected["needed_band"]))
        finally:
            session.close()
        assert view["career"]["slug"] == slug
        assert view["need"]["needed_band"] == expected["needed_band"] and view["need"]["bands"] == expected["bands"]
        assert view["need"]["formation"] == expected["formation"] and view["need"]["system_slug"] == expected["system_slug"]
        printed = view["items"][0]["player"]["tactical_fit"]
        assert printed["fit"] == pytest.approx(float(fit["fit"])) and printed["formula"] == market.FIT_FORMULA

    def test_a_round_named_by_the_reader_moves_the_need(self, world: dict[str, Any]) -> None:
        client = _account()
        slug = _career(client, world)
        ident = _opened(client, name="By round", career=slug)["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        later = client.get(f"{SHORTLISTS}/{ident}", params={"round_index": 6})
        assert later.status_code == 200, later.text
        session = SessionLocal()
        try:
            career = session.scalar(select(Career).where(Career.slug == slug))
            assert career is not None
            expected = market.club_need(session, career, round_index=6)
        finally:
            session.close()
        assert later.json()["need"]["needed_band"] == expected["needed_band"]
        assert later.json()["need"]["bands"] == expected["bands"]

    def test_another_account_s_career_is_not_a_link_at_all(self, world: dict[str, Any]) -> None:
        owner, other = _account("Owner"), _account("Other")
        slug = _career(owner, world)
        refused = other.post(SHORTLISTS, json={"name": "Not mine", "career": slug})
        assert refused.status_code == 404, refused.text
        assert refused.json()["detail"]["code"] == "no_such_career", "a foreign career answers as one that does not exist"

    def test_a_deleted_career_leaves_the_list_and_only_loses_the_need(self, world: dict[str, Any]) -> None:
        client = _account()
        slug = _career(client, world)
        ident = _opened(client, name="Outlives the job", career=slug)["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        assert client.delete(f"{CAREERS}/{slug}").status_code == 200
        view = _read(client, ident)
        assert view["career"] is None and view["need"] is None
        assert view["counts"]["printed"] == 1, "the list is still the manager's own; only the whose-need answer went away"

    def test_no_career_means_no_fit_column_rather_than_a_zero(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Nobody's squad")["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        assert _read(client, ident)["items"][0]["player"]["tactical_fit"] is None


class TestOwnershipAndOrder:
    """A list is reachable by its id, by its owner only, in the order it was built."""

    def test_another_account_cannot_read_change_or_delete_a_list(self, world: dict[str, Any]) -> None:
        owner, other = _account("Owner"), _account("Other")
        ident = _opened(owner, name="Private")["shortlist"]["id"]
        assert other.get(f"{SHORTLISTS}/{ident}").status_code == 404
        assert other.patch(f"{SHORTLISTS}/{ident}", json={"name": "Hijacked"}).status_code == 404
        assert other.delete(f"{SHORTLISTS}/{ident}").status_code == 404
        assert other.post(f"{SHORTLISTS}/{ident}/items", json={"player": world["youngest"]}).status_code == 404
        assert other.delete(f"{SHORTLISTS}/{ident}/items/{world['youngest']}").status_code == 404
        assert _read(owner, ident)["shortlist"]["name"] == "Private"

    def test_the_list_route_shows_only_this_account_s_lists(self, world: dict[str, Any]) -> None:
        mine, theirs = _account("Mine"), _account("Theirs")
        ident = _opened(mine, name="Only mine")["shortlist"]["id"]
        _opened(theirs, name="Only theirs")
        listed = mine.get(SHORTLISTS).json()
        assert [row["name"] for row in listed["items"]] == ["Only mine"]
        assert listed["items"][0]["id"] == ident and listed["items"][0]["players_listed"] == 0
        assert listed["total"] == 1 and listed["room_left"] == MAX_SHORTLISTS - 1

    def test_an_anonymous_caller_is_turned_away_from_every_door(self, world: dict[str, Any]) -> None:
        anonymous = TestClient(app)
        assert anonymous.get(SHORTLISTS).status_code in (401, 403)
        assert anonymous.post(SHORTLISTS, json={"name": "Nobody"}).status_code in (401, 403)
        assert anonymous.get(f"{SHORTLISTS}/anything").status_code in (401, 403)

    def test_a_list_that_is_not_there_names_the_id_and_what_is_held(self, world: dict[str, Any]) -> None:
        refused = _account().get(f"{SHORTLISTS}/ssl_does-not-exist")
        assert refused.status_code == 404 and refused.json()["detail"]["code"] == "no_such_shortlist"
        assert refused.json()["detail"]["lists_held"] == 0 and refused.json()["detail"]["ident"] == "ssl_does-not-exist"

    def test_positions_are_the_order_the_list_was_built_in(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Insertion order")["shortlist"]["id"]
        for slug in world["many"][:4]:
            _listed(client, ident, slug)
        assert [entry["position"] for entry in _read(client, ident)["items"]] == [1, 2, 3, 4]
        assert [entry["player"]["slug"] for entry in _read(client, ident)["items"]] == world["many"][:4]

    def test_taking_a_player_off_leaves_the_others_where_they_were(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Order kept")["shortlist"]["id"]
        for slug in world["many"][:3]:
            _listed(client, ident, slug)
        dropped = client.delete(f"{SHORTLISTS}/{ident}/items/{world['many'][1]}")
        assert dropped.status_code == 200, dropped.text
        assert dropped.json()["now_lists"] == 2
        assert [entry["position"] for entry in _read(client, ident)["items"]] == [1, 3], "the rows that stay keep the positions they had"

    def test_an_unlisted_player_is_not_reported_as_removed(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Empty")["shortlist"]["id"]
        refused = client.delete(f"{SHORTLISTS}/{ident}/items/{world['youngest']}")
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "not_listed"
        assert refused.json()["detail"]["listed"] == []

    def test_deleting_a_list_takes_its_membership_with_it(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Temporary")["shortlist"]["id"]
        for slug in world["many"][:3]:
            _listed(client, ident, slug)
        gone = client.delete(f"{SHORTLISTS}/{ident}")
        assert gone.status_code == 200 and gone.json()["players_left_off"] == 3
        session = SessionLocal()
        try:
            assert _items_of(session, ident) == []
            assert session.scalar(select(ScoutShortlist).where(ScoutShortlist.id == ident)) is None
        finally:
            session.close()


class TestPublished:
    """What the tier says about itself, checked against what it does."""

    def test_the_rules_endpoint_publishes_the_limits_and_every_refusal_it_names(self, world: dict[str, Any]) -> None:
        published = TestClient(app).get("/api/v1/scout/rules").json()["shortlists"]
        explained = set(published["refusals"])
        assert explained <= set(REFUSALS), sorted(explained - set(REFUSALS))
        assert explained == {
            "no_such_shortlist",
            "no_such_player",
            "no_such_career",
            "already_listed",
            "shortlist_full",
            "too_many_shortlists",
            "not_listed",
            "name_taken",
        }, "the codes a client has to branch on are the ones the endpoint explains"
        assert published["max_shortlists_per_user"] == MAX_SHORTLISTS and published["max_items_per_shortlist"] == MAX_ITEMS
        assert published["not_stored"].startswith("every figure about a player")
        assert "cascade" in " ".join(published["limitations"]) or "gone_from_the_world" in " ".join(published["limitations"])

    def test_the_read_prints_its_own_limits_and_their_meaning(self, world: dict[str, Any]) -> None:
        client = _account()
        view = _read(client, _opened(client, name="Self describing")["shortlist"]["id"])
        assert view["rules"] == rules() and view["limitations"] == limitations()
        assert len(view["limitations"]) >= 6

    def test_capabilities_reports_the_tier_and_says_it_stores_no_figures(self, world: dict[str, Any]) -> None:
        session = SessionLocal()
        try:
            assert shortlist_ready(session) is True
            counts = shortlist_counts(session)
        finally:
            session.close()
        flags = TestClient(app).get("/api/v1/capabilities").json()
        assert flags["m7_shortlist"]["ready"] is True and flags["m7_shortlist"]["stores_no_figures"] is True
        assert flags["m7_shortlist"]["counts"]["lists_per_user"] == MAX_SHORTLISTS
        assert flags["m7_shortlist"]["counts"]["membership_rows_stored"] == counts["membership_rows_stored"]

    def test_the_gate_is_clean_over_real_lists_and_finds_a_planted_pair(self, world: dict[str, Any]) -> None:
        client = _account()
        ident = _opened(client, name="Checked")["shortlist"]["id"]
        _listed(client, ident, world["youngest"])
        _listed(client, ident, world["second"])
        owner = _who(client)
        session = SessionLocal()
        try:
            gate = shortlist_problems(session, owner)
            assert gate["clean"] is True, gate["problems"]
            assert gate["checked"]["membership_rows"] >= 2 and gate["checked"]["players_in_pool"] == world["players"]
            first, second = _items_of(session, ident)
            second.position = int(first.position)
            session.commit()
            planted = shortlist_problems(session, owner)
            assert not planted["clean"], "two rows in one position is a list that cannot be added to again"
            assert any("positions are" in problem for problem in planted["problems"])
            second.position = int(first.position) + 1
            session.commit()
            assert shortlist_problems(session, owner)["clean"] is True
        finally:
            session.close()

    def test_the_list_route_carries_that_gate_for_the_account_reading_it(self, world: dict[str, Any]) -> None:
        client = _account()
        _opened(client, name="Gated")
        listed = client.get(SHORTLISTS).json()
        assert listed["integrity"]["clean"] is True and listed["integrity"]["checked"]["shortlists"] == 1
        assert "real_players" in listed["integrity"]["rule"]


class TestServiceLayer:
    """The refusals themselves, without an HTTP layer between the claim and the check."""

    def test_a_player_not_in_the_pool_never_becomes_a_row(self, world: dict[str, Any]) -> None:
        session = SessionLocal()
        try:
            owner = _who(_account())
            created = create_shortlist(session, owner, name="Service level")
            session.commit()
            with pytest.raises(ShortlistRefusal) as raised:
                add_player(session, owner, created["shortlist"]["id"], player="definitely-not-here")
            assert raised.value.code == "no_such_player" and raised.value.figures["ident"] == "definitely-not-here"
        finally:
            session.close()

    def test_a_view_of_another_account_s_list_refuses_before_reading_anything(self, world: dict[str, Any]) -> None:
        session = SessionLocal()
        try:
            ident = _opened(_account("Owner"), name="Not for you")["shortlist"]["id"]
            with pytest.raises(ShortlistRefusal) as raised:
                shortlist_view(session, _who(_account("Other")), ident)
            assert raised.value.code == "no_such_shortlist" and raised.value.figures["lists_held"] == 0
        finally:
            session.close()

    def test_the_projection_a_list_prints_is_the_search_s_own_function(self, world: dict[str, Any]) -> None:
        session = SessionLocal()
        try:
            client = _account()
            ident = _opened(client, name="Same code path")["shortlist"]["id"]
            _listed(client, ident, world["youngest"])
            view = shortlist_view(session, _who(client), ident)
            candidate = next(item for item in pool(session) if item.player.slug == world["youngest"])
            assert view["items"][0]["player"]["overall"] == int(candidate.player.overall)
            assert view["items"][0]["player"]["club"] == ({"name": candidate.club_name, "slug": candidate.club_slug, "path": f"/team/{candidate.club_slug}"} if candidate.club_slug else None)
        finally:
            session.close()

    def test_the_counts_this_tier_reports_are_counts_of_membership(self, world: dict[str, Any]) -> None:
        session = SessionLocal()
        try:
            counts = shortlist_counts(session)
            assert counts["shortlists_stored"] == int(session.scalar(select(func.count()).select_from(ScoutShortlist)) or 0)
            assert counts["membership_rows_stored"] == int(session.scalar(select(func.count()).select_from(ScoutShortlistItem)) or 0)
        finally:
            session.close()
