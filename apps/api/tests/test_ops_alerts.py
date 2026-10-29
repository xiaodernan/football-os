"""Operator alerts: the cost ceiling tells somebody without being asked (M13 Phase 6 item 21).

The advisor's monthly block names a breach on a page; these cases hold the part that leaves the page. Each one
plants ledger rows and lets the sweep derive the month, because the alert is supposed to be a fact about
`model_calls` rather than about a payload: the ceiling, the pace, the dedupe key and the money in the sentence all
move when the rows move.

Delivery is exercised against a real local HTTP server, because the claim under test is what a receiver got --
the bytes, the signature over those bytes, and the row's record of the answer -- not that a mocked client was
called. Retries point at a closed port, which is the honest shape of a receiver that is down.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models import ModelCall, OpsAlert
from app.services import ops_alerts


@pytest.fixture()
def session() -> Iterator[Session]:
    """A ledger this file owns, and the two settings the sweep reads returned to their defaults."""
    original_url = settings.ops_alert_webhook_url
    original_ceiling = settings.ai_monthly_ceiling_usd
    object.__setattr__(settings, "ops_alert_webhook_url", "")
    object.__setattr__(settings, "ai_monthly_ceiling_usd", 0.0)
    row = SessionLocal()
    try:
        row.query(OpsAlert).delete()
        row.query(ModelCall).delete()
        row.commit()
        yield row
    finally:
        row.query(OpsAlert).delete()
        row.query(ModelCall).delete()
        row.commit()
        row.close()
        object.__setattr__(settings, "ops_alert_webhook_url", original_url)
        object.__setattr__(settings, "ai_monthly_ceiling_usd", original_ceiling)


@contextmanager
def _settings(**values: Any) -> Iterator[None]:
    originals = {name: getattr(settings, name) for name in values}
    try:
        for name, value in values.items():
            object.__setattr__(settings, name, value)
        yield
    finally:
        for name, value in originals.items():
            object.__setattr__(settings, name, value)


def _call(db: Session, *, cost: float = 1.0, when: datetime | None = None) -> ModelCall:
    row = ModelCall(
        id=f"mc_{uuid4().hex[:12]}",
        provider="openai",
        model="gpt-4o-mini",
        feature="knowledge_answer",
        user_id=None,
        input_tokens=100,
        output_tokens=50,
        reasoning_tokens=0,
        latency_ms=1,
        estimated_cost_usd=cost,
        actual_cost_usd=cost,
        success=True,
        demo_mode=False,
        created_at=when or datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class _Sink:
    """A receiver that records what it was sent and answers 204."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        sink = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - the base class names the verb
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                sink.requests.append(
                    {
                        "path": self.path,
                        "body": body,
                        "signature": self.headers.get("X-Football-Alert-Signature"),
                        "alert_header": self.headers.get("X-Football-Alert-Id"),
                    }
                )
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args: Any) -> None:  # the test output is not the server's log
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}/alerts"

    def start(self) -> _Sink:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture()
def sink() -> Iterator[_Sink]:
    server = _Sink().start()
    try:
        yield server
    finally:
        server.stop()


def _raise_warning(session: Session) -> None:
    """A month that is over its pace on day one: $4 spent, $10 ceiling, 31 days to the month."""
    with _settings(ai_monthly_ceiling_usd=10.0):
        _call(session, cost=4.0, when=datetime(2026, 10, 1, 9, tzinfo=UTC))
        ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 12, tzinfo=UTC))


class TestRaisingTheAlert:
    def test_a_month_with_no_ceiling_raises_nothing(self, session: Session) -> None:
        _call(session, cost=2.0)
        answer = ops_alerts.evaluate(session)
        assert answer["monthly"]["configured"] is False
        assert answer["raised"] == [] and answer["already_held"] == []
        assert session.query(OpsAlert).count() == 0, "no ceiling means no threshold, and no invented one"

    def test_a_month_over_its_pace_raises_a_warning(self, session: Session) -> None:
        with _settings(ai_monthly_ceiling_usd=10.0):
            _call(session, cost=4.0, when=datetime(2026, 10, 1, 9, tzinfo=UTC))
            answer = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 12, tzinfo=UTC))
        assert answer["monthly"]["projected_over"] is True and answer["monthly"]["exceeded"] is False
        assert len(answer["raised"]) == 1
        row = answer["raised"][0]
        assert row["level"] == "warning"
        assert row["dedupe_key"] == "cost_monthly_ceiling:2026-10:projected_over"
        assert row["state"] == "open"
        assert "projected $124.00 by month end" in row["summary"], "4.00 over 1 of 31 days projects to 124.00"
        assert row["detail"]["spend_usd"] == 4.0 and row["detail"]["trigger"].endswith(":projected_over")

    def test_a_month_over_its_ceiling_raises_a_critical_alert(self, session: Session) -> None:
        with _settings(ai_monthly_ceiling_usd=10.0):
            _call(session, cost=12.0, when=datetime(2026, 10, 1, 9, tzinfo=UTC))
            answer = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 12, tzinfo=UTC))
        assert len(answer["raised"]) == 1
        row = answer["raised"][0]
        assert row["level"] == "critical"
        assert row["dedupe_key"] == "cost_monthly_ceiling:2026-10:exceeded"
        assert "$12.00 spent in 2026-10 against a $10.00 ceiling, $2.00 over" == row["summary"]

    def test_the_same_condition_is_one_row_however_many_sweeps(self, session: Session) -> None:
        with _settings(ai_monthly_ceiling_usd=10.0):
            _call(session, cost=4.0, when=datetime(2026, 10, 1, 9, tzinfo=UTC))
            first = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 12, tzinfo=UTC))
            second = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 13, tzinfo=UTC))
        assert len(first["raised"]) == 1
        assert second["raised"] == [] and second["already_held"] == [first["raised"][0]["alert"]]
        assert session.query(OpsAlert).count() == 1, "one condition, one row"

    def test_a_pace_breach_and_a_ceiling_breach_are_two_rows(self, session: Session) -> None:
        with _settings(ai_monthly_ceiling_usd=10.0):
            _call(session, cost=4.0, when=datetime(2026, 10, 1, 9, tzinfo=UTC))
            ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 12, tzinfo=UTC))
            _call(session, cost=8.0, when=datetime(2026, 10, 1, 13, tzinfo=UTC))
            second = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 14, tzinfo=UTC))
        assert len(second["raised"]) == 1 and second["raised"][0]["level"] == "critical"
        rows = session.query(OpsAlert).order_by(OpsAlert.created_at.asc()).all()
        assert [row.level for row in rows] == ["warning", "critical"], "the pace warning and the breach are two facts"

    def test_last_month_s_spend_is_not_this_month_s_alert(self, session: Session) -> None:
        with _settings(ai_monthly_ceiling_usd=10.0):
            _call(session, cost=50.0, when=datetime(2026, 9, 15, 9, tzinfo=UTC))
            answer = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 12, tzinfo=UTC))
        assert answer["monthly"]["spend_usd"] == 0.0
        assert answer["raised"] == [] and session.query(OpsAlert).count() == 0

    def test_the_sweep_publishes_the_arithmetic_and_its_limit(self, session: Session) -> None:
        answer = ops_alerts.evaluate(session)
        assert answer["formula"].startswith("an alert is raised once per (kind, month, condition)")
        assert "model_calls" in answer["limitation"] and "attempt" in answer["limitation"]


class TestDelivery:
    def test_without_a_webhook_the_ledger_is_the_channel(self, session: Session) -> None:
        _raise_warning(session)
        row = session.query(OpsAlert).one()
        assert row.delivery_channel == "recorded"
        assert row.delivered_at is None and row.delivery_attempts == 0
        listed = ops_alerts.list_alerts(session)
        assert listed["channel"] == "recorded"
        assert listed["pending_delivery"] == 0, "a recorded alert is not a failed delivery waiting to retry"
        assert "set OPS_ALERT_WEBHOOK_URL" in listed["note"]

    def test_a_webhook_receives_the_signed_payload_and_the_row_records_it(self, session: Session, sink: _Sink) -> None:
        with _settings(ops_alert_webhook_url=sink.url):
            _raise_warning(session)
        assert len(sink.requests) == 1
        sent = sink.requests[0]
        expected = hmac.new(settings.app_secret.encode("utf-8"), sent["body"], hashlib.sha256).hexdigest()
        assert sent["signature"] == f"sha256={expected}", "the receiver can tell this POST from a stranger's"
        payload = json.loads(sent["body"])
        row = session.query(OpsAlert).one()
        assert payload["alert"] == row.id and sent["alert_header"] == row.id
        assert payload["level"] == "warning" and payload["month"] == "2026-10"
        assert payload["summary"] == row.summary and payload["signature_version"] == 1
        assert row.delivered_at is not None and row.delivery_attempts == 1 and row.delivery_error is None
        assert row.delivery_channel == "webhook"

    def test_a_delivered_alert_is_not_sent_again(self, session: Session, sink: _Sink) -> None:
        with _settings(ops_alert_webhook_url=sink.url):
            _raise_warning(session)
            second = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 13, tzinfo=UTC))
        assert len(sink.requests) == 1, "a sweep is not a reason to page twice"
        assert second["delivery"]["attempted"] == 0 and second["delivery"]["pending"] == 0

    def test_a_dead_receiver_is_retried_then_left_on_the_ledger(self, session: Session) -> None:
        with _settings(ops_alert_webhook_url="http://127.0.0.1:9/alerts"):
            _raise_warning(session)
            row = session.query(OpsAlert).one()
            assert row.delivered_at is None and row.delivery_attempts == 1 and row.delivery_error
            for _ in range(ops_alerts.MAX_DELIVERY_ATTEMPTS + 2):
                ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 13, tzinfo=UTC))
        session.refresh(row)
        assert row.delivery_attempts == ops_alerts.MAX_DELIVERY_ATTEMPTS, "a dead receiver stops being retried"
        assert row.delivered_at is None and row.delivery_error
        listed = ops_alerts.list_alerts(session)
        assert listed["pending_delivery"] == 0, "the ceiling is visible on the same row as the last error"

    def test_a_channel_configured_later_delivers_the_recorded_row(self, session: Session, sink: _Sink) -> None:
        _raise_warning(session)
        assert session.query(OpsAlert).one().delivered_at is None
        with _settings(ops_alert_webhook_url=sink.url):
            answer = ops_alerts.evaluate(session, now=datetime(2026, 10, 1, 13, tzinfo=UTC))
        assert answer["delivery"]["delivered"] == 1 and len(sink.requests) == 1
        assert session.query(OpsAlert).one().delivered_at is not None


class TestTheDoors:
    def test_the_list_door_answers_the_ledger(self, session: Session, admin_client: TestClient) -> None:
        _raise_warning(session)
        resp = admin_client.get("/api/v1/metrics/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"items", "total", "open", "acknowledged", "pending_delivery", "channel", "formula", "note"}
        assert body["total"] == 1 and body["open"] == 1 and body["acknowledged"] == 0
        assert body["items"][0]["dedupe_key"] == "cost_monthly_ceiling:2026-10:projected_over"

    def test_the_check_door_sweeps_and_shows_its_work(self, session: Session, admin_client: TestClient) -> None:
        with _settings(ai_monthly_ceiling_usd=10.0):
            _call(session, cost=12.0)
            resp = admin_client.post("/api/v1/metrics/alerts/check")
        assert resp.status_code == 200
        body = resp.json()
        assert body["monthly"]["exceeded"] is True
        assert len(body["raised"]) == 1 and body["raised"][0]["level"] == "critical"
        again = admin_client.post("/api/v1/metrics/alerts/check")
        assert again.json()["raised"] == [], "the door is a sweep, not a generator of duplicates"

    def test_acknowledging_records_who_read_it(self, session: Session, admin_client: TestClient) -> None:
        _raise_warning(session)
        alert = session.query(OpsAlert).one()
        resp = admin_client.post(f"/api/v1/metrics/alerts/{alert.id}/acknowledge")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "acknowledged" and body["acknowledged_by"] and body["acknowledged_at"]
        session.refresh(alert)
        assert alert.state == "acknowledged"
        listed = admin_client.get("/api/v1/metrics/alerts?state=open").json()
        assert listed["items"] == [] and listed["open"] == 0 and listed["acknowledged"] == 1
        assert admin_client.get("/api/v1/metrics/alerts?state=nonsense").status_code == 422

    def test_an_unknown_alert_is_absent(self, admin_client: TestClient) -> None:
        resp = admin_client.post("/api/v1/metrics/alerts/alert_nobody/acknowledge")
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "no_such_alert"

    def test_every_door_asks_for_the_operator_standing(self, session: Session, auth_client: TestClient) -> None:
        _raise_warning(session)
        alert = session.query(OpsAlert).one()
        assert auth_client.get("/api/v1/metrics/alerts").status_code == 403
        assert auth_client.post("/api/v1/metrics/alerts/check").status_code == 403
        assert auth_client.post(f"/api/v1/metrics/alerts/{alert.id}/acknowledge").status_code == 403
        anonymous = TestClient(app)
        assert anonymous.get("/api/v1/metrics/alerts").status_code == 401
        assert anonymous.post("/api/v1/metrics/alerts/check").status_code == 401
        assert anonymous.post(f"/api/v1/metrics/alerts/{alert.id}/acknowledge").status_code == 401
