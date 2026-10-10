"""OpenTelemetry distributed tracing setup (M12 Observability).

Configures OpenTelemetry with FastAPI instrumentation, HTTPX client instrumentation,
and an OTLP exporter. Tracing is enabled by the environment variable
`OTEL_EXPORTER_OTLP_ENDPOINT` — when unset, `init_tracing` returns None, no spans are
created, no exporter thread runs, and no network call is attempted, so local
development and test runs stay silent. The packages themselves ship in
`requirements.txt`; what the variable gates is the collector traffic, not the import.

The tracer name is `football_os.api` and the service name is `football-os-api`.
"""

from __future__ import annotations

import os
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanProcessor

from app.core.config import settings

SERVICE_NAME = "football-os-api"
ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"


def init_tracing(*, span_processor: SpanProcessor | None = None) -> TracerProvider | None:
    """Initialise OpenTelemetry tracing when an OTLP endpoint is configured.

    Returns the installed `TracerProvider`, or None when
    `OTEL_EXPORTER_OTLP_ENDPOINT` is unset — the expected state for local
    development and CI, where no collector runs. Idempotency note: the OpenTelemetry
    API installs a global provider once; a second call logs an override warning and
    replaces it, so this is a boot-time call, not a per-request one.

    `span_processor` exists for tests: pass a `SimpleSpanProcessor(InMemorySpanExporter)`
    to observe spans without a collector. Production leaves it None and gets the
    OTLP/HTTP exporter behind a batch processor, so a slow or down collector
    cannot block a request.
    """
    endpoint = os.getenv(ENDPOINT_ENV)
    if not endpoint:
        return None

    provider = build_provider(endpoint, span_processor)
    trace.set_tracer_provider(provider)

    # Instrument the HTTPX client (outgoing HTTP calls) globally; FastAPI is
    # instrumented per-app in `instrument_fastapi`, called from app.main.create_app.
    HTTPXClientInstrumentor().instrument()
    return provider


def build_provider(endpoint: str, span_processor: SpanProcessor | None = None) -> TracerProvider:
    """Build the SDK tracer provider with the service resource and one span processor."""
    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": "0.1.0",
            "deployment.environment": settings.env,
        }
    )
    provider = TracerProvider(resource=resource)
    if span_processor is not None:
        provider.add_span_processor(span_processor)
    else:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return provider


def instrument_fastapi(app: Any, *, tracer_provider: trace.TracerProvider | None = None) -> None:
    """Instrument a FastAPI application with OpenTelemetry.

    Called from `app.main.create_app` after the app is constructed. A no-op when
    tracing is disabled. `tracer_provider` overrides the global provider — tests
    pass the provider `init_tracing` returned so they never touch global state.
    """
    if not os.getenv(ENDPOINT_ENV):
        return
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=tracer_provider or trace.get_tracer_provider()
    )


def get_tracer(name: str = "football_os.api") -> trace.Tracer:
    """Get a tracer instance for manual span creation."""
    return trace.get_tracer_provider().get_tracer(name)
