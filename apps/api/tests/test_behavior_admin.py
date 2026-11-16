"""The beacon door: public, minimal, shape-checked, and read by the admin console."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator[Session]:
    with SessionLocal() as live:
        from app.models import PageView

        live.execute(PageView.__table__.delete())
        live.commit()
        yield live
        live.execute(PageView.__table__.delete())
        live.commit()


class TestTelemetryPageView:
    def test_a_good_beacon_writes_one_row(self, client, session) -> None:  # type: ignore[no-untyped-def]
        response = client.post(f"{API}/telemetry/page-view", json={
            "session_ref": "abcdefghij1234567890abcdef",
            "path": "/world",
            "dwell_ms": 4321,
            "bounced": False,
        })
        assert response.status_code == 204
        from app.models import PageView

        rows = session.execute(select(PageView)).scalars().all()
        assert len(rows) == 1
        assert rows[0].seeded is False
        assert rows[0].bounced is False
        assert rows[0].dwell_ms == 4321

    def test_the_path_is_shape_checked(self, client) -> None:  # type: ignore[no-untyped-def]
        for bad in ("//world", "world", "javascript:alert(1)", "/a b", "/%0d%0a", ""):
            response = client.post(f"{API}/telemetry/page-view", json={
                "session_ref": "abcdefghij1234567890abcdef",
                "path": bad,
                "dwell_ms": 1,
                "bounced": True,
            })
            assert response.status_code in (422,), (bad, response.status_code)

    def test_the_session_ref_is_shape_checked(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.post(f"{API}/telemetry/page-view", json={
            "session_ref": "short!",
            "path": "/world",
            "dwell_ms": 1,
            "bounced": True,
        })
        assert response.status_code == 422


class TestAdminBehavior:
    def test_the_passphrase_is_required(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/admin/behavior").status_code == 401
        assert client.get(f"{API}/admin/behavior", headers={"x-admin-passphrase": "wrong"}).status_code == 401

    def test_the_console_answers_with_the_passphrase(self, client, session) -> None:  # type: ignore[no-untyped-def]
        from app.models import PageView

        for path, dwell, bounced in [("/", 3000, True), ("/world", 12000, False), ("/tutorial", 30000, False)]:
            session.add(PageView(session_ref="seedabc12345def67890ab", path=path, dwell_ms=dwell, bounced=bounced, seeded=True))
        session.commit()

        response = client.get(f"{API}/admin/behavior", headers={"x-admin-passphrase": "123"})
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["totals"]["views"] == 3
        assert body["totals"]["sessions"] == 1
        assert body["source_note"]["seeded_views"] == 3
        assert body["source_note"]["real_views"] == 0
        assert len(body["daily"]) == 90
        assert body["funnels"], "the console prints funnels"
        assert "recommendations" in body
        assert body["model"]["calls_in_window"] >= 0

    def test_the_window_is_clamped(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/admin/behavior?window_days=7", headers={"x-admin-passphrase": "123"})
        assert response.status_code == 200
        assert response.json()["window_days"] == 7
        assert len(response.json()["daily"]) == 7

    def test_the_seed_does_not_count_as_organic(self, client, session) -> None:  # type: ignore[no-untyped-def]
        from app.models import PageView

        session.add(PageView(session_ref="organic1abc123def456ghi", path="/", dwell_ms=100, bounced=True, seeded=False))
        session.add(PageView(session_ref="organic1abc123def456ghi", path="/world", dwell_ms=9000, bounced=False, seeded=False))
        session.add(PageView(session_ref="seededxyz123abc456def", path="/world", dwell_ms=9000, bounced=False, seeded=True))
        session.commit()

        response = client.get(f"{API}/admin/behavior?window_days=90", headers={"x-admin-passphrase": "123"})
        body = response.json()
        assert body["source_note"]["real_views"] == 2
        assert body["source_note"]["seeded_views"] == 1
        assert body["source_note"]["real_sessions"] == 1
