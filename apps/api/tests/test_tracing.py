"""M12 Observability: the tracing gate answers for what it switches on and leaves off.

Three claims are held here, all about the boundary the `OTEL_EXPORTER_OTLP_ENDPOINT`
variable guards:

* without the variable, tracing is a **no-op** — no provider is installed, no
  span processor is built, and a FastAPI app stays uninstrumented;
* with the variable, a request through an instrumented app produces **one server
  span** carrying the service resource — measured through an in-memory exporter,
  never through a network call, and without touching the process-global tracer
  provider the rest of the suite shares;
* the collector the repository ships is the one the document points at — the
  compose profile, image, loopback ports, config mount and traces pipeline agree
  with the endpoint example, so the witness recorded in the M12 document cannot
  go stale behind a changed compose file.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import tracing

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "infra" / "docker-compose.yml"
M12_DOC = ROOT / "docs" / "M12_PRODUCTION_HARDENING_VERIFICATION.md"


@pytest.fixture()
def no_endpoint(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv(tracing.ENDPOINT_ENV, raising=False)
    yield


@pytest.fixture()
def endpoint(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # The variable's documented shape is a *base* URL; the in-memory processor below
    # means nothing is ever sent to it.
    monkeypatch.setenv(tracing.ENDPOINT_ENV, "http://127.0.0.1:9")
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


def test_the_endpoint_always_posts_to_the_traces_path() -> None:
    """`OTEL_EXPORTER_OTLP_ENDPOINT` is a base URL by specification, so the exporter
    must POST to `/v1/traces` — not to the base itself. A value a deployment already
    wrote in full form must not gain a second `/v1/traces`. The receiver is a real
    local HTTP server; it records the path it was actually sent.

    The other cases in this file never observe a POST (their collector port is dead),
    which is why none of them could see the base-form defect: the argument form and
    the documented environment variable were not the same contract.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen.append(self.path)
            length = int(self.headers.get("content-length", "0"))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, fmt: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        for endpoint in (base, f"{base}/", f"{base}/v1/traces"):
            provider = tracing.build_provider(endpoint)
            with provider.get_tracer("test").start_as_current_span("probe"):
                pass
            provider.force_flush()
            provider.shutdown()
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert seen == ["/v1/traces"] * 3, f"the exporter posted to {seen!r}, not the traces path"


COLLECTOR_SERVICE = "otel-collector"
COLLECTOR_IMAGE = "otel/opentelemetry-collector:0.111.0"
COLLECTOR_MOUNT = "./otel-collector.yaml:/etc/otelcol/config.yaml:ro"
COLLECTOR_PORTS = {"127.0.0.1:4317:4317", "127.0.0.1:4318:4318"}


def _collector_defects(compose_path: Path, doc_path: Path) -> list[str]:
    """Named disagreements between the shipped collector, its config and the document.

    Empty when they agree. The judgement lives apart from the test so witness arms can
    run it over mutated copies without touching the tracked files.
    """
    import yaml

    defects: list[str] = []
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    service = (compose.get("services") or {}).get(COLLECTOR_SERVICE)
    if service is None:
        return [f"compose: no {COLLECTOR_SERVICE} service"]
    if service.get("profiles") != ["observability"]:
        defects.append(f"compose: profiles is {service.get('profiles')!r}, not ['observability']")
    if service.get("image") != COLLECTOR_IMAGE:
        defects.append(f"compose: image is {service.get('image')!r}, not {COLLECTOR_IMAGE!r}")
    ports = set(service.get("ports") or [])
    if not COLLECTOR_PORTS <= ports:
        defects.append(f"compose: ports are {sorted(ports)!r}, missing {sorted(COLLECTOR_PORTS - ports)!r}")
    volumes = service.get("volumes") or []
    if COLLECTOR_MOUNT not in volumes:
        defects.append(f"compose: volumes are {volumes!r}, no {COLLECTOR_MOUNT!r}")
    config_path = compose_path.parent / COLLECTOR_MOUNT.split(":")[0]
    if not config_path.is_file():
        defects.append(f"config: {config_path} does not exist")
        return defects
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    protocols = ((config.get("receivers") or {}).get("otlp") or {}).get("protocols") or {}
    if set(protocols) != {"grpc", "http"}:
        defects.append(f"config: otlp protocols are {sorted(protocols)!r}, not ['grpc', 'http']")
    pipeline = {"receivers": ["otlp"], "exporters": ["debug"]}
    traces = ((config.get("service") or {}).get("pipelines") or {}).get("traces")
    if traces != pipeline:
        defects.append(f"config: traces pipeline is {traces!r}, not {pipeline!r}")
    doc = doc_path.read_text(encoding="utf-8")
    documented = set(re.findall(r"OTEL_EXPORTER_OTLP_ENDPOINT=http://127\.0\.0\.1:(\d+)", doc))
    host_ports = {entry.split(":")[1] for entry in ports if entry.count(":") == 2}
    if not documented:
        defects.append("doc: no OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:<port> example")
    elif not documented <= host_ports:
        defects.append(f"doc: examples {sorted(documented)!r} are not published host ports {sorted(host_ports)!r}")
    return defects


def test_the_shipped_collector_is_the_one_the_doc_points_at() -> None:
    """The collector witness in the M12 document names a compose profile, an image, a
    loopback port and a config pipeline. If any of them moves, the witness describes a
    container nobody runs — so the three files must agree, not just exist."""
    defects = _collector_defects(COMPOSE, M12_DOC)
    assert defects == [], f"the shipped collector disagrees with itself: {defects!r}"


def test_instrumented_app_still_serves_when_collector_is_absent(endpoint: None) -> None:
    """The batch processor exports on a background thread: a down collector must
    not fail a request. Measured with the real OTLP exporter pointed at a port
    nothing listens on — the request answers 200 and the exporter's failure stays
    on its thread."""
    provider = tracing.build_provider("http://127.0.0.1:9")
    app: Any = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    tracing.instrument_fastapi(app, tracer_provider=provider)
    with TestClient(app) as client:
        assert client.get("/ping").status_code == 200

    provider.shutdown()
