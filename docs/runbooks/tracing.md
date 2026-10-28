# Runbook — tracing and the span store

**When:** a request is slow or failing and you need to see what it did, or an operator wants the slowest
routes and the error rate by route.

## The two backends

`apps/api/app/core/tracing.py` turns tracing on when **either** is configured:

- **OTLP collector** — `OTEL_EXPORTER_OTLP_ENDPOINT` (a base URL; the module appends `/v1/traces`). Spans go
  to the collector behind a batch processor.
- **The database span store** — `TRACE_STORE_ENABLED=1`. `SpanStoreExporter` writes each finished span into
  `request_spans` from the SDK's batch thread, so the request path never pays for the write.

With neither set, `init_tracing` returns `None`: no spans, no exporter thread, no network call. That is the
normal local/CI state.

Two guarantees the exporter holds to: **a store failure never fails a request** (it catches everything and the
batch processor drops the batch), and **the store is bounded** — every export deletes spans older than
`RETENTION` (seven days).

## Reading it

```bash
# one request's spans, oldest first, with each span's parent
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" "$API/api/v1/traces/<trace_id>"

# the operator's summary: per route, count / errors / error rate / p50 / p95 / max
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" "$API/api/v1/traces/summary?window_minutes=60"
```

Both doors ask for the **admin** standing: a span carries the request's concrete `http.target`, and
`request_spans` does not record whose request it was, so a non-admin could otherwise read another account's
path. The refusal is a 403 `insufficient_role`, answered before the lookup.

The summary groups `kind == "SERVER"` spans by `attributes.http.route` (else the span name); an error is
`status == ERROR` or `http.status_code ≥ 500`; `limit` caps the scan and `truncated` says when it bit. The
formula travels in the answer (`ROUTE_SUMMARY_FORMULA`).

## The caveat a live store hides

**Every page render writes spans of its own** — `/capabilities` from the layout, `/auth/me` from the current
user read, and `/traces/summary` itself. So the store moves *between* the API's answer and the table a page
renders from it: comparing the two cell by cell on a live store is not a stable test. Freeze the store (stop
the writer) when you need to compare; the exporter's write path is pinned separately by
`apps/api/tests/test_trace_store.py`.

## Verify the store is on and writing

```bash
# with TRACE_STORE_ENABLED=1 on the API process
curl -sS "$API/api/v1/world/status" >/dev/null
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  -tA -c "SELECT count(*), min(start_time), max(start_time) FROM request_spans"
```

A non-zero count with recent `start_time` is the evidence. An empty table with the flag on means the exporter
could not write — read the API log for "the span store could not write a batch".

## What this runbook does not claim

- It does not deploy a collector. The OTLP path is only as real as the endpoint behind it.
- It does not retain traces past seven days; the prune is part of every export.
- It does not make the summary a metric system. It is a read of a bounded store, recomputed per request, with
  no counter stored.
