"""M12: a trace backend that needs no collector, and a door that reads it back.

The observability claim this repository could not make was "no span has reached a real backend":
OpenTelemetry was wired with an OTLP exporter, and a host that runs no collector has nowhere to
send a span. The store is that backend - an ordinary OpenTelemetry exporter that writes each
finished span into the database - and this file is the gate for it.

Four claims, in the order they can be checked:

* **A span reaches the store.** A request through an instrumented app leaves rows in
  `request_spans`, and the door reads them back by trace id.
* **The tree is in the answer.** A child span names the span it hung from, so a reader can see
  the shape of the work rather than a flat list.
* **A store failure is not a request failure.** The exporter catches everything: a database that
  is down loses the spans, not the request.
* **The store is bounded.** An export deletes the rows older than the published seven-day window
  and keeps the younger ones, so a long-running instance does not accumulate traces forever.

The door asks for the platform's operator standing (`admin`), because a span carries the
request's concrete `http.target` and the store does not record whose request it was - an
authenticated player holding a trace id could otherwise read another account's path and
query string. A trace id nobody stored answers 404 for an operator - absence must not
confirm which ids exist - and every other account is refused before the lookup.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.span_store import SpanStoreExporter
from app.models import RequestSpan

PASSWORD = "TestPass1234!"


@pytest.fixture()
def store_on() -> Iterator[None]:
    """Turn the store on for the duration of a case, and put it back afterwards.

    The setting is on a frozen dataclass, so it is set the way the rest of the suite sets one
    (`object.__setattr__`), and it is put back in a `finally`: a case that leaves the store on
    would instrument the apps of every case that follows it, and the tracing gate's own "without
    an endpoint, tracing is a no-op" case would answer otherwise.
    """
    was = settings.trace_store_enabled
    object.__setattr__(settings, "trace_store_enabled", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "trace_store_enabled", was)


def _client() -> TestClient:
    from app.main import app

    client = TestClient(app)
    email = f"trace-store-{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Trace Store Tester",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"registration failed: {response.text}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _admin_client() -> TestClient:
    """An operator: the only standing that may read the store.

    The account is written straight to the database because the register door's `Literal`
    refuses `admin` by design; `test_authorization_census` holds that gap as a policy.
    """
    from app.core import security
    from app.main import app
    from app.models import User

    db = SessionLocal()
    try:
        row = User(
            id=security.new_public_id("usr"),
            email=f"trace-admin-{uuid4().hex[:8]}@example.test",
            password_hash=security.hash_password(PASSWORD),
            display_name="Trace Store Operator",
            role="admin",
            is_active=True,
        )
        db.add(row)
        db.commit()
        user_id = row.id
    finally:
        db.close()
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {security.create_access_token(user_id, 'admin')}"})
    return client


class TestTheStore:
    def test_a_finished_span_is_stored_with_its_own_timings(self, store_on: None) -> None:
        """The exporter writes a row a reader can use: the ids, the parent, the duration."""
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from app.core import tracing

        exporter = InMemorySpanExporter()
        provider = tracing.build_provider(None, SimpleSpanProcessor(exporter))
        assert provider is not None

        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/ping")
        def ping() -> dict[str, str]:
            return {"ok": "1"}

        tracing.instrument_fastapi(app, tracer_provider=provider)  # type: ignore[arg-type]
        with TestClient(app) as client:
            assert client.get("/ping").status_code == 200

        spans = exporter.get_finished_spans()
        assert spans, "the instrumented app produced no span at all"

        store = SpanStoreExporter(SessionLocal)
        result = store.export(spans)
        assert result.name == "SUCCESS", f"the store refused a batch of {len(spans)} spans"

        with SessionLocal() as db:
            rows = db.scalars(select(RequestSpan).order_by(RequestSpan.start_time)).all()
        assert rows, "the batch was reported as stored and nothing is in the table"
        row = rows[0]
        assert len(row.trace_id) == 32
        assert len(row.span_id) == 16
        assert row.name, "a stored span has no name"
        assert row.duration_ms >= 0
        assert row.start_time is not None and row.end_time is not None

    def test_a_child_span_names_the_span_it_hung_from(self, store_on: None) -> None:
        """The tree is stored, not rebuilt by the reader."""
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from app.core import tracing

        exporter = InMemorySpanExporter()
        provider = tracing.build_provider(None, SimpleSpanProcessor(exporter))

        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/outer")
        def outer() -> dict[str, str]:
            # The tracer comes from this test's provider, not the global one: a span on the
            # global provider would never reach this test's exporter.
            tracer = provider.get_tracer("store-test")
            with tracer.start_as_current_span("inner"):
                return {"ok": "1"}

        tracing.instrument_fastapi(app, tracer_provider=provider)  # type: ignore[arg-type]
        with TestClient(app) as client:
            assert client.get("/outer").status_code == 200

        spans = exporter.get_finished_spans()
        assert len(spans) >= 2, f"the request produced {len(spans)} span(s); a parent and a child were expected"
        store = SpanStoreExporter(SessionLocal)
        store.export(spans)

        with SessionLocal() as db:
            rows = db.scalars(select(RequestSpan)).all()
        by_name = {row.name: row for row in rows}
        assert "inner" in by_name, f"the child span was not stored: {sorted(by_name)}"
        assert "GET /outer" in by_name, f"the parent span was not stored: {sorted(by_name)}"
        assert by_name["inner"].parent_span_id == by_name["GET /outer"].span_id, (
            "the child span does not name its parent, so the tree has to be rebuilt by the reader"
        )

    def test_a_failing_store_never_raises_into_the_caller(self, store_on: None) -> None:
        """A trace backend that can take the API down is worse than no trace backend."""
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from app.core import tracing

        exporter = InMemorySpanExporter()
        provider = tracing.build_provider(None, SimpleSpanProcessor(exporter))

        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/ping")
        def ping() -> dict[str, str]:
            return {"ok": "1"}

        tracing.instrument_fastapi(app, tracer_provider=provider)  # type: ignore[arg-type]
        with TestClient(app) as client:
            assert client.get("/ping").status_code == 200

        spans = exporter.get_finished_spans()

        class BrokenSession:
            def __call__(self) -> Any:
                raise RuntimeError("the database is down")

        store = SpanStoreExporter(BrokenSession())  # type: ignore[arg-type]
        result = store.export(spans)
        assert result.name == "FAILURE", "a broken store reported success"
        store.shutdown()

    def test_an_export_prunes_spans_older_than_the_published_window(self, store_on: None) -> None:
        """The store is bounded, and the bound is the published seven days, not any prune.

        The two ages are literal on purpose: deriving them from `RETENTION` would keep this case
        green for whatever window the module was changed to, which is the drift it exists to
        catch. Eight days old is outside the window, six is inside; the span the exporter writes
        is the third row, so a prune that deletes everything fails on a different row than one
        that never runs.
        """
        from datetime import timedelta

        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from app.core import tracing

        now = _now()
        old_trace, kept_trace = "1" * 32, "2" * 32
        with SessionLocal() as db:
            for trace_id, span_id, age in (
                (old_trace, "1" * 16, timedelta(days=8)),
                (kept_trace, "2" * 16, timedelta(days=6)),
            ):
                start = now - age
                db.add(
                    RequestSpan(
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=None,
                        name="GET /aged",
                        kind="SERVER",
                        status="OK",
                        start_time=start,
                        end_time=start + timedelta(seconds=1),
                        duration_ms=1000,
                        attributes_json={},
                    )
                )
            db.commit()

        exporter = InMemorySpanExporter()
        provider = tracing.build_provider(None, SimpleSpanProcessor(exporter))
        assert provider is not None

        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/prune")
        def prune() -> dict[str, str]:
            return {"ok": "1"}

        tracing.instrument_fastapi(app, tracer_provider=provider)  # type: ignore[arg-type]
        with TestClient(app) as client:
            assert client.get("/prune").status_code == 200

        spans = exporter.get_finished_spans()
        assert spans, "the instrumented app produced no span to export"
        result = SpanStoreExporter(SessionLocal).export(spans)
        assert result.name == "SUCCESS", f"the store refused a batch of {len(spans)} spans"

        exported = {f"{span.get_span_context().trace_id:032x}" for span in spans}
        with SessionLocal() as db:
            stored = set(db.scalars(select(RequestSpan.trace_id)).all())
        assert old_trace not in stored, "an eight-day-old span survived an export; the store is not bounded"
        assert kept_trace in stored, "a six-day-old span was deleted with the expired ones"
        assert exported <= stored, f"the exported span(s) {sorted(exported - stored)} were not stored"


class TestTheDoor:
    def test_the_door_reads_a_stored_trace_back(self) -> None:
        client = _admin_client()
        with SessionLocal() as db:
            db.add(
                RequestSpan(
                    trace_id="a" * 32,
                    span_id="b" * 16,
                    parent_span_id=None,
                    name="GET /players",
                    kind="SERVER",
                    status="OK",
                    start_time=_now(),
                    end_time=_now(),
                    duration_ms=42,
                    attributes_json={"http.route": "/players"},
                )
            )
            db.add(
                RequestSpan(
                    trace_id="a" * 32,
                    span_id="c" * 16,
                    parent_span_id="b" * 16,
                    name="SELECT players",
                    kind="INTERNAL",
                    status="OK",
                    start_time=_now(),
                    end_time=_now(),
                    duration_ms=7,
                    attributes_json={},
                )
            )
            db.commit()

        response = client.get(f"/api/v1/traces/{'a' * 32}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["trace_id"] == "a" * 32
        assert body["span_count"] == 2
        names = [span["name"] for span in body["spans"]]
        assert "GET /players" in names and "SELECT players" in names
        child = next(span for span in body["spans"] if span["name"] == "SELECT players")
        assert child["parent_span_id"] == "b" * 16

    def test_an_unknown_trace_answers_404(self) -> None:
        client = _admin_client()
        response = client.get("/api/v1/traces/does-not-exist")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "no_such_trace"

    def test_a_player_is_refused_before_the_lookup(self) -> None:
        """A trace carries another request's concrete target, so the door is an operator's.

        The same id is read successfully by an admin afterwards: the refusal is the player's
        standing, not a disguised 404. The refusal runs before the lookup, so it answers the
        same way for an id that exists and one that never did.
        """
        trace_id = "d" * 32
        with SessionLocal() as db:
            db.add(
                RequestSpan(
                    trace_id=trace_id,
                    span_id="e" * 16,
                    parent_span_id=None,
                    name="GET /api/v1/share/boards/secret-share-token",
                    kind="SERVER",
                    status="OK",
                    start_time=_now(),
                    end_time=_now(),
                    duration_ms=12,
                    attributes_json={"http.target": "/api/v1/share/boards/secret-share-token"},
                )
            )
            db.commit()

        player = _client()
        refused = player.get(f"/api/v1/traces/{trace_id}")
        assert refused.status_code == 403, refused.text
        detail = refused.json()["detail"]
        assert detail["code"] == "insufficient_role", f"the refusal named {detail['code']!r}, not the standing code"
        assert detail["held"] == "player", f"the refusal says the caller held {detail['held']!r}"
        assert detail["required"] == ["admin"], f"the refusal asks for {detail['required']!r}"
        missing = player.get("/api/v1/traces/does-not-exist")
        assert missing.status_code == 403, f"a player learned whether an id exists: {missing.status_code}"

        allowed = _admin_client().get(f"/api/v1/traces/{trace_id}")
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["trace_id"] == trace_id

    def test_the_door_needs_a_session(self) -> None:
        from app.main import app

        anonymous = TestClient(app)
        response = anonymous.get("/api/v1/traces/anything")
        assert response.status_code == 401


def _now() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)
