"""§38's share output (M10): a link over a CV, revocable, public, and carrying no account.

The claims this file defends, in the order it attacks them:

* a token opens a read that needs no session, and closing the link takes that door away — §38's word for the output
  is *revocable*, which is the whole difference between a link and a leak;
* an unknown token and a closed one — the account's own or another account's — earn the same 404 with the same
  sentence, so no answer on this path reports which tokens this build has heard of (§35's reach rule, applied to a
  key), while a live token opens its door for whoever holds it, which is the whole point of a link;
* the public payload is a projection, not a scrub: the account block never enters it, and the case searches the
  emitted JSON for the identifying keys rather than trusting the docstring;
* what the link shows is re-read at the moment of the request — a session completed after the link was minted
  appears through the link, which a stored snapshot could not pass;
* the table that makes the link possible stores no figure: its columns are asserted over `Base.metadata`, because
  §38's "nothing here is a copy" claim is worth nothing if the share row quietly became a copy;
* the two refusals that can stop a link from being minted are answered *before* a token exists, and a minor's
  `videos` is one of them while an adult's is not — the pair, because a guard with no passing side proves nothing
  (§40's data-minimisation rule, through §49's one threshold constant, imported rather than restated);
* every code this tier now answers with is registered in the project's one table, and none of them is a 403, which
  §35, §36 and §38 keep for `insufficient_role`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import Base, SessionLocal
from app.main import app
from app.services.club import academy, answers
from app.services.portfolio import cv as portfolio
from app.services.portfolio import sharing

CV = "/api/v1/portfolio/cv"
RULES = "/api/v1/portfolio/rules"
SHARE = "/api/v1/portfolio/share"
SHARES = "/api/v1/portfolio/shares"
PASSWORD = "strong-pass-1234"

#: The section list every case here publishes unless it is testing the list itself. Three filled, one unfilled,
# one withheld: a projection has to have a withheld side to be a projection. Deliberately typed in a different order
# from §38's, because the door is claimed to put it back.
PUBLISHED: Final = ["position", "skills", "training", "matches"]

#: What a reader sees, in the order the spec defines it. Derived from `SECTIONS` rather than retyped, so this file
# cannot be the place where §38's order stops being §38's order.
IN_SPEC_ORDER: Final = [key for key in portfolio.SECTIONS if key in set(PUBLISHED)]

#: What may never appear anywhere in a public answer, however the payload is nested. Typed here rather than imported
# from the service: a census that reads its own forbidden list from the code under test goes vacuous the moment that
# list is emptied. `test_the_service_and_this_file_agree_on_what_is_private` is the separate pin that turns drift red.
FORBIDDEN_KEYS: Final = ("user_id", "email", "display_name", "account", "id", "visibility")


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _client(name: str) -> TestClient:
    """Its own client with its own account, so a link is always one person's and no case can pass another's rows."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"share-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _player(client: TestClient, age: int = 24) -> dict[str, Any]:
    response = client.post(
        "/api/v1/players",
        json={"name": "Share Midfielder", "position": "CM", "age": age, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _open(client: TestClient, sections: list[str] | None = None) -> dict[str, Any]:
    response = client.post(SHARE, json={"sections": PUBLISHED if sections is None else sections})
    assert response.status_code == 200, response.text
    return response.json()


def _anonymous() -> TestClient:
    """A client with no session at all: the only caller a share link exists to serve."""
    return TestClient(app)


def _walk_keys(value: Any) -> Iterator[str]:
    """Every key in a nested payload, so "no account field is in the answer" is measured over the answer."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield str(key)
            yield from _walk_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk_keys(inner)


def _complete_a_session(client: TestClient) -> None:
    drills = client.get("/api/v1/trainings/drills")
    assert drills.status_code == 200, drills.text
    planned = client.post("/api/v1/trainings/sessions", json={"drill_id": drills.json()[0]["id"], "available_minutes": 60})
    assert planned.status_code == 201, planned.text
    done = client.post(f"/api/v1/trainings/sessions/{planned.json()['session_id']}/complete", json={"execution": 4, "focus": 4, "difficulty_experience": 3})
    assert done.status_code == 200, done.text


class TestALinkIsAKey:
    def test_opening_a_link_mints_a_token_and_anonymous_reader_gets_the_published_sections(self) -> None:
        client = _client("Ada Link")
        _player(client)
        _complete_a_session(client)
        record = _open(client)
        token = str(record["token"])
        assert sharing.TOKEN_BYTES * 2 == len(token) and all(char in "0123456789abcdef" for char in token), token
        answer = _anonymous().get(f"{SHARE}/{token}")
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert [section["section"] for section in body["sections"]] == IN_SPEC_ORDER
        unfilled = [key for key in IN_SPEC_ORDER if key in portfolio.UNFILLED_REASONS]
        assert body["counts"] == {"sections": len(IN_SPEC_ORDER), "filled": len(IN_SPEC_ORDER) - len(unfilled), "unfilled": unfilled}

    def test_the_public_door_answers_without_a_session_and_the_private_ones_do_not(self) -> None:
        client = _client("Ada Doors")
        _player(client)
        token = _open(client)["token"]
        assert _anonymous().get(f"{SHARE}/{token}").status_code == 200
        assert _anonymous().get(CV).status_code == 401
        assert _anonymous().post(SHARE, json={"sections": ["position"]}).status_code == 401
        assert _anonymous().get(SHARES).status_code == 401
        assert _anonymous().request("DELETE", f"{SHARE}/{token}").status_code == 401

    def test_closing_the_link_takes_the_door_away_and_the_same_token_then_answers_404(self) -> None:
        client = _client("Ada Close")
        _player(client)
        token = _open(client)["token"]
        assert _anonymous().get(f"{SHARE}/{token}").status_code == 200
        closed = client.request("DELETE", f"{SHARE}/{token}")
        assert closed.status_code == 200, closed.text
        assert closed.json()["live"] is False and closed.json()["token"] is None
        answer = _anonymous().get(f"{SHARE}/{token}")
        assert answer.status_code == 404, answer.text
        assert answer.json()["detail"]["code"] == "no_such_share"

    def test_repointing_an_open_link_keeps_the_token_and_changes_what_it_shows(self) -> None:
        """§17's rule that an old link keeps working: the choice that changes is the content, not the address."""
        client = _client("Ada Repoint")
        _player(client)
        first = _open(client)
        second = _open(client, sections=["position", "archetype"])
        assert second["token"] == first["token"], "a live link must not move while its owner edits it"
        assert second["sections"] == ["position", "archetype"]
        body = _anonymous().get(f"{SHARE}/{second['token']}").json()
        assert [section["section"] for section in body["sections"]] == ["position", "archetype"]

    def test_one_account_holds_one_open_link_and_its_history_stays_on_the_ledger(self) -> None:
        client = _client("Ada Ledger")
        _player(client)
        token = str(_open(client)["token"])
        client.request("DELETE", f"{SHARE}/{token}")
        fresh = _open(client, sections=["skills"])
        assert fresh["token"] != token, "a minted-after-revocation link must not reopen the closed door"
        ledger = client.get(SHARES).json()
        assert ledger["counts"] == {"opened": 2, "live": 1, "revoked": 1}
        assert token not in str(ledger["shares"]), "a closed token must not be printed back to anybody"
        assert [row["live"] for row in ledger["shares"]] == [True, False]


class TestAbsenceAnswersReach:
    def test_an_unknown_and_two_closed_tokens_earn_the_same_404_with_the_same_sentence(self) -> None:
        """Three tokens a stranger cannot tell apart: one never minted, two closed by owners who are not the reader."""
        first = _client("Ada Owner")
        _player(first)
        closed_one = str(_open(first)["token"])
        first.request("DELETE", f"{SHARE}/{closed_one}")
        second = _client("Ada Other")
        _player(second)
        closed_two = str(_open(second)["token"])
        second.request("DELETE", f"{SHARE}/{closed_two}")
        live = str(_open(second)["token"])
        answers_seen = [
            _anonymous().get(f"{SHARE}/deadbeefdeadbeefdeadbeefdeadbeef"),
            _anonymous().get(f"{SHARE}/{closed_one}"),
            _anonymous().get(f"{SHARE}/{closed_two}"),
        ]
        assert [answer.status_code for answer in answers_seen] == [404, 404, 404]
        prefixes = {str(answer.json()["detail"]["message"]).split("answers to")[0] for answer in answers_seen}
        assert len(prefixes) == 1, prefixes
        assert _anonymous().get(f"{SHARE}/{live}").status_code == 200, "a live token is a key, and a key opens its door"

    def test_trying_to_close_another_account_s_link_leaves_that_link_open(self) -> None:
        owner = _client("Ada StillOpen")
        _player(owner)
        token = str(_open(owner)["token"])
        stranger = _client("Ada Stranger")
        _player(stranger)
        refused = stranger.request("DELETE", f"{SHARE}/{token}")
        assert refused.status_code == 404, refused.text
        assert refused.json()["detail"]["code"] == "no_such_share"
        assert _anonymous().get(f"{SHARE}/{token}").status_code == 200, "the refusal must not have acted"

    def test_closing_a_link_twice_is_a_conflict_that_names_the_time_it_shut(self) -> None:
        client = _client("Ada Twice")
        _player(client)
        token = str(_open(client)["token"])
        assert client.request("DELETE", f"{SHARE}/{token}").status_code == 200
        again = client.request("DELETE", f"{SHARE}/{token}")
        assert again.status_code == 409, again.text
        assert again.json()["detail"]["code"] == "share_already_revoked"
        assert again.json()["detail"]["revoked_at"], again.text


class TestThePublicReadCarriesNoAccount:
    def test_no_identifying_key_appears_anywhere_in_the_public_payload(self) -> None:
        client = _client("Ada Silent")
        _player(client)
        token = str(_open(client)["token"])
        body = _anonymous().get(f"{SHARE}/{token}").json()
        found = sorted(set(_walk_keys(body)) & set(FORBIDDEN_KEYS))
        assert found == [], f"the public read carried {found}"

    def test_every_key_the_projection_removes_is_one_the_door_admits_to_removing(self) -> None:
        """The census both ways: nothing admitted stays in, and nothing disappears from the shape without being named."""
        client = _client("Ada Pair")
        _player(client)
        token = str(_open(client, sections=list(portfolio.SECTIONS))["token"])
        private = client.get(CV).json()
        public = _anonymous().get(f"{SHARE}/{token}").json()
        admitted = set(_anonymous().get(RULES).json()["share"]["private_keys_dropped"])
        removed = set(_walk_keys(private)) - set(_walk_keys(public))
        assert removed <= admitted, f"the projection hid {sorted(removed - admitted)} without publishing the rule"
        assert {"account", "visibility"} <= removed, f"nothing was actually dropped: {sorted(removed)}"

    def test_a_section_the_link_does_not_publish_is_absent_and_so_is_its_formula(self) -> None:
        """Withholding is a subtraction, so the answer must not describe what it withheld beyond naming it."""
        client = _client("Ada Subtraction")
        _player(client)
        token = str(_open(client, sections=["position"])["token"])
        body = _anonymous().get(f"{SHARE}/{token}").json()
        assert [section["section"] for section in body["sections"]] == ["position"]
        assert "training.minutes" not in body["formulas"], body["formulas"]
        assert [key for key in body["withheld"]] and all("section" in row for row in body["withheld"])

    def test_the_sections_a_link_publishes_are_printed_in_the_spec_s_order(self) -> None:
        client = _client("Ada Order")
        _player(client)
        token = str(_open(client, sections=["training", "position", "videos"])["token"])
        body = _anonymous().get(f"{SHARE}/{token}").json()
        expected = [key for key in portfolio.SECTIONS if key in {"training", "position", "videos"}]
        assert [section["section"] for section in body["sections"]] == expected
        assert body["published_sections"] == expected


class TestTheLinkIsALiveRead:
    def test_a_session_completed_after_the_link_opened_shows_through_the_link(self) -> None:
        """The anti-snapshot case: nothing was stored about the session, so the number can only be a re-read."""
        client = _client("Ada Live")
        _player(client)
        _complete_a_session(client)
        token = str(_open(client)["token"])
        before = _anonymous().get(f"{SHARE}/{token}").json()
        assert _figure(before, "training", "completed") == 1, before["sections"]
        _complete_a_session(client)
        after = _anonymous().get(f"{SHARE}/{token}").json()
        assert _figure(after, "training", "completed") == _figure(before, "training", "completed") + 1
        assert _figure(after, "training", "minutes") > _figure(before, "training", "minutes")
        mine = client.get(CV).json()
        assert _figure(mine, "training", "completed") == _figure(after, "training", "completed"), "the link and its owner must be the same read"

    def test_the_share_table_stores_no_figure_of_the_cv(self) -> None:
        table = Base.metadata.tables["cv_shares"]
        assert sorted(column.name for column in table.columns) == sorted(
            ["id", "user_id", "share_token", "sections", "created_at", "updated_at", "revoked_at"]
        ), [column.name for column in table.columns]

    def test_the_account_with_no_player_gets_a_link_of_ten_reasons_not_a_refusal(self) -> None:
        """§38's own rule, one door further out: an absent player is an answer, so a link over it is not an error."""
        client = _client("Ada Empty")
        token = str(_open(client, sections=list(portfolio.SECTIONS))["token"])
        body = _anonymous().get(f"{SHARE}/{token}").json()
        assert body["has_player"] is False
        assert len(body["sections"]) == len(portfolio.SECTIONS)
        assert body["counts"]["filled"] == 0, [row["section"] for row in body["sections"] if row["available"]]


class TestTheRulesRefuseBeforeATokenExists:
    def test_a_name_outside_the_ten_is_refused_and_no_link_was_minted(self) -> None:
        client = _client("Ada Refuse")
        _player(client)
        refused = client.post(SHARE, json={"sections": ["position", "wallet"]})
        assert refused.status_code == 422, refused.text
        detail = refused.json()["detail"]
        assert detail["code"] == "section_unknown" and detail["unknown"] == ["wallet"]
        assert client.get(SHARES).json()["counts"]["opened"] == 0

    def test_a_minor_cannot_publish_the_videos_section_and_the_refusal_names_the_threshold(self) -> None:
        client = _client("Ada Minor")
        _player(client, age=academy.MINOR_AGE - 1)
        refused = client.post(SHARE, json={"sections": ["position", "videos"]})
        assert refused.status_code == 422, refused.text
        detail = refused.json()["detail"]
        assert detail["code"] == "minor_section_blocked"
        assert detail["threshold"] == academy.MINOR_AGE and detail["age"] == academy.MINOR_AGE - 1
        assert detail["blocked"] == ["videos"] and "videos" not in detail["publishable"]

    def test_an_adult_publishes_the_same_section_the_minor_was_refused(self) -> None:
        """The other side of the guard: without this case the refusal could be firing for everybody."""
        client = _client("Ada Adult")
        _player(client, age=academy.MINOR_AGE)
        record = _open(client, sections=["videos"])
        assert record["sections"] == ["videos"]
        assert _anonymous().get(f"{SHARE}/{record['token']}").json()["counts"]["sections"] == 1

    def test_the_threshold_this_tier_enforces_is_the_academy_s_constant_not_a_copy(self) -> None:
        assert sharing.MINOR_AGE is academy.MINOR_AGE

    def test_an_empty_section_list_is_an_answer_and_not_a_refusal(self) -> None:
        client = _client("Ada None")
        _player(client)
        record = _open(client, sections=[])
        assert record["sections"] == [] and record["withheld"] == list(portfolio.SECTIONS)
        body = _anonymous().get(f"{SHARE}/{record['token']}").json()
        assert body["sections"] == [] and body["counts"]["sections"] == 0


class TestTheDoors:
    def test_every_code_this_tier_answers_with_is_registered_and_none_of_them_is_a_403(self) -> None:
        for code in sharing.REFUSALS:
            assert code in answers.ANSWERS, f"{code} is answered by a fall-through, not by a registration"
            assert answers.ANSWERS[code] != 403, "403 is reserved for insufficient_role project-wide"
        assert sharing.FORBIDDEN_CODES == frozenset()
        assert answers.published(sharing.REFUSALS) == {code: answers.ANSWERS[code] for code in sharing.REFUSALS}

    def test_the_rules_door_publishes_the_share_rules_that_the_service_enforces(self) -> None:
        body = _anonymous().get(RULES).json()
        assert body["share"]["publishable"] == list(portfolio.SECTIONS)
        assert body["share"]["minor_blocked"] == ["videos"], "the door mirrors the service's list, so this is the independent witness"
        assert body["share"]["minor_age"] == academy.MINOR_AGE
        assert sorted(body["share"]["private_keys_dropped"]) == sorted(FORBIDDEN_KEYS)
        assert set(body["refusal_answers"]) >= set(sharing.REFUSALS) | set(portfolio.REFUSALS)

    def test_the_service_and_this_file_agree_on_what_is_private(self) -> None:
        """The census above reads the list this file typed, not the service's, so this is the pin that makes an
        emptied or extended `PRIVATE_KEYS` a red rather than a quieter pass."""
        assert set(sharing.PRIVATE_KEYS) == set(FORBIDDEN_KEYS), "the projection's subtraction and its census drifted"

    def test_all_three_outputs_the_spec_permits_now_name_a_door_that_exists(self) -> None:
        """§38 permits three outputs. Each public sentence must name a door the tier actually declares."""
        body = _anonymous().get(RULES).json()
        paths = {row["path"] for row in body["routes"]}
        for key in ("public_player_profile", "share_link", "pdf"):
            sentence = body["public_outputs"][key]
            assert "not in this build" not in sentence, sentence
            assert any(path in sentence for path in paths), f"{key} names no door this tier actually declares: {sentence}"
        assert "/portfolio/cv.pdf" in body["public_outputs"]["pdf"]


def _figure(payload: dict[str, Any], section: str, name: str) -> Any:
    for row in payload["sections"]:
        if row["section"] == section:
            return row.get("figures", {}).get(name)
    return None
