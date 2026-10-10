"""M12 Observability: the tracing gate answers for what it switches on and leaves off.

Two claims are held here, both about the boundary the `OTEL_EXPORTER_OTLP_ENDPOINT`
variable guards:

* without the variable, tracing is a **no-op** — no provider is installed, no
  span processor is built, and a FastAPI app stays uninstrumented;
* with the variable, a request through an instrumented app produces **one server
  span** carrying the service resource — measured through an in-memory exporter,
  never through a network call, and without touching the process-global tracer
  provider the rest of the suite shares.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import tracing


@pytest.fixture()
def no_endpoint(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(tracing.ENDPOINT_ENV, raising=False)
    yield


@pytest.fixture()
def endpoint(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Any syntactically valid URL; the in-memory processor below means nothing is
    # ever sent to it.
    monkeypatch.setenv(tracing.ENDPOINT_ENV, "http://127.0.0.1:9/v1/traces")
    # The production path installs the provider globally and patches the httpx
    # client. The global install is process-wide state the rest of the suite must
    # not inherit, so this run replaces it with a no-op — `instrument_fastapi` takes
    # the provider explicitly, which is exactly the seam the test needs.
    monkeypatch.setattr(otel_trace, "set_tracer_provider", lambda _provider: None)
    yield


def test_without_endpoint_tracing_is_a_no_op(no_endpoint: None) -> None:
    assert tracing.init_tracing() is None

    app = FastAPI()
    before = len(app.user_middleware)
    tracing.instrument_fastapi(app)
    assert len(app.user_middleware) == before, "instrument_fastapi must not instrument a disabled app"


def test_with_endpoint_a_request_produces_a_server_span(endpoint: None) -> None:
    exporter = InMemorySpanExporter()
    provider = tracing.init_tracing(span_processor=SimpleSpanProcessor(exporter))

    assert provider is not None
    resource_attrs = provider.resource.attributes
    assert resource_attrs["service.name"] == "football-os-api"
    assert resource_attrs["deployment.environment"] == "test"

    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    # mypy: FastAPIInstrumentor wants its own app type; the runtime contract is duck-typed.
    tracing.instrument_fastapi(app, tracer_provider=provider)  # type: ignore[arg-type]
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200

    spans = exporter.get_finished_spans()
    # Exactly one SERVER span for the request. The rest of the list is the httpx
    # CLIENT side: TestClient is itself an httpx caller, and `init_tracing`
    # instruments httpx globally — the same instrumentation a real outgoing call
    # gets. Naming the stragglers is the difference between a count that passes
    # and a setup that is understood.
    from opentelemetry.trace import SpanKind

    server_spans = [s for s in spans if s.kind == SpanKind.SERVER]
    assert len(server_spans) == 1
    span = server_spans[0]
    assert span.name == "GET /ping"
    assert span.resource.attributes["service.name"] == "football-os-api"
    assert span.context is not None and span.context.trace_id != 0


def test_instrumented_app_still_serves_when_collector_is_absent(endpoint: None) -> None:
    """The batch processor exports on a background thread: a down collector must
    not fail a request. Measured with the real OTLP exporter pointed at a port
    nothing listens on — the request answers 200 and the exporter's failure stays
    on its thread."""
    provider = tracing.build_provider("http://127.0.0.1:9/v1/traces")
    app: Any = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    tracing.instrument_fastapi(app, tracer_provider=provider)
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200

    provider.shutdown()
