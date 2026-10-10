# M12 Production Hardening — what landed, and what it does not claim

The spec's M12 list is nine words: `Security`, `Performance`, `Observability`, `Cost optimization`,
`Caching`, `Rate limiting`, `Data governance`, `Backup`, `Disaster recovery`. Three of them were
already standing when this milestone started, and the rest are recorded here — each with the plane it
was measured on, and each with the sentence about what it deliberately does not do.

## The three that were already standing

| Item | Where it lives | What it already answered |
| --- | --- | --- |
| Rate limiting | `app/core/security.py`'s `RateLimiter` + the `rate_limited` code registered in the answer table | Per-scope fixed-window limits, applied by the `limit()` dependency every door calls |
| Security | §60's census (`test_authorization_census.py`), the §51/§60 answer-table landings, `install_error_handlers` | Every 403 in the tree comes from a code the table answers; no router spells a status literal |
| Cost *tracking* | `services/model_ledger.py` + `/metrics/providers` | Every call recorded with tokens, latency, cost, demo flag |

They are listed because a verification document that only records the new work invites the reader to
assume the old work is unverified. It is verified elsewhere, and its evidence lives there.

## What landed

### Observability — structured logging with request correlation

`app/core/logging.py`. `JSONFormatter` emits one JSON object per record with the fields a log
aggregator indexes on — `timestamp`, `level`, `logger`, `message`, `module`, `function`, `line`,
`request_id` — and any extra a call attaches via `logger.info("...", extra={...})` is carried through
rather than dropped. `RequestIDFilter` reads the correlation ID the middleware set, so every line a
request produces can be joined to it.

The middleware (`app/main.py`) generates a `X-Request-ID` when the caller sent none, echoes the
caller's own when they did, and both the ID and `X-Request-Duration-Ms` travel back on the response.
`configure_logging()` replaces the previous `logging.basicConfig(...)` call — the old format was
`"%(asctime)s %(levelname)s %(name)s %(message)s"`, which is human-readable and not machine-readable,
and an aggregation pipeline could not index it without a parser.

Third-party noise is silenced where it would drown the application's own lines: `uvicorn.access`
(request lines httpx and the access log already produce), `sqlalchemy.engine` (per-query echo), and
`sqlalchemy.pool` (per-connection checkouts). What is deliberately **not** claimed: no external log
sink is configured — no Loki, no CloudWatch. The formatter is the contract with whichever sink is
wired later, and the sink is deployment configuration, not application code.

### Performance — an in-memory TTL cache and a response middleware

`app/core/cache.py`. `TTLCache` is a thread-safe `OrderedDict` with three properties a cache needs
and one it must not have: TTL expiry, LRU eviction at `max_size`, and statistics (`hits`, `misses`,
`hit_rate`, `evictions`) — and no persistence, because a cache that survives a restart is a stale
database with none of a database's guarantees.

Two instances run: `_response_cache` (1 minute, 5,000 entries) and `_compute_cache` (5 minutes,
10,000). The HTTP middleware in `app/main.py` caches `GET` responses whose content type is JSON, is
bypassed by a `Cache-Control: no-cache` request header, and answers with `X-Cache: HIT` or
`X-Cache: MISS` so a caller can tell which they got. It is bypassed outright when
`settings.env == "test"` — the test database persists from case to case, so a cached response would
make the case after it read the case before it. That bypass is what kept `test_community.py`'s
follow-then-withdraw case honest, and it was found by that case going red, not by reading the code.

`GET /api/v1/metrics/cache` publishes both caches' statistics, so the cache is observable rather
than an invisible optimisation.

**Not claimed:** there is no distributed cache. Redis is not in `requirements.txt`, and the run that
built this has no Redis instance, so a Redis-backed tier would have been unmeasured speculation — the
in-memory cache is measured, and a Redis tier behind the same interface is the upgrade path when an
instance exists.

### Performance — latency percentiles that read the same on both engines

`app/services/latency_profile.py`. `/metrics/system` carried `p95_latency_ms: None` with a comment
saying a percentile would need computing. PostgreSQL has `percentile_cont`; SQLite has nothing
equivalent. This project runs both engines (SQLite local, PostgreSQL CI and production), so a
window function would have answered the same field two different ways — one exactly and one not at
all.

The profile reads the newest `SAMPLE_SIZE` (2000) rows in the window and computes nearest-rank
percentiles in Python: the same arithmetic on both engines, and honest about being a sample —
`sample_size`, `sampled_from` and `sample_is_newest` are in the answer. Nearest-rank rather than
interpolated, because an interpolated value between two rows is a latency no call actually took, and
this figure sits beside a sentence about what a caller waited. `GET /api/v1/metrics/latency` exposes
it overall or per feature, and the system door now carries the p95 itself.

The case that pinned the definition found a mistake in the *test*: it asserted `50/95/99` over rows
`0..99`, and `n = ceil(P/100 × N)` makes the correct nearest-rank answers `49/94/98`. The code was
right and the assertion was wrong; the test now carries the formula in a comment so the next reader
does not have to re-derive it.

### Cost optimisation — an advisor over the ledger, not an enforcer over the router

`app/services/cost_advisor.py`, `GET /api/v1/metrics/cost-optimisation?days=N`. Four breakdowns over
a stated window, every figure recomputed from `model_calls` on the request:

| Breakdown | What it answers |
| --- | --- |
| `by_feature` | each feature's spend, call count, failed count and failure rate, in spend order |
| `by_model` | cost per 1,000 tokens per model — the figure a routing decision is actually made on |
| `totals` | spend, calls, failures, demo share, reasoning share, budget |
| `recommendations` | the four findings below |

Four recommendations, each firing only above its threshold and each naming the arithmetic that
produced it: `failure_waste` (a failed call is a paid call with no answer; fires above 5% failures),
`reasoning_share` (reasoning tokens are billed at the output rate; fires above 50% of output),
`budget_pace` (spend per day against `settings.ai_daily_budget_usd`), and
`cheaper_model_available` (a model called in the same ledger at 2×+ lower rate per 1k, with the
saving in dollars).

The service's docstring and the endpoint's `limitation` both say the same thing: this is an advisor,
not an enforcer. Nothing changes which provider a door calls — that is §45's router's decision, and
an endpoint that read the ledger could not safely own it. A human reads the figures and decides.

### Data governance and backup/recovery — documents and scripts

* `docs/DATA_GOVERNANCE.md` — classification (public / internal / confidential / restricted),
  retention periods per data category with disposal methods, access principles, quality controls,
  privacy obligations, review cycle, roles, and incident response.
* `docs/BACKUP_RECOVERY.md` — RTO/RPO targets per system (API 4h/15min, database 2h/5min), the
  continuous-archiving plus daily logical dump strategy, four recovery scenarios, the testing
  schedule, the alerting table, and the on-call roles.
* `scripts/backup_db.sh` — full (`pg_dump -Fc`) or incremental (WAL/verification) with S3 upload,
  post-backup verification via `pg_restore --list`, and local cleanup keeping the last 7 days.
* `scripts/restore_db.sh` — restore into a named target database, replayed with `alembic upgrade
  head`, parallel restore on 4 jobs.

**Not claimed:** backup and restore are *written and reviewed*, not *executed here*. This host runs
SQLite for the API's tests and a PostgreSQL container on 54321 for the local plane; there is no
`pg_dump`, no S3 bucket, and no WAL archive configured, so the scripts are verified by inspection and
by their own argument handling, and the first live `pg_dump` run belongs to a host that has both.
The documents say so, because a backup script nobody has run is a plan, not a control.

## The figures, with their plane

| measurement | plane | result |
| --- | --- | --- |
| `pytest tests/test_cost_advisor.py tests/test_latency_profile.py tests/test_metrics.py tests/test_agents.py tests/test_answer_census.py tests/test_authorization_census.py tests/test_community.py tests/test_account_deletion.py -q --tb=line` | SQLite, local venv, working copy | **127 tests / 0 failures / 0 errors / 0 skipped**, rc=0, wall **65s** |
| `ruff check app tests` | same | All checks passed |
| `ruff format --check` over the new modules | same | all formatted |
| `mypy` over `cost_advisor`, `latency_profile`, `metrics`, `cache`, `logging`, `main` | same | no issues |
| `pytest tests/test_openapi_contract_currency.py tests/test_spec_audit_currency.py -q` | same, against `HEAD` | 13 tests, rc=0 |
| contract paths after the three metrics doors | `docs/api/openapi.json` committed | 179 → **182** |
| `git grep -li agents -- apps/api/app` | committed tree | 13 → **14** (`services/agents/orchestrator.py`) |

The contract and audit figures were recomputed against the committed tree, not the working copy,
because `test_spec_audit_currency.py` reads `git show HEAD:…`. Two doc landings were needed to make
that pass — one for the agents scan, one for the contract-path count — and both are recorded in the
audit's own numbers rather than left stale.

## What M12 does not claim

* **No external cache.** In-memory only; no Redis instance exists to measure against.
* **No external log sink.** The JSON formatter is the contract with a sink that deployment wires.
* **No distributed tracing.** No OpenTelemetry, no span propagation. Request correlation through the
  ID header is what exists; spans are not.
* **Backup scripts unexecuted on this host.** No `pg_dump`, no S3, no WAL archive here.
* **No load test.** No k6, no locust, no measured throughput figure. The latency percentiles measure
  *observed* latency over the ledger; they do not assert a ceiling under load.
* **No cost guarantee.** The advisor reports; the router decides (`settings.ai_daily_budget_usd` is a
  `budget_exhausted()` check the caller honouring it is what enforces).
* **The i18n §81 work is another agent's lane.** Several web files were modified by the concurrent
  run during this milestone and are not part of it.
