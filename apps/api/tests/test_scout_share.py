"""M7 §24 + §38 — a report link that answers without an account, and closes when its owner says so.

The claim this file measures is the one the tier makes: the link stores a *question*, not a report. So:

* the public read is compared field by field with `POST /scout/report` for the same question — every one of §24's
  thirteen fields has to be the same object, because both are the same live read;
* the link is walked as a stranger: no session, and no key anywhere in the payload that names an account;
* the token is treated as the capability it is: an unknown one, a revoked one and somebody else's answer the same
  404, and a second revocation is the 409 that says the door was already shut;
* the same question asked twice returns the same live token, including when the player is spelled by id the second
  time — the row stores the canonical slug the report read;
* a career deleted after the link was minted leaves `team_fit: null` and `career_available: false` rather than an
  error, which is the same answer the private door gives when no career is named;
* a player the stored pool no longer holds answers `share_subject_gone`, not "no such link";
* the live-link ceiling is exercised by moving it to one with `monkeypatch`, so the refusal names both figures
  without the suite minting twenty reports to reach it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.cache import _response_cache, response_cache_key
from app.core.db import SessionLocal
from app.models import Career, RealPlayer, ScoutReportShare, Team
from app.services.scouting import sharing as sharing_module
from app.services.scouting.report import REPORT_FIELDS
from app.services.world import sync_world, world_ready

PASSWORD = "strong-pass-1234"
CAREERS = "/api/v1/careers"
REPORT = "/api/v1/scout/report"
SHARE = "/api/v1/scout/share"
SHARES = "/api/v1/scout/shares"

#: Keys that would mean an account leaked into a public payload. `club` legitimately carries a club's name and
#: slug, so the comparison is against exact key names rather than every appearance of the word.
PRIVATE_KEYS = frozenset({"user_id", "owner_id", "email", "display_name", "password_hash", "account"})


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world with the two rows every link in this file is minted about."""
    session = SessionLocal()
    try:
        sync_world(session)
        rows = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(rows) > 100 and world_ready(session)
        club = str(session.scalars(select(Team.id).order_by(Team.overall, Team.slug).limit(1)).one())
        observed = max(rows, key=lambda row: (int(row.appearances or 0), row.slug))
        other = next(row for row in rows if row.slug != observed.slug and row.position == observed.position)
        return {
            "club_id": club,
            "player": observed.slug,
            "player_id": observed.id,
            "other": other.slug,
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Any]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _app() -> Any:
    from app.main import app

    return app


def _register(client: TestClient) -> dict[str, Any]:
    """A fresh account, so every ledger count in this file starts at zero."""
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"scout-share-{uuid4().hex[:8]}@example.test",
            "password": PASSWORD,
            "display_name": "Share Scout",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert registered.status_code == 201, registered.text
    client.headers.update({"Authorization": f"Bearer {registered.json()['access_token']}"})
    return registered.json()


def _career(client: TestClient, world: dict[str, Any]) -> str:
    created = client.post(
        CAREERS,
        json={
            "club": world["club_id"],
            "manager_name": "Share Scout",
            "philosophy": "balanced",
            "budget": 4_000_000,
            "objectives": [{"kind": "wins", "target": 1, "label": "win once"}],
        },
    )
    assert created.status_code == 200, created.text
    return str(created.json()["career"]["slug"])


def _keys(node: Any) -> Iterator[str]:
    """Every key in a JSON payload, so an identity field has nowhere to hide."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


class TestThePublicRead:
    def test_a_link_answers_a_stranger_and_agrees_with_the_private_report(self, world: dict[str, Any]) -> None:
        question = {"player": world["player"], "role": "ST", "compare_to": world["other"]}
        with TestClient(_app()) as client:
            _register(client)
            minted = client.post(SHARE, json=question)
            assert minted.status_code == 200, minted.text
            body = minted.json()
            token = str(body["token"])
            assert body["created"] is True
            assert len(token) == 32 and all(character in "0123456789abcdef" for character in token)
            private = client.post(REPORT, json=question)
            assert private.status_code == 200, private.text
        with TestClient(_app()) as stranger:
            public = stranger.get(f"/api/v1/scout/shared/{token}")
        assert public.status_code == 200, public.text
        payload = public.json()
        assert payload["demo_data"] is True
        assert payload["asked_for"] == {"player": world["player"], "role": "ST", "career": None, "compare_to": world["other"], "round_index": None}
        assert payload["shared"]["career_named"] is False
        assert payload["shared"]["career_available"] is False
        assert payload["shared"]["player_slug"] == world["player"]
        assert payload["shared"]["opened_at"] == body["opened_at"]
        assert not PRIVATE_KEYS & set(_keys(payload)), "a public report must not carry an account's own keys"
        for field in REPORT_FIELDS:
            assert payload[field] == private.json()[field], f"{field} drifted between the public and private reads"

    def test_an_unknown_token_is_the_same_absence(self, world: dict[str, Any]) -> None:
        with TestClient(_app()) as stranger:
            answer = stranger.get("/api/v1/scout/shared/" + "0" * 32)
        assert answer.status_code == 404, answer.text
        assert answer.json()["detail"]["code"] == "no_such_share"


class TestTheLedger:
    def test_the_same_question_returns_the_same_live_token_even_spelled_by_id(self, world: dict[str, Any]) -> None:
        question = {"player": world["player"], "role": "ST"}
        with TestClient(_app()) as client:
            _register(client)
            first = client.post(SHARE, json=question)
            assert first.status_code == 200, first.text
            second = client.post(SHARE, json=question)
            assert second.status_code == 200, second.text
            by_id = client.post(SHARE, json={"player": world["player_id"], "role": "ST"})
            assert by_id.status_code == 200, by_id.text
        opened = first.json()
        assert second.json()["created"] is False
        assert second.json()["token"] == opened["token"]
        assert second.json()["opened_at"] == opened["opened_at"]
        assert by_id.json()["token"] == opened["token"], "a player spelled by id is the same player"
        assert by_id.json()["created"] is False

    def test_a_different_question_mints_a_new_live_token(self, world: dict[str, Any]) -> None:
        with TestClient(_app()) as client:
            _register(client)
            first = client.post(SHARE, json={"player": world["player"], "role": "ST"})
            second = client.post(SHARE, json={"player": world["player"], "role": "AM"})
            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert second.json()["token"] != first.json()["token"]
            ledger = client.get(SHARES)
        assert ledger.status_code == 200, ledger.text
        assert ledger.json()["counts"] == {"opened": 2, "live": 2, "revoked": 0}
        assert ledger.json()["max_live"] == sharing_module.MAX_LIVE
        assert {row["token"] for row in ledger.json()["shares"]} == {first.json()["token"], second.json()["token"]}

    def test_a_bad_role_is_refused_before_a_token_exists(self, world: dict[str, Any]) -> None:
        with TestClient(_app()) as client:
            _register(client)
            refused = client.post(SHARE, json={"player": world["player"], "role": "INVERTED"})
            ledger = client.get(SHARES)
        assert refused.status_code == 422, refused.text
        assert refused.json()["detail"]["code"] == "unknown_role"
        assert ledger.json()["counts"] == {"opened": 0, "live": 0, "revoked": 0}

    def test_the_live_ceiling_refuses_with_both_figures(self, world: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sharing_module, "MAX_LIVE", 1)
        with TestClient(_app()) as client:
            _register(client)
            first = client.post(SHARE, json={"player": world["player"], "role": "ST"})
            second = client.post(SHARE, json={"player": world["player"], "role": "AM"})
        assert first.status_code == 200, first.text
        assert second.status_code == 409, second.text
        detail = second.json()["detail"]
        assert detail["code"] == "too_many_shares"
        assert detail["live"] == 1 and detail["max_live"] == 1


class TestClosingTheDoor:
    def test_revoking_closes_the_read_and_a_second_revocation_says_so(self, world: dict[str, Any]) -> None:
        with TestClient(_app()) as client:
            _register(client)
            minted = client.post(SHARE, json={"player": world["player"]}).json()
            closed = client.delete(f"/api/v1/scout/share/{minted['token']}")
            again = client.delete(f"/api/v1/scout/share/{minted['token']}")
            with TestClient(_app()) as stranger:
                public = stranger.get(f"/api/v1/scout/shared/{minted['token']}")
            ledger = client.get(SHARES)
        assert closed.status_code == 200, closed.text
        assert closed.json()["live"] is False
        assert closed.json()["token"] is None
        assert again.status_code == 409, again.text
        assert again.json()["detail"]["code"] == "share_already_revoked"
        assert public.status_code == 404, public.text
        assert public.json()["detail"]["code"] == "no_such_share"
        row = next(item for item in ledger.json()["shares"] if item["share"] == minted["share"])
        assert row["token"] is None and row["live"] is False and row["revoked_at"] is not None
        assert ledger.json()["counts"] == {"opened": 1, "live": 0, "revoked": 1}

    def test_closing_a_link_retires_the_public_answer_the_cache_still_holds(self, world: dict[str, Any]) -> None:
        """The measured bug: the row said closed while the door answered 200 for the rest of the TTL.

        The test suite runs with the response-cache middleware switched off, so the warm entry is planted exactly
        as `cached_response_for` would store one — the public key, the empty identity — and the DELETE has to take
        it away. The row and the door are checked afterwards, because a cache that agreed with a shut door would
        still be wrong if the row had stayed open.
        """
        with TestClient(_app()) as client:
            _register(client)
            minted = client.post(SHARE, json={"player": world["player"]}).json()
            token = str(minted["token"])
            path = f"/api/v1/scout/shared/{token}"
            key = response_cache_key(path, "")
            _response_cache.set(key, {"body": "{}", "status_code": 200, "headers": [], "media_type": "application/json"})
            assert _response_cache.get(key) is not None, "the fixture has to start warm"
            closed = client.delete(f"/api/v1/scout/share/{token}")
            assert _response_cache.get(key) is None, "closing the link must retire the anonymous answer the cache holds"
            assert _response_cache.drop_public_path(path) == 0, "and there must be nothing left to sweep"
            with TestClient(_app()) as stranger:
                public = stranger.get(path)
            ledger = client.get(SHARES)
        assert closed.status_code == 200, closed.text
        assert closed.json()["live"] is False and closed.json()["token"] is None
        assert public.status_code == 404, public.text
        assert public.json()["detail"]["code"] == "no_such_share"
        assert ledger.json()["counts"] == {"opened": 1, "live": 0, "revoked": 1}

    def test_somebody_elses_link_is_not_this_accounts_to_close(self, world: dict[str, Any]) -> None:
        with TestClient(_app()) as owner:
            _register(owner)
            minted = owner.post(SHARE, json={"player": world["player"]}).json()
        with TestClient(_app()) as other:
            _register(other)
            refused = other.delete(f"/api/v1/scout/share/{minted['token']}")
            stranger_ledger = other.get(SHARES)
        with TestClient(_app()) as stranger:
            still_open = stranger.get(f"/api/v1/scout/shared/{minted['token']}")
        assert refused.status_code == 404, refused.text
        assert refused.json()["detail"]["code"] == "no_such_share"
        assert stranger_ledger.json()["counts"]["opened"] == 0
        assert still_open.status_code == 200, still_open.text


class TestTheQuestionAges:
    def test_a_deleted_career_leaves_the_fit_empty_and_the_link_alive(self, world: dict[str, Any]) -> None:
        with TestClient(_app()) as client:
            _register(client)
            slug = _career(client, world)
            minted = client.post(SHARE, json={"player": world["player"], "career": slug})
            assert minted.status_code == 200, minted.text
        session = SessionLocal()
        try:
            career = session.scalar(select(Career).where(Career.slug == slug))
            assert career is not None
            session.delete(career)
            session.commit()
        finally:
            session.close()
        with TestClient(_app()) as stranger:
            public = stranger.get(f"/api/v1/scout/shared/{minted.json()['token']}")
        assert public.status_code == 200, public.text
        payload = public.json()
        assert payload["asked_for"]["career"] == slug
        assert payload["shared"]["career_named"] is True
        assert payload["shared"]["career_available"] is False
        assert payload["team_fit"] is None, "a career the world no longer holds cannot keep a fit figure"

    def test_a_player_the_pool_lost_says_the_subject_is_gone(self, world: dict[str, Any], session: Any) -> None:
        with TestClient(_app()) as client:
            _register(client)
            minted = client.post(SHARE, json={"player": world["player"]}).json()
        row = session.scalar(select(ScoutReportShare).where(ScoutReportShare.share_token == str(minted["token"])))
        assert row is not None
        row.player = "a-player-that-left-the-pool"
        session.commit()
        with TestClient(_app()) as stranger:
            public = stranger.get(f"/api/v1/scout/shared/{minted['token']}")
        assert public.status_code == 404, public.text
        detail = public.json()["detail"]
        assert detail["code"] == "share_subject_gone"
        assert detail["player"] == "a-player-that-left-the-pool"
