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

### Observability — distributed tracing (OpenTelemetry)

`app/core/tracing.py`, wired from `app/main.py`. `init_tracing()` builds an SDK `TracerProvider`
whose resource carries `service.name=football-os-api`, the service version and the deployment
environment, and installs it as the global provider with an OTLP/HTTP exporter behind a
`BatchSpanProcessor` — a slow or down collector cannot block a request, because the export runs on
the processor's own thread. `HTTPXClientInstrumentor` covers outgoing calls; `instrument_fastapi`
covers the app's incoming requests. `main.py` calls both at boot.

The switch is the environment variable `OTEL_EXPORTER_OTLP_ENDPOINT`, and what it gates is the
**traffic**, not the import: without it, `init_tracing` returns None, no processor is built, no
background thread runs, no network call is attempted, and `instrument_fastapi` leaves the app
uninstrumented. With it, a request produces a `SERVER` span named for its route. The five packages
are pinned in `requirements.txt`, so a fresh install cannot boot into an `ImportError` the env var
was supposed to prevent — the first version of this module imported OpenTelemetry at module level
while promising "tests run without external dependencies", which was exactly the kind of claim this
project exists to catch.

What is measured (`tests/test_tracing.py`, three cases): without the variable, no provider is
installed and a FastAPI app gains no middleware; with it, a request through an instrumented app
produces exactly one `SERVER` span carrying the service resource — observed through an
`InMemorySpanExporter` injected as the span processor, never through a network call, and without
installing a global provider the rest of the suite would inherit (`init_tracing` accepts one for
exactly this reason, and `instrument_fastapi` takes the provider explicitly). The remaining spans
that exporter sees are the httpx CLIENT spans TestClient itself produces — the same instrumentation
a real outgoing call gets. The third case points the real OTLP exporter at a port nothing listens
on and holds the request to 200: a down collector degrades telemetry, not the API.

What is deliberately **not** claimed: no collector runs on this host, so no span has ever been
exported to a real backend; no sampling policy beyond the SDK default; no trace-context propagation
assertion across the web tier (the browser does not send `traceparent`, and the proxy is not
instrumented). Span export is deployment configuration, the same boundary the log sink sits behind.

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

`app/core/redis_cache.py`. `RedisCache` sits behind the same operations and keeps `TTLCache` as a
mandatory second tier: every `set` writes the fallback first and Redis second, so a cache that is
down costs a read path and never a write. The connection is attempted once at construction with a
two-second socket budget; on any failure — refused, timed out, or an authentication handshake the
instance rejects — `redis_available` drops to false and stays there, and every later call takes the
in-memory branch without paying another connect. Keys are namespaced `football_os:` and values are
JSON, so a shared instance cannot collide with another application's data.

`REDIS_URL` is the only knob and defaults to `redis://localhost:6379/0`. `get_stats()` publishes the
URL **only while Redis is serving** — a URL can carry a password, and a metrics endpoint is the
wrong place to put one.

**Measured on this host:** port 6379 is occupied, by a Redis that requires a password, so the
default no-auth URL cannot authenticate. The layer behaves as designed there: the first `get` costs
0.008 ms and falls through to memory, the `set` still lands in the fallback and returns true, the
second read hits the fallback (`hits: 1`, `hit_rate: 0.5`), and `redis_available` is false. That is
the path most likely to run in a deployment that has not provisioned a cache, so measuring it beats
asserting it.

**Not claimed:** the Redis tier has never served a real request. No authenticated instance was
available here, so the ten degradation cases run against a mocked client and the `integration`-marked
case is the one that needs a live service. Degradation is also **sticky for the life of the
process** — a Redis that starts after the process is not picked up until restart. That is the right
trade against paying a failed connect per call, and it is stated so a reader deploying behind a
restart-less rollout can decide otherwise.

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

**Executed 2026-10-11 — the first live restore drill.** The scripts name host binaries this host
does not have, but the project's own PostgreSQL container (`football_os_db`, port 54321) ships
them, so the drill ran inside it against the container's real data (69 tables, 231 users at drill
time):

1. `pg_dump -Fc -Z 3` → **2,106,017 bytes**; `pg_restore --list` counts **69 TABLE DATA entries**,
   one per table.
2. `pg_restore --jobs=4` into a throwaway `football_os_restore_drill` database — rc=0.
3. Exact per-table `count(*)` compared source against restored: **58/69 tables identical**. The 11
   that differ are exactly the tables the live tier writes (`users`, `xp_events`, `coach_messages`,
   `knowledge_queries`, `model_calls`, `audit_logs`, `refresh_sessions`, `training_plans`,
   `training_sessions`, `user_achievements`, `user_players`) — the browser walk was running
   against the same container while the drill ran, and every divergence is source-side additions
   since the dump instant. **Zero tables where the restored copy holds more rows than the
   source.** A restored copy matching a moving source as of the dump instant is what a faithful
   restore looks like; the drill's comparison is reproducible only in a quiesced window, which is
   the same caveat production's verify step carries.
4. `alembic upgrade head` + `alembic check` against the restored copy — and here the drill earned
   its keep: **`alembic check` failed**, reporting two `remove_index` operations on `video_assets`.
   The restored copy was faithful; the drift it copied was the source's. The container had been
   created before `2e197f085070` fixed the double-indexing of `player_id`/`match_id`, so it still
   carried the original aliases (`ix_video_match`, `ix_video_player`) that no fresh database — and
   therefore no gate run — has ever had. Migration `0027` drops both aliases (`DROP INDEX IF
   EXISTS`, no-ops on fresh databases, reversible via `downgrade`); applied to the container, the
   duplicate indexes are gone and `alembic check` is clean against the live database. The gate
   compares models against *fresh* databases; only a restore drill compares against the one that
   has lived.

The drill database was dropped afterwards. Still **not claimed**: no S3 upload, no WAL archive,
no point-in-time recovery — the container is one local PostgreSQL, and the scripts' remote
pathways remain inspection-verified. What changed is the worst claim in this document: the backup
and restore are now *executed*, and the execution found a defect no gate could see.

## The figures, with their plane

| measurement | plane | result |
| --- | --- | --- |
| `pytest tests/test_cost_advisor.py tests/test_latency_profile.py tests/test_metrics.py tests/test_agents.py tests/test_answer_census.py tests/test_authorization_census.py tests/test_community.py tests/test_account_deletion.py -q --tb=line` | SQLite, local venv, working copy | **127 tests / 0 failures / 0 errors / 0 skipped**, rc=0, wall **65s** |
| `ruff check app tests` | same | All checks passed |
| `ruff format --check` over the new modules | same | all formatted |
| `mypy` over `cost_advisor`, `latency_profile`, `metrics`, `cache`, `logging`, `main` | same | no issues |
| `pytest tests/test_openapi_contract_currency.py tests/test_spec_audit_currency.py -q` | same, against `HEAD` | 13 tests, rc=0 |
| `pytest tests/test_tracing.py -q` | SQLite, working copy | **3 tests / 0 failures**, rc=0 |
| contract paths after the three metrics doors | `docs/api/openapi.json` committed | 179 → **182** |
| `git grep -li agents -- apps/api/app` | committed tree | 13 → **14** (`services/agents/orchestrator.py`) |

The contract and audit figures were recomputed against the committed tree, not the working copy,
because `test_spec_audit_currency.py` reads `git show HEAD:…`. Two doc landings were needed to make
that pass — one for the agents scan, one for the contract-path count — and both are recorded in the
audit's own numbers rather than left stale.

## What M12 does not claim

* **No authenticated Redis tier.** `RedisCache` landed with the in-memory fallback wired, and its
  degradation paths are measured against this host's password-protected 6379 — but no instance has
  ever served a real request through it, and the fallback is sticky for the life of the process.
* **No external log sink.** The JSON formatter is the contract with a sink that deployment wires.
* **No trace backend.** OpenTelemetry is wired and the span path is measured through an in-memory
  exporter, but no collector runs on this host, so no span has reached a real backend; sampling and
  propagation through the proxy are deployment concerns, not claims.
* **No off-host backup pathway executed.** The restore drill ran `pg_dump` → `pg_restore` inside
  the project's own container; S3 upload and WAL archiving remain inspection-verified only.
* **No published load-test ceiling.** `scripts/bench_api.py` is the harness; a measured run
  against the local tier is recorded below when it is run, and it will not be extrapolated to
  production hardware.
* **No cost guarantee, and honouring the cap is still a per-caller duty.** The advisor reports; the
  router decides. Two doors check `budget_exhausted()` at the call instead of trusting a caller to
  stop on its own: `/knowledge/ask` refuses with 429 `ai_budget_exhausted` (2026-10-06), and
  `/coach/ask` skips the phrasing step while still shipping the arithmetic (2026-10-11), because
  the recommendation there is computed from stored data and the model only words it. Provider-side
  spend controls are not in this repository, so a door that omits the check is not stopped by it.
* **The i18n §81 work is another agent's lane.** Several web files were modified by the concurrent
  run during this milestone and are not part of it.
