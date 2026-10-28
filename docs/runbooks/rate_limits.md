# Runbook — rate limits

**When:** a caller reports `429 rate_limited`, a load test trips the limiter, or a door needs a different
ceiling.

## What the limiter is

`RateLimiter` in `apps/api/app/core/security.py` — a **fixed-window, in-memory** limiter. Each door calls:

```python
limit(request, limit_per_window, window_seconds=60, scope="<door>")
```

The bucket key is `scope:client-ip:path`, so one door's budget does not spend another's. The map is bounded by
`MAX_BUCKETS`; idle buckets are dropped first, and live survivors are evicted oldest-first when a flood of
distinct sources would otherwise grow it without limit.

A refusal is **429** with `detail.code == "rate_limited"` and a `Retry-After` header (seconds). The platform's
answer-code vocabulary lists it under `TOO_MANY_REQUESTS_CODES`.

**`ENV=test` turns the limiter off** (`limit()` returns immediately), so the suite never spends a budget. A
test that asserts a 429 must set the env deliberately; a test that asserts normal behaviour is unaffected.

## Why the effective limit scales with replicas

The store is **this process's memory**, not a shared tier. With N replicas behind a load balancer, one
client can spend roughly N × the per-door ceiling before every replica refuses. ADR-001 names the fix
(Redis); until it is taken, a published per-door number is a **per-process** number. Say so when quoting it.

## Raising or lowering a door

The ceiling is the `limit_per_window` constant in that door's `limit(...)` call — a code change, not an env
var. Grep the door:

```bash
grep -rn 'scope="<door>"' apps/api/app/api/v1
```

A window is `window_seconds` (default 60). The public catalogue and admin reads use a larger per-minute
budget than the write doors; keep a write door's ceiling low enough that a retry storm cannot fan out.

## Verify

```bash
# a burst above the ceiling gets 429 + Retry-After; a burst below it does not
for i in $(seq 1 40); do
  curl -s -o /dev/null -w '%{http_code}\n' "$API/api/v1/world/status"
done | sort | uniq -c
```

Against a running API (not `ENV=test`), the tail of the burst should be `429`; the first calls `200`. Read
`Retry-After` from one of the 429s and confirm a request after that many seconds is answered again.

## What this runbook does not claim

- It does not make the limit shared across replicas. That is ADR-001's Redis tier.
- It does not cover provider-side rate limits (model or data APIs); those are the provider's 429s, not this
  limiter's.
- It does not promise a specific number here. The ceilings live in the doors; this file names where they are
  and what the refusal looks like.
