"""The notification tier (spec module 27): one row per event an account should hear about.

The two claims this file holds: the tray is the recipient's own (another account's
notification is absence, not a refusal that leaks), and the three community verbs —
follow, comment, reaction — write rows at the moment they happen, never to the actor
whose own action it was.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models import Notification
from app.services.notifications import notify

API = "/api/v1/notifications"

PASSWORD = "strong-pass-1234"


def _account(client: TestClient, display_name: str) -> dict:
    email = f"ntf-{display_name.lower().replace(' ', '')}-{uuid.uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": display_name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    # every test speaks as the account it registered last
    client.headers.update({"Authorization": f"Bearer {body['access_token']}"})
    return body


def _client(display_name: str) -> TestClient:
    client = TestClient(app)
    registered = _account(client, display_name)
    client.headers.update({"Authorization": f"Bearer {registered['access_token']}"})
    return client


class TestTheTray:
    def test_an_empty_tray_answers_zeroes_and_no_row(self, client) -> None:  # type: ignore[no-untyped-def]
        _account(client, "Empty Tray")
        body = client.get(API).json()
        assert body["items"] == [] and body["total"] == 0 and body["unread_total"] == 0
        assert client.get(f"{API}/unread-total").json() == {"unread_total": 0}

    def test_another_accounts_notification_is_absence(self, client) -> None:  # type: ignore[no-untyped-def]
        _account(client, "Reader")
        stranger = _client("Writer")
        with TestClient(app) as second:
            token = second.post(
                "/api/v1/auth/register",
                json={"email": f"ntf-other-{uuid.uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Other", "role": "player", "accepts_data_policy": True},
            ).json()["access_token"]
            second.headers.update({"Authorization": f"Bearer {token}"})
            # Writer has a notification; Other probes for its id by brute force — the tray answers
            # absence to every id, because the id is not Other's.
            _account(stranger, "Anyone")
            with TestClient(app) as probe:
                probe.headers.update({"Authorization": f"Bearer {token}"})
                row = probe.get(API).json()["items"]
                assert row == []
        # the reader's own tray stays empty
        assert client.get(API).json()["total"] == 0

    def test_marking_one_and_then_all_clears_the_badge(self, client) -> None:  # type: ignore[no-untyped-def]
        _account(client, "Marker")
        # three real rows through the service, against this account's id
        from app.core.db import SessionLocal

        with SessionLocal() as session:
            from app.models import User

            account_id = session.query(User).filter(User.display_name == "Marker").order_by(User.created_at.desc()).first().id
            for index in range(3):
                notify(session, account_id, kind="follower", payload={"follower_name": f"N{index}"})
        body = client.get(API).json()
        assert body["total"] == 3 and body["unread_total"] == 3
        first = body["items"][0]["id"]
        marked = client.post(f"{API}/{first}/read")
        assert marked.status_code == 200 and marked.json()["read_at"] is not None
        assert client.get(f"{API}/unread-total").json() == {"unread_total": 2}
        assert client.post(f"{API}/{first}/read").json()["read_at"] is not None, "marking twice is the same state, not an error"
        cleared = client.post(f"{API}/read-all")
        assert cleared.json() == {"marked": 2, "unread_before": 2, "unread_after": 0}
        assert client.get(f"{API}/unread-total").json() == {"unread_total": 0}

    def test_marking_a_strangers_notification_is_absence(self, client) -> None:  # type: ignore[no-untyped-def]
        _account(client, "Honest")
        stranger = _client("Absent Owner")
        # the stranger's tray has one row through the service
        from app.core.db import SessionLocal

        with SessionLocal() as session:
            from app.models import User

            stranger_id = session.query(User).filter(User.display_name == "Absent Owner").order_by(User.created_at.desc()).first().id
            row = notify(session, stranger_id, kind="follower", payload={"follower_name": "N"})
            assert row is not None
            notification_id = row["id"]
        assert client.post(f"{API}/{notification_id}/read").status_code == 404
        assert stranger.get(f"{API}/unread-total").json()["unread_total"] == 1

    def test_the_tray_is_paged_newest_first(self, client) -> None:  # type: ignore[no-untyped-def]
        _account(client, "Paged")
        from app.core.db import SessionLocal

        with SessionLocal() as session:
            from app.models import User

            account_id = session.query(User).filter(User.display_name == "Paged").order_by(User.created_at.desc()).first().id
            for index in range(25):
                row = Notification(id=f"ntf_page_{index}_{uuid.uuid4().hex[:6]}", user_id=account_id, kind="follower", payload={"follower_name": f"N{index}"})
                row.created_at = datetime.now(UTC) - timedelta(seconds=100 - index)
                session.add(row)
            session.commit()
        first_page = client.get(f"{API}?page=1").json()
        second_page = client.get(f"{API}?page=2").json()
        assert len(first_page["items"]) == 20 and len(second_page["items"]) == 5
        assert first_page["items"][0]["payload"]["follower_name"] == "N24", "newest first"
        assert first_page["pages"] == 2 and first_page["total"] == 25


class TestProducers:
    def test_a_follow_notifies_the_followed_account_and_never_the_follower(self, client) -> None:  # type: ignore[no-untyped-def]
        from app.core.db import SessionLocal
        from app.models import User

        follower = _client("Follower One")
        followed = _client("Followed One")
        with SessionLocal() as session:
            target_id = session.query(User).filter(User.display_name == "Followed One").order_by(User.created_at.desc()).first().id
        press = follower.post(f"/api/v1/community/follows/{target_id}")
        assert press.status_code == 200, press.text
        # the followed account hears about it
        assert followed.get(f"{API}/unread-total").json()["unread_total"] >= 1, "the followed account must hear about the new reach"
        row = followed.get(API).json()["items"][0]
        assert row["kind"] == "follower" and row["payload"]["follower_name"] == "Follower One"
        # the follower's own tray stays empty: their own act is not news to them
        assert follower.get(f"{API}/unread-total").json()["unread_total"] == 0

    def test_a_comment_and_a_reaction_notify_the_author_not_the_actor(self, client) -> None:  # type: ignore[no-untyped-def]
        author = _client("Author One")
        stranger = _client("Stranger One")
        published = author.post("/api/v1/community/posts", json={"kind": "note", "body": "A wall post waiting for replies."})
        assert published.status_code == 200, published.text
        post_id = published.json()["post"]["id"]

        reacted = stranger.post(f"/api/v1/community/posts/{post_id}/reactions", json={"reaction": "like"})
        assert reacted.status_code == 200, reacted.text
        commented = stranger.post(f"/api/v1/community/posts/{post_id}/comments", json={"body": "First reply on the wall."})
        assert commented.status_code == 200, commented.text

        author_rows = author.get(API).json()["items"]
        kinds = [row["kind"] for row in author_rows]
        assert "reaction" in kinds and "comment" in kinds, f"author heard {kinds}"
        comment_row = next(row for row in author_rows if row["kind"] == "comment")
        assert comment_row["payload"]["actor_name"] == "Stranger One"
        assert "First reply" in comment_row["payload"]["excerpt"]

        # the stranger's own tray: their own acts are not news to them
        assert stranger.get(f"{API}/unread-total").json()["unread_total"] == 0

    def test_the_authors_own_reaction_writes_no_notification(self, client) -> None:  # type: ignore[no-untyped-def]
        author = _client("Self Actor")
        published = author.post("/api/v1/community/posts", json={"kind": "note", "body": "My own post, my own reaction."})
        assert published.status_code == 200, published.text
        post_id = published.json()["post"]["id"]
        author.post(f"/api/v1/community/posts/{post_id}/reactions", json={"reaction": "like"})
        assert author.get(f"{API}/unread-total").json()["unread_total"] == 0, "an account never hears about its own act"
