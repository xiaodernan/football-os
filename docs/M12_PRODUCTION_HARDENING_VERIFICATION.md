# M12 Production Hardening — what landed, and what it does not claim

The spec's M12 list is nine words: `Security`, `Performance`, `Observability`, `Cost optimization`,
`Caching`, `Rate limiting`, `Data governance`, `Backup`, `Disaster recovery`. Three of them were
already standing when this milestone started, and the rest are recorded here — each with the plane it
was measured on, and each with the sentence about what it deliberately does not do.

## The three that were already standing

| Item | Where it lives | What it already answered |
| --- | --- | --- |
| Rate limiting | `app/core/security.py`'s `RateLimiter`, `limit()`, and `tests/test_rate_limiter.py` — **8 cases, added 2026-10-13** | Per-scope fixed-window limits, applied by the `limit()` dependency every door calls. The window slides with the clock rather than resetting on a boundary, and `scope`, `client` and `path` each get their own budget, which is the point of all three being in the key. It is called before any credential is looked at on register, login and account deletion. The row above used to say this was verified elsewhere; it was not — no test named it. Writing them found that the bound in the code was not one: the prune at `MAX_BUCKETS` dropped only *idle* buckets, so a flood of distinct live buckets — which is what a rotating source address produces, since the key contains the client — left 6000 of them in a map capped at 5000. That is an unbounded map reachable from outside the very doors the limiter protects, and the failure mode that leaves an API with no rate limit at all is a process that has died. `_prune` now drops idle buckets first and then the least recently touched survivors until the promise holds. |
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

That is true of every response except the one that needs it most. Starlette builds its stack as
`[ServerErrorMiddleware] + user_middleware + [ExceptionMiddleware]`, so `request_context` — for all the
care taken over its registration order — sits *inside* the middleware that renders an unhandled
exception: a route that raises propagates out of it before the lines that dress the response have run,
and the 500 reached the client carrying no `X-Request-ID`, no duration, no `nosniff`. The log line kept
its ID, because the context variable is set before the call and `ServerErrorMiddleware` reads the same
variable back — so the two ends disagreed: the server had recorded an ID it never put on the wire, and
nothing tied them together but a timestamp and a path. That is the same as having no ID, and it is the
wrong response to lose it on, since a 500 is the one status a client quotes back at you. The header set
now lives in one function, `app/core/response_headers.py`: `request_context` calls it for everything that
flows normally, `install_error_handlers`'s `_unhandled` calls it for the one answer that never comes back
to it, and `request_started_var` carries the start time across the same gap so a crash still reports a
real duration. `tests/test_error_response_headers.py` drives a throwing route through the real middleware
stack and asserts the crash answer's ID is the ID in its own log record. The case was written first and
failed first — the response came back with `content-length: 72` and nothing but `content-type`.

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

What is measured (`tests/test_tracing.py`, seven cases): without the variable, no provider is
installed and a FastAPI app gains no middleware; with it, a request through an instrumented app
produces exactly one `SERVER` span carrying the service resource — observed through an
`InMemorySpanExporter` injected as the span processor, never through a network call, and without
installing a global provider the rest of the suite would inherit (`init_tracing` accepts one for
exactly this reason, and `instrument_fastapi` takes the provider explicitly). The remaining spans
that exporter sees are the httpx CLIENT spans TestClient itself produces — the same instrumentation
a real outgoing call gets. The third case points the real OTLP exporter at a port nothing listens
on and holds the request to 200: a down collector degrades telemetry, not the API. The fourth case
listens on a socket of its own and asserts every accepted endpoint form — base, base with a trailing
slash, and one that already names `/v1/traces` — POSTs to `/v1/traces` and nothing else; that case
was written after a live walk found the base form POSTing to the collector root, below. The fifth
reads the repository instead of the process: `_collector_defects` compares the compose file, the
collector's own config and this document and returns named disagreements — the `observability`
profile, the pinned image, both loopback ports, the config mount and its file, the OTLP protocols,
the traces pipeline, and the port in the documented endpoint example. Ten planted defects across
those clauses were each named by it, and the unmutated copies read none. The sixth sends a known W3C
`traceparent` through the real instrumentation: the server span continues that trace and names the
caller's span as its remote parent, while a second request with no header starts a different trace —
the control that makes the first reading mean the header was believed. With extraction disabled,
the same case fails naming the caller's span id (`the server span has no parent; the caller's span
00f067aa0ba902b7 was not extracted`). The seventh pins the other half of the W3C contract: the
provider is built on the SDK's parent-based default, so a caller that sends `sampled=0` (flags
`00`) is honoured and **no** `SERVER` span is exported, while the same trace id sent with `sampled=1`
(`01`) is exported as the continuation of the caller's span — two requests, one span, and the
control makes the emptiness attributable to the flag. Forcing the provider's sampler always-on
turns that case red alone on its count (`expected exactly one server span, got 2`); forcing it
always-off reds it on the same count (`got 0`), which is the control half proving the sampled
request is the one that produced the span.

**The collector leg (2026-10-22).** The repository now ships the collector it exports to:
`infra/otel-collector.yaml` receives OTLP over gRPC (4317) and HTTP (4318) and prints spans through
the `debug` exporter, and `infra/docker-compose.yml` runs `otel/opentelemetry-collector:0.111.0`
under the `observability` profile with both ports bound to `127.0.0.1`. Started with
`docker compose --profile observability up -d otel-collector`, an API booted with
`OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` and one `GET /healthz` later, the collector's
own log carries a `SERVER` span named `GET /healthz`, its ASGI child spans, and the resource
`service.name: Str(football-os-api)`, `deployment.environment: Str(development)`,
`telemetry.sdk.language: Str(python)` — one trace id across the tree. It printed
`Resource attributes:` once for the batch and eight spans inside it; two of the `SERVER` spans are
the two `/healthz` knocks the walk made.

That walk found a defect the in-memory tests could not: `OTEL_EXPORTER_OTLP_ENDPOINT` is a **base**
URL by specification (the SDK appends the signal path when it reads the variable itself), but
`build_provider` handed the value to `OTLPSpanExporter(endpoint=…)`, which treats its argument as
the **full** traces URL. The exporter therefore POSTed to the collector root and the collector
answered `404 Not Found`; the API log reads `Failed to export spans batch code: 404, reason: Not
Found`, and the collector saw no spans. A direct POST to `http://127.0.0.1:4318/v1/traces` answered
`200 {"partialSuccess":{}}`, which named the sender as the culprit rather than the receiver.
`_traces_endpoint()` now appends `/v1/traces` unless the value already names it. The new case was
run against the unfixed code first and failed exactly there (`At index 0 diff: '/' !=
'/v1/traces'`); after the fix that case passes and the live walk exports the span described
above.

**The proxy leg (2026-10-23).** The sixth case proved the API continues a caller's `traceparent`; the
browser reaches that API only through the Next.js cookie proxy, and the proxy built its outgoing
headers from an allowlist (`accept`, `authorization`, `cookie`, `content-type`, `range`), so an
upstream caller's trace context — a load balancer's, an edge worker's, a gateway's — stopped at the
tier and the API began a second trace for one request. `apps/web/lib/trace-context.ts` validates the
incoming header against the W3C format and forwards `traceparent` and `tracestate` only when it is
valid: two lowercase hex version digits that are not `ff`, a 32-hex trace id and 16-hex parent id that
are not all zero, two hex flags, and no trailing field on version `00` (a higher version's extra
fields travel unread). With no incoming header the tier sends nothing — it does not mint ids, because
it has no span to name.

**Measured.** `qa-proxy-gate.mjs` holds three more checks (six total over 131 files): it compiles and
**calls** the shipped helper for three valid shapes (bare, with `tracestate`, a future version), drops
nine invalid ones — including a `tracestate` with no `traceparent`, the control that the tier starts
no trace — and reads the route's own AST to prove `handle` computes the context off the incoming
request, both calls that forward `target` carry it, and `callApi` spreads it into the outgoing
headers. Eight arm planes matched, predictions written first: the control 6/6 green; four helper
mutations (uppercase accepted, all-zero trace id, orphan `tracestate`, version `00` with a trailing
field) each red on the propagation check naming that shape; three route mutations (the spread removed,
the retry loses the context, `handle` stops reading the request) each red on the reach check naming the
missing seam. The live walk: a production web build (`NEXT_DIST_DIR=.next-m12trace`, port 3221)
proxying to an API with `TRACE_STORE_ENABLED=1` over a fresh SQLite database, one
`GET /api/v1/traces/…` carrying `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
answered 401 (the door is auth-gated) and left four `request_spans` rows whose `trace_id` is the
caller's, the `SERVER` row naming `00f067aa0ba902b7` as its parent; the same request with no header
left an unparented `SERVER` span in a different trace (`964b3f829197972596588c36b1848188`).

What is deliberately **not** claimed: no production or third-party trace backend — the witness is a
local container whose exporter prints to its own log, so nothing survives the container and nothing
is queryable; no configurable sampling policy beyond the SDK's parent-based default, whose honouring
of a caller's `sampled=0` and `sampled=1` is now measured (the provider exposes no sampler knob); no
collector authentication, TLS or retention configuration; and **the web tier sends no trace context of
its own**: the browser has no
tracer and the proxy is not instrumented, so the tier starts no trace; it forwards a valid upstream
`traceparent` and drops an invalid one, which means a trace crosses the proxy only when a caller
upstream of it supplies one. Span export is deployment configuration, the same boundary the log sink
sits behind.

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

`GET /api/v1/metrics/cache` publishes the statistics of every tier the process runs — the two
in-memory caches and Redis — so the cache is observable rather than an invisible optimisation, and
an operator can see which tier is actually serving.

**The middleware body is now tested, which it was not when this document first described it.**
`response_cache` had no test at all, because it returns early when `settings.env == "test"` and
every test runs with that set — the same bypass that kept `test_community.py`'s follow-then-withdraw
case honest. The bypass stays, because the reason for it is real; what changed is that the body
moved out of the middleware closure into `cached_response_for`, taking the cache as an argument, so
nine cases can drive it directly with a real `Request` and a stub origin. Extracting it found two
things reading had not: the body read assumed a streaming response and raised `AttributeError` on
any plain `JSONResponse`, and the cached value was a `StarletteResponse` object, which an
in-memory cache can hold and Redis cannot — so no second tier could ever have sat behind that
interface. The payload is now a plain dict both tiers can hold. The shape is verified on a live
server too, since the unit tests exercise the non-streaming path: MISS, then HITs at
byte-identical length, with `no-cache` returning no header at all.

**What is honest to say about where Redis sits today: it is landed, tested, observable, and now on
one request path — as the response cache's second tier.** `cached_response_for` takes an optional
`shared` tier and reads through it: miss in the process-local cache, look in the shared one, write
back what is found. The reason is in the measurement above — four workers each hold an independent
cache, so a response one process paid for could not be served by another, which is part of why the
gain from extra workers fell away at higher concurrency. The payload being a plain dict rather than
a `StarletteResponse` is what made this possible at all: an in-memory cache can hold the latter and
Redis cannot.

**What has *not* changed is the degraded path, and the distinction is load-bearing.** On this host,
where `redis_available` is false, the shared tier is never written to and every read falls through,
so every code path is the single-tier behaviour that was measured before it. `RedisCache` keeps an
internal `TTLCache` for exactly the case where Redis is down — right for a standalone cache, wrong
for a shared one, because writing into it would build a second process-local cache while leaving
`redis_available` false, and the shared tier would then look healthy to anyone reading its hit rate
while sharing nothing. The `available` property is what prevents that write, and a tier is only
read from when it is serving.

`app/core/redis_cache.py`. `RedisCache` sits behind the same operations and keeps `TTLCache` as a
mandatory second tier: every `set` writes the fallback first and Redis second, so a cache that is
down costs a read path and never a write. The connection is attempted once at construction with a
two-second socket budget; on any failure — refused, timed out, or an authentication handshake the
instance rejects — `redis_available` drops to false and stays there, and every later call takes the
in-memory branch without paying another connect. Keys are namespaced `football_os:` and values are
JSON, so a shared instance cannot collide with another application's data.

`REDIS_URL` is the only knob and defaults to `redis://localhost:6379/0`. `get_stats()` publishes the
URL **only while Redis is serving** — a URL can carry a password, and a metrics endpoint is the
wrong place to put one. *(Corrected 2026-10-20: the URL is now published **redacted** — the
userinfo is parsed off — because the sentence above described an intention the code did not
carry. See the shared-tier section below.)*

**Measured on this host at the time:** port 6379 is occupied, by a Redis that requires a password, so the
default no-auth URL cannot authenticate. The layer behaves as designed there: the first `get` costs
0.008 ms and falls through to memory, the `set` still lands in the fallback and returns true, the
second read hits the fallback (`hits: 1`, `hit_rate: 0.5`), and `redis_available` is false. That is
the path most likely to run in a deployment that has not provisioned a cache, so measuring it beats
asserting it. Wiring the shared tier in did not change that: the warning is emitted once, structured,
and the request that triggered it is answered from the near tier as before.

**Not claimed *then*:** the shared tier had never served a real request. No authenticated instance was
available here, so the cross-process read-through was proven against a stand-in connection — the
`RedisCache` code runs and only its socket is replaced — while the ten degradation cases run against
a mocked client and the `integration`-marked case is the one that needs a live service. **No figure
above is a Redis figure:** the load numbers were all measured with the tier degraded, so nothing
here measures what sharing buys. Degradation is also **sticky for the life of the process** — a
Redis that starts after the process is not picked up until restart. That is the right trade against
paying a failed connect per call, and it is stated so a reader deploying behind a restart-less
rollout can decide otherwise. *(The tier itself is live since 2026-10-20; the load figures above
are still the degraded ones. See the shared-tier section.)*

**Also found by verifying this live rather than by reading:** two different requests came back with
the same `X-Request-ID` and the same `X-Request-Duration-Ms`. `response_cache` was registered after
`request_context` and therefore wrapped it, so a HIT returned its replay before `request_context`
had run — the caller answered under the previous caller's identity, with the previous caller's
duration, and without this request's security headers. The registration order is now the other way
round, so `request_context` is outermost: it sets the id before the cache layer runs (which means a
warning emitted while looking an answer up carries the id of the request that caused it) and it runs
on a HIT. `X-Request-ID` and `X-Request-Duration-Ms` are also filtered out of the cached payload, on
the way in and again on the way out, because an entry a shared tier already holds must not carry one
request's identity across to the next. The case that caught it was run once with the order reverted
to confirm it fails there.

**The second thing found live was worse, because it broke the product's own configuration.**
`Access-Control-Allow-Origin` is a function of the request's `Origin`, but the cache key was path
plus query — so the first caller to fetch a path warmed the cache and every later caller was served
the first caller's header. This project allowlists two origins (`localhost:3210` and
`127.0.0.1:3210`), and the second was answered with the first as soon as a path was warm; a browser
compares that header against its own origin and refuses the mismatch, so one of the two configured
origins silently stopped working. An origin nobody allowlisted was handed one too. Neither is a
security hole — the same comparison is what rejects them — but the first is a correctness bug in the
product's own setup, and it would have been invisible to any test that used a single origin.

`Origin` is therefore the third component of `response_cache_key`, which is what `Vary: Origin`
means. Each component is percent-encoded with `safe=""` so that none can contain a colon, which
also settles a flaw the old `path:query` join had always had: `("/a:b", "c")` and `("/a", "b:c")`
produced the same key. Caching is not disabled by this — the same origin still hits, and a caller
that sent no `Origin` still gets a MISS of its own. `Set-Cookie` was checked as the other
request-dependent header a cache could replay: every call to `_set_refresh_cookie` sits on a POST,
and only GETs are cached, so it does not reach the payload. Verified against a live server as well
as by test — two allowlisted origins each MISS and get their own header, an unallowlisted origin
gets none, and the repeat of the first is a HIT carrying that origin.

### The shared cache tier, live — and the cross-account leak that was behind it

Two findings, and the first one is why the shared tier could not be landed before this section.

**The finding: the cache replayed one account's private answer to another.** Measured 2026-10-20
against a live server with the cache engaged (`ENV=development`, the project's PostgreSQL, the
cache's own tier and the shared tier both enabled). Account A registered, created a player and
asked for `GET /api/v1/players`; account B asked for the same path with its own token:

```
A GET /players -> 200 body: [{"id":"ply_6NzRGkWAhv5hIN-q","name":"Alice Only Player","position":"ST", ...}]
B GET /players -> 200 body: [{"id":"ply_6NzRGkWAhv5hIN-q","name":"Alice Only Player","position":"ST", ...}]
LEAK: True - B was served A's player
```

The key was path + query + origin and named no caller, so B's request matched A's stored answer
and B was handed A's football identity with a 200. Nothing in the response said so: the cached
payload was the leak, not a header, and the replay was indistinguishable from a normal answer.
Every private `GET` in this API was exposed the same way — the caller's own player, their
progression, their club, their agent memory.

**The fix: the key names the caller, and the shared tier never sees a private answer.** Two halves,
because the two tiers are two different things.

* The **near** tier (one process's memory) is keyed by `caller_identity(credential)` — a truncated
  SHA-256 of the `Authorization` header, never the header itself. A private answer is stored under
  its caller's name, so no other caller's request can match it, and the same caller still gets a
  `HIT` in the process that computed it.
* The **shared** tier follows RFC 9111 §3.5: *a shared cache must not store a response to a request
  that carries an `Authorization` header*, because that response is not one every user may see. So a
  credentialed request is neither read from nor written to the shared tier, and the shared store
  holds public answers and nothing else.

`Authorization` is the only credential this API honours (`current_user` reads a bearer token and
nothing else), so it is the only one the cache has to consider. The cost is that a private answer
is not shared between workers — the price of never sharing one account's answer with another, and
of keeping user data out of a store every worker can read.

Re-measured on the same live server, same script, same two accounts:

```
A GET /players -> 200 body: [{"id":"ply_z2wS2KUmjfOehFau","name":"Alice Only Player", ...}]
B GET /players -> 200 body: []
LEAK: False - B was served its own answer
```

and the shared store held no key for that path at all — the private answer was never written to it.

The gate is `tests/test_response_cache_privacy.py` (10 cases): the identity is a hash and not the
credential, two callers have two keys, two callers never see each other's body, the same caller is
still served from the near tier, a private answer never reaches the shared tier, a public answer
does, a second reader with an empty near tier is served from the shared one, and the same thing
happens against the real middleware stack with two real accounts.

**The second finding: the metrics door published the cache's password.** `get_stats()` published
`redis_url` — and a Redis URL is where the credential lives
(`redis://:secret@host:6379/0`). The document above had already said that "a URL can carry a
password, and a metrics endpoint is the wrong place to put one", while the code published the
whole URL to any signed-in caller as soon as the tier was serving, and the connection log line
printed it too. `redact_url()` now parses the URL and drops the userinfo, keeping the host, the
port and the database number, and both the published stats and the log line use it. The gate
covers a password containing `@` and `/` — a naive string split would not have removed it.

**The tier, live.** The project now publishes an authenticated Redis of its own
(`infra/docker-compose.yml`, `redis:7-alpine`, `--requirepass`, host port 63790 — not 6379,
which on this host belongs to another application's cache), and CI starts the same image with the
same password and the same URL. Measured on this host, 2026-10-20:

* `redis-cli ping` without the password answers `NOAUTH Authentication required.`; with it, `PONG`.
* Two **server processes** (ports 8099 and 8098, each with its own empty process-local tier) were
  asked for the same public path:

```
server 1 -> 200 X-Cache: MISS bytes: 11571
server 2 -> 200 X-Cache: HIT  bytes: 11571
same answer: True
keys in the shared store: ['football_os:http:%2Fapi%2Fv1%2Fworld%2Fteams:::']
the shared store holds a payload of 13402 bytes
```

Server 2's own tier was empty, so its `HIT` can only have come from the shared store — the
cross-process read-through this document used to say was proven "against a stand-in connection".
The key's four components are visible in it: path, query, origin, and the caller's identity
(empty here, because the request presented no credential).
The gate is `tests/test_redis_shared_tier.py` (10 cases): the compose file publishes an
authenticated cache of its own, CI starts the same one, the password never leaves the process, a
cache that refuses the handshake degrades and says so rather than pretending to serve, and a key
written by one operating system process is read by **another operating system process** through
its own client.

### The trace backend: spans the project stores itself, beside the collector that now runs

The observability claim this milestone could not make was about OpenTelemetry: the SDK was wired,
the span path was measured through an in-memory exporter, and **no collector ran on this host** at
the time — so no span had ever reached a real backend. The claim was honest. The repository has
since answered it twice: a span now reaches a real collector (the `observability` profile described
in the tracing section above), and it reaches the project's own backend, below.

**The store.** `app/core/span_store.py` is an ordinary OpenTelemetry *exporter* that writes each
finished span into `request_spans` (migration `0029`). It is installed behind the SDK's
`BatchSpanProcessor`, so the write happens on the exporter's thread and the request path never pays
for it. The rows carry the span's own identifiers — `trace_id` groups a request's spans, `span_id`
names one, `parent_span_id` names the span it hung from — so the tree is *stored* rather than
rebuilt by whoever reads it, plus the span's own start, end, duration and attributes.

Two rules the exporter holds to, both of them the kind a trace backend that has taken an API down
would break:

* **A store failure is never a request failure.** The exporter catches everything and returns a
  failure result; the batch processor then drops the batch. Measured: a store whose session factory
  raises answers `FAILURE` and raises nothing into the caller.
* **The store is bounded.** Every export also deletes the spans older than the retention window
  (seven days), so an instance that runs for months does not accumulate traces forever. Measured: a
  row dated eight days back is deleted by an export while one dated six days back and the span the
  export itself wrote survive; the two ages are literal, so widening the window reds the case.

**The door.** `GET /api/v1/traces/{trace_id}` returns the spans of one trace, oldest first, each
with the parent it hung from. It is an **operator's window**, and it asks for the operator's
standing: only an `admin` account may read a stored trace. A trace id nobody stored answers
`404 no_such_trace` — absence must not confirm which ids exist — and a non-admin is refused
`403 insufficient_role` before the lookup, so the refusal does not differ between an id that exists
and one that does not.

**Why the standing is the fix.** A stored `SERVER` span carries the request's concrete
`http.target`: measured on a share route as `/api/v1/share/boards/secret-share-token`, the token
itself, in a span whose attributes also carry the full `http.url`. `request_spans` has no column
that says whose request a trace was, so with the door open to any authenticated account, a player
holding (or guessing) a trace id could read another account's path and query string. The door had
been `current_user`-gated only.

**What it is off by default for.** `TRACE_STORE_ENABLED=1` turns the store on; the default is off
because it writes a row per span, and a deployment that runs a collector has a better place for
them. The OTLP path is untouched, and the two are independent: a deployment can send spans to a
collector and keep them in the database, or use either alone.

**Measured** (`tests/test_trace_store.py`, 8 cases): a finished span is stored with its own timings
and identifiers; a child span names the span it hung from, read back through the door; a broken
store reports failure without raising; an export deletes an eight-day-old row, keeps a six-day-old
one and the span it just wrote; an admin reads a stored trace and gets 404 for an unknown one; a
player is refused `403 insufficient_role` for both a stored id and an unknown one, while an admin
control reads the same stored trace back. Arms on copies of the tree: removing the standing check
reds the refusal case alone, at `assert 200 == 403` with the stored span — including `http.target`
— in the refusal's own response; changing the standing to `("fan",)` reds the refusal at
`required == ['fan']` and reds both admin door cases at `assert 403 == 200` and `assert 403 == 404`;
removing the prune call reds the retention case alone (`an eight-day-old span survived`), widening
`RETENTION` to 365 days reds the same case alone, and a prune that deletes every row reds it at
`a six-day-old span was deleted with the expired ones` plus the two store-shape cases. The door's
docstring changed, so `docs/api/openapi.json` was regenerated, and the contract, spec-audit and
both census gates are green at the new tree.

### What sharing buys, measured with the tier live

Every load figure above was taken with the tier degraded, and the document said so: *"no figure above
is a Redis figure"*. The tier is live now, and the shared tier counts its own hits, so the question
can finally be asked as a paired measurement on one host: **the same code, the same minutes, the
same endpoint, one server with the shared store and one without.**

`/api/v1/healthz`, 15 seconds per run, this host (a shared Windows workstation, so the absolute
numbers are a floor and the pairs are the point):

| workers | concurrency | tier live | tier degraded | difference |
| --- | --- | --- | --- | --- |
| 1 | 10 | 201.71 req/s (p50 29.31, p95 81.56) | 236.38 req/s (p50 24.39, p95 76.47) | **−34.67 (−15%)** |
| 1 | 50 | 175.22 req/s (p50 198.75, p95 804.39) | 168.05 req/s (p50 193.39, p95 898.40) | +7.17 (+4%) |
| 4 | 10 | 187.84 req/s (p50 30.66, p95 151.36) | 175.52 req/s (p50 30.44, p95 205.64) | +12.32 (+7%) |
| 4 | 50 | **84.34 req/s** (p50 354.79, p95 1955.24) | 39.86 req/s (p50 275.34, p95 1205.20) | **+44.48 (2.12×)** |

Three things this says, and the third is the one worth having.

* **With one worker the shared tier is a small tax** (-15% at c10): the process-local tier already
  answers every repeat, so the shared store is a round trip paid for nothing.
* **With four workers at saturation the shared tier more than doubles throughput** (2.12× at c50):
  four workers each holding their own cache is four caches, and at c50 the requests are spread
  across them, so the working set is four times as large as one worker needs. One store is one
  cache, and the database leaves the loop.
* **The tail gets worse, and the reason is the same round trip**: p95 1955 ms with the tier live
  against 1205 ms degraded. More requests are served, and the ones that miss pay for the shared
  store before they pay for the database.

And the attribution is the counters' own: worker B, whose own tier was empty, answered **12 HIT /
0 MISS**, every answer one worker A had already paid for, with B's shared tier counting 4 hits and
0 misses. A worker with hits above zero has served an answer another worker paid for - which is
the whole claim of a shared tier, and the one the load numbers above could not make.

**What this does not say.** These are one host's numbers, on a workstation shared with roughly two
hundred other processes, and the endpoint is the cheapest door the API has. The published load
figures earlier in this document are still the ones a reader should quote; these are the *pair*,
and the pair is the claim.

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
it overall or per feature.

**The formula now lives in `app/core/percentile.py`, because `/metrics/system` needed a second set of
percentiles.** That door's four headline rows — `request_count`, `error_count`, `avg_latency_ms`,
`p95_latency_ms` — were reading the model-call ledger: the first two were `COUNT(ModelCall.id)` and
its failed subset, the latencies came out of the same table. So the figures an operator looks at first
answered how much AI the product bought rather than how much traffic it took, and a door answering 404
all day, a limiter firing, a worker wedging, moved none of them. `avg_latency_ms` duplicated
`/metrics/database`'s own `avg_model_call_latency_ms` — nothing was lost by moving it.

`app/core/request_metrics.py` records what this process served, from `request_context`, which is the
outermost user middleware and therefore the only place that sees every response. `error_count` is the
5xx subset: a 404 says a client asked the wrong thing, a 500 says the server broke, and a row that
cannot tell them apart is not an error rate. Durations go into a deque bounded at the same 2000 rows,
for the reason the profile's sample is bounded — and the arithmetic is imported rather than copied, so
the two percentiles cannot drift into disagreeing about the same sample. The scope is stated in the
answer (`scope: this process`): every worker holds its own figures, which is the same answer `uptime`
already gives and the two belong together.

The 500 path is the one that needed the extra line. An unhandled exception is rendered by
`ServerErrorMiddleware`, which sits outside every user middleware, so the count would otherwise be
taken only for requests that succeeded — and the failures that matter most would be the missing ones.

The case that pinned the definition found a mistake in the *test*: it asserted `50/95/99` over rows
`0..99`, and `n = ceil(P/100 × N)` makes the correct nearest-rank answers `49/94/98`. The code was
right and the assertion was wrong; the test now carries the formula in a comment so the next reader
does not have to re-derive it.

### Observability — the system row answers the system

`GET /api/v1/metrics/system` had four rows that answered something else, and two of them answered it
so misleadingly that the number worked against the reader rather than for them.

`uptime_seconds` was `0.0`, with a comment asking for process start time tracking that nobody made
happen. The row carried the field in its response model, in the OpenAPI schema and in its own
docstring — the promise was everywhere and the answer was a constant. Uptime is not a number that is
merely wrong when zero: it is the one figure that tells "restarted seconds ago" from "has been up for
a week", so the placeholder reported both at once. `app/core/runtime.py` now captures the start at
import, the last moment shared by every process. It cannot live in `main`, which is where the obvious
place would put it: uvicorn's `--reload` runs a supervisor and a worker that import independently, and
each having its own clock is the correct answer to "this process" rather than the supervisor's age.
`perf_counter` rather than `time`, so a host clock correction shows up as neither an outage nor a jump
into the future.

`active_users_today` counted `DISTINCT ModelCall.user_id` over today. That is a real question under
another name — how many accounts bought an AI call — and the row answered it in place of the one it
promised. A user who logged in and spent the day on training, tactics or boards was active today and
counted as nobody, so an operator watching this number would read a busy product as an empty one;
of the two directions for the row to be wrong, that is the one that hides the product working.
`User.last_login_at` is the column that records what the row promises, and login was already writing
it. The path that never wrote it was registration, which hands back a usable access token and is
therefore the account's first session — the newest accounts were invisible to the very number whose
job is to notice them.

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
* `scripts/backup_db.sh` — full (`pg_dump -Fc`) or incremental, with S3 upload, post-backup
  verification via `pg_restore --list`, and local cleanup keeping the last 7 days. An
  *incremental* is a write-ahead-log archive, so the script refuses (exit 2) unless the server
  answers `archive_mode=on`, reports the last archived segment from `pg_stat_archiver`, and — when
  `REPLICA_HOST` is set — checks replay lag against `REPLICA_LAG_CEILING_SECONDS` (default 300).
* `scripts/restore_db.sh` — restore into a named scratch database, replayed with `alembic upgrade
  head` (run from `apps/api`, the one directory carrying `alembic.ini`), parallel restore on 4
  jobs. The target name must pass the same scratch policy `scripts/qa_db.py` uses to decide what it
  may drop, and success is printed only after `pg_restore`'s exit code *and* the restored table
  count have both been read.
* `scripts/dr_lib.sh` — the connection coordinates both scripts use, derived from
  `infra/docker-compose.yml` (`54321`, `football_os`, `football`) instead of typed defaults, and
  refused (exit 2, with the match count) if the compose file does not carry exactly one host-port
  mapping and one assignment per variable.

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
pathways remain inspection-verified. What changed is the worst claim in this document: the drill's
*commands* were executed inside the container, and that execution found a defect no gate could
see. The *scripts* were not what ran.

**Corrected 2026-10-20 — the drill exercised the commands, not the pair.** Nothing in this
repository invoked `scripts/backup_db.sh` or `scripts/restore_db.sh`; they were described here and
never run, and running them found five defects, each measured before it was fixed:

1. **`incremental` was a no-op that returned success.** It logged "Checking WAL archive status",
   ran `pg_waldump -n 1` when the host had it, and exited 0 — no artifact, no `pg_dump` call, no
   question asked of the server. Measured with stubs on the HEAD script: rc=0 and an empty backup
   directory, a success shape around an absent backup.
2. **Both scripts typed the server coordinates.** `PGPORT=5432`, `PGUSER=football`,
   `PGDATABASE=football_os` — while the compose file this project ships publishes PostgreSQL on
   **54321**, the port every other tier derives. The default was a second copy of a fact the
   compose file already owned, and the copy was stale.
3. **The restore's target was a name its own policy refuses.** The default was
   `football_os_restore`, and the script dropped it with an interpolated, unquoted identifier
   before asking anything: `DROP DATABASE IF EXISTS $TARGET_DB`. `scripts/qa_db.py` already owned
   the rule for what this project may drop and re-create; the restore script did not consult it.
4. **The failure branch was unreachable.** `pg_restore` was followed by `if [[ $? -eq 0 ]]` under
   `set -euo pipefail`: a failed restore aborts the script at the command, so the branch that was
   meant to report the failure never ran, and no line naming the status was ever printed.
5. **Alembic ran from a directory with no `alembic.ini`, and success was printed without a
   measurement.** The script `cd`'d to the repository root; `alembic.ini` exists only at
   `apps/api/`. Nothing counted the restored copy before announcing completion.

The fix, in the same pair: `scripts/dr_lib.sh` derives the four coordinates from
`infra/docker-compose.yml`, refusing (exit 2, with the match count) unless the file carries exactly
one host-port mapping and one assignment per variable; the restore hands its target to
`scripts/qa_db.py --assert-scratch`, the policy the qa script already uses to decide what it may
drop; `pg_restore`'s status is captured with `rc=$?` so the error line runs; alembic runs from
`apps/api`; and success is printed only after the restored table count has been read. An
`incremental` now asks `SHOW archive_mode`, reads `pg_stat_archiver`, and — with `REPLICA_HOST` set
— the replay lag, refusing with exit 2 on every non-answer instead of reporting a backup.

`apps/api/tests/test_dr_scripts.py` is the gate: **14 cases**, run against the shipped scripts with
stub `psql`/`pg_dump`/`pg_restore`/`pg_isready`/`python` in front and no server, so every leg —
including restore failure — is reachable offline. It reads the compose file rather than typing the
port, runs the shipped `dr_published_pg_port` and the shipped policy CLI instead of paraphrasing
them, and holds `pg_dump`'s argv to the derived coordinates. **14 passed** on the fixed pair;
**1 passed / 13 failed** against HEAD's scripts on a sibling `git archive` plane (528/528 files),
with the red names matching the defect list above — the reverse control that makes this a gate
rather than a description.

### Performance — a measured load run

A recorded run of `scripts/bench_api.py` from 2026-10-13, against the local tier (uvicorn, single
process, the API on the project's PostgreSQL container, `ENV=development`, the response-cache
middleware enabled, localhost loopback, concurrency 10, 15 s per endpoint) — the steady-state shape,
where the sibling "Load" section below measures the same harness at saturation:

| endpoint | requests | throughput | p50 | p95 | p99 | errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET /api/v1/healthz` | 4200 | 279.63 req/s | 20.51 ms | 80.62 ms | 331.24 ms | 0 |
| `GET /api/v1/world/competitions?page_size=12` | 4169 | 277.84 req/s | 22.38 ms | 64.71 ms | 304.02 ms | 0 |
| `GET /api/v1/tactics/status` | 3885 | 258.15 req/s | 24.65 ms | 69.27 ms | 188.02 ms | 0 |

What these numbers are: the cached read path, on one process, on a developer machine. The two content
endpoints sit behind the 60-second response cache the milestone shipped, so steady-state traffic like
this measures the cache plus the middleware chain more than it measures PostgreSQL. What they are
**not**: a capacity ceiling, a production figure, or a soak test — no saturation was reached (the
loopback saturated the client before it saturated anything else), nothing ran longer than 15 s, and
no Redis was in the path. Reproduce with `MSYS_NO_PATHCONV=1 python -m scripts.bench_api --endpoint
/api/v1/healthz --concurrency 10 --duration 15` — the env var matters on Git Bash, whose argument
path-mangling silently rewrites a leading-slash endpoint into a Windows path
(`http://127.0.0.1:8731C:/Program Files/Git/api/v1/healthz`) and turns the whole run into one long
404 measurement that *looks* like a healthy throughput figure. This run's own first
three attempts did exactly that, which is why the mangled URL is printed before the run and the
harness env var is part of the recorded command.

## The figures, with their plane

| measurement | plane | result |
| --- | --- | --- |
| `pytest tests/test_cost_advisor.py tests/test_latency_profile.py tests/test_metrics.py tests/test_request_metrics.py tests/test_agents.py tests/test_answer_census.py tests/test_authorization_census.py tests/test_community.py tests/test_account_deletion.py -q --tb=line` | SQLite, local venv, working copy | **127 tests / 0 failures / 0 errors / 0 skipped**, rc=0, wall **65s** |
| `ruff check app tests` | same | All checks passed |
| `ruff format --check` over the new modules | same | all formatted |
| `mypy` over `cost_advisor`, `latency_profile`, `metrics`, `request_metrics`, `percentile`, `runtime`, `response_headers`, `cache`, `redis_cache`, `logging`, `main` | same | no issues |
| `pytest tests/test_openapi_contract_currency.py tests/test_spec_audit_currency.py -q` | same, against `HEAD` | 13 tests, rc=0; since 2026-10-23 the contract's byte case normalises the checkout's line endings — a fresh `core.autocrlf=true` worktree at `394cd10` checked the contract out 484939 bytes / CRLF against the exporter's 467634 / LF, and the raw comparison was red on equal content; on that still-CRLF plane the five documentation gates are **38/38 rc=0**, and a one-byte contract change (`3.1.0` → `3.1.1`) still reds the case |
| `pytest tests/test_tracing.py -q` | SQLite, working copy | **7 tests / 0 failures**, rc=0; forced always-on reds only the sampling case (`got 2`), forced always-off reds it (`got 0`) |
| `pytest tests/test_trace_store.py -q` | SQLite, working copy; arms on a copy of the tree | **8 tests / 0 failures**, rc=0; guard removed → only the refusal case red (`assert 200 == 403`, the stored span in its response); standing `("fan",)` → refusal red at `required == ['fan']`, both admin door cases red (`assert 403 == 200`, `assert 403 == 404`); prune call removed or `RETENTION` widened to 365 days → only the retention case red (the eight-day row survives); prune deletes all rows → retention case red at the six-day row, plus the two store-shape cases |
| one `GET /healthz` through a live API with `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` | live uvicorn + `otel/opentelemetry-collector:0.111.0`, debug exporter, SQLite | `SERVER` span `GET /healthz` read back from the collector log, resource `service.name=football-os-api`, `deployment.environment=development`; **before the `/v1/traces` fix the same walk logged `404 Not Found` and exported nothing** |
| `node scripts/qa-proxy-gate.mjs` | `apps/web`, working copy | **6 checks / 0 failures**, 131 files; 8/8 arm planes matched |
| one `GET /api/v1/traces/…` through a production web build with `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01` | web `next start` on 3221 → API with `TRACE_STORE_ENABLED=1`, fresh SQLite | 401 from the auth-gated door, and four `request_spans` rows with the caller's `trace_id`, the `SERVER` row parented by `00f067aa0ba902b7`; the no-header control left an unparented `SERVER` span in trace `964b3f829197972596588c36b1848188` |
| contract paths after the three metrics doors | `docs/api/openapi.json` committed | 179 → **182** |
| `git grep -li agents -- apps/api/app` | committed tree | 13 → **14** (`services/agents/orchestrator.py`) |
| `python -m scripts.bench_api --endpoint /api/v1/healthz --concurrency 10 --duration 15` | live uvicorn, one worker, Postgres 54321, demo mode, response cache **on** | **90.80 req/s**, p50 71.50 / p95 99.29 / p99 153.21 ms, **0 errors**, 1375 requests |
| same, `--concurrency 50` | same | **52.54 req/s**, p50 612.12 / p95 2743.91 / p99 4481.11 ms, **0 errors**, 829 requests |
| `--endpoint /api/v1/players --concurrency 10` (unauthenticated) | same | **76.08 req/s**, p50 84.93 / p95 325.97 / p99 1646.32 ms, 923 responses all 401 |
| `--healthz --concurrency 10`, **`--workers 4`** | same, four uvicorn workers | **117.43 req/s**, p50 77.36 / p95 188.24 / p99 385.36 ms, **max 655.91 ms**, 0 errors |
| `--healthz --concurrency 50`, **`--workers 4`** | same | **55.83 req/s**, p50 564.11 / p95 2843.56 / p99 4070.82 ms, 0 errors |

The contract and audit figures were recomputed against the committed tree, not the working copy,
because `test_spec_audit_currency.py` reads `git show HEAD:…`. Two doc landings were needed to make
that pass — one for the agents scan, one for the contract-path count — and both are recorded in the
audit's own numbers rather than left stale.

### Load — the ceiling this tier actually has, and the one statistic that lies

`scripts/bench_api.py`, three runs against a live uvicorn (single worker, `--reload` off so the
watcher is not in the numbers), Postgres on 54321, demo mode, response cache active because
`env=development`.

**Throughput saturates rather than scales.** Going from 10 to 50 concurrent clients — five times the
load — *cut* throughput from 90.80 to 52.54 req/s while p50 rose 8.6× (71.50 → 612.12 ms). That is
the signature of a saturated single process, not a slow one: the server stopped absorbing requests
and started queueing them. **~90 req/s is this tier's ceiling on this host**, and it is a single
uvicorn worker, so the honest next question — what more workers buy — is unmeasured here and is not
implied by these figures.

**`max` is not a quotable statistic from this harness.** At concurrency 10 it came out 15091 ms in
one run and 15131 ms in another, against a 15-second window — one request starved for essentially
the whole run, reproduced in both. p99 over the same runs was 133 and 153 ms. Quote p99; the max
measures this host's scheduler, not the API. At concurrency 50 the max was 7389 ms, *below* the
window, because workers still mid-request when the run ends are abandoned after a 5-second grace and
never enter the results at all.

**Zero errors in all three runs**, so the ceiling here is latency, not correctness.

**Four workers buy real headroom at low load and almost none at high load**, which is the shape the
bottleneck predicts. At concurrency 10, four workers lifted throughput 90.80 → 117.43 req/s (+29%);
at concurrency 50 they lifted it only 52.54 → 55.83 req/s (+6%). Below saturation the Python
process is what is scarce, so more of them help; above it the scarce thing is Postgres and this
host, and more processes merely queue behind the same dependency.

**The long `max` was a single-worker artifact, and four workers prove it.** The 15-second outliers
that reproduced twice at one worker came out at **655.91 ms** with four, against the same 15-second
window and the same endpoint. Nothing about the API changed — only how many processes were waiting
to accept. So the diagnosis above was right, and it is now settled by measurement rather than by
argument: at one worker a single request can be starved for essentially the whole run, and the fix
is not a tuning knob, it is a second process. The cost is a longer p99 at low concurrency (153 →
385 ms), because four workers also means four times the concurrent work against the same database.

**The 401 door has a slower tail than the health check** — p99 1646 ms against 153 ms. A door that
refuses every unauthenticated caller still reaches the dependency before it answers, and the tail is
where that shows.

These numbers are a **floor, not a ceiling**: this host is a Windows workstation shared with roughly
two hundred other processes. They are published because a harness that has never been run publishes
nothing, and because the *shape* — saturation at one process, max unreliable, p99 stable — will
survive the move to quieter hardware even though the absolute figures will not.

## The account's own erasure, and the claim that said it did not exist (2026-10-21)

M12's gate names **account-level erasure** as a condition, and `DATA_POLICY.md` §3 said, in as many
words, that it was *not implemented, so not claimed as a feature*: "full account erasure (`DELETE /me`
with cascade and aggregate anonymisation) … a UI that offered them would be a lie, so it does not."

**The door, the service, the preview and the panel have all been there since the account tier landed.**
`DELETE /api/v1/auth/account` (`apps/api/app/api/v1/auth.py`) erases the account: the rows it owns go
through the schema's own cascade, the rows with no foreign key to it (jobs, knowledge queries, revoked
tokens, usage events) are deleted explicitly, the **aggregates are retained with the account id
removed** rather than deleted — provider cost totals and operational action counts survive, the person
does not — and the account's private media is unlinked from storage with the byte count reported. A
phrase (`DELETE`) and the current password are both required; the tenant-orphan case is refused
**before any write**; and `GET /api/v1/auth/account` prints the whole inventory without changing a row,
so the panel can name what the button will take before the button is armed.

**What was missing was the evidence, and the record was wrong in the other direction.**
`apps/api/tests/test_account_deletion.py` had four cases — the session and the phrase, the cascade with
the media and the identity, a storage key that leaves the private directory, and the last owner of a
tenant with other members — and **no walk touched the web tier's control at all**: the most destructive
button the interface offers had never been pressed by a browser. `visual-qa.mjs` §10a now does, on a
throwaway account (the walk's own account has a season, a club, a training log and eleven published
screens to its name by now):

| what the walk proves | how |
| --- | --- |
| the panel names what it destroys before it destroys it | the inventory's own counts, read out of the DOM |
| the erase control stays inert until the phrase **and** the password are there | the button's `disabled` before, after the phrase alone, and after both |
| the wrong password is refused, and the account is still there | the door's own refusal beside `GET /auth/me` still answering with the account's email |
| the erasure takes the account, and its session stops working | `identity_retained=false` beside `GET /auth/me` answering **401** |

And `DATA_POLICY.md` §3 now says what is true: the account erasure is implemented and walked, and the
thing that is still **not** implemented — per-entity visibility toggles — is still named as
unimplemented, because a UI that offered it would be a lie. (The policy's other stale claim, that
per-video deletion was missing, is corrected in
[docs/M5_WEB_VERIFICATION.md](M5_WEB_VERIFICATION.md): the door has been there since M5 and the walk has
pressed it in a browser — what the delete *did* leave behind was the clip's own analysis job, and that is
fixed.)

## The gate's security half: a first-party probe, and the report it leaves (2026-10-22)

M12's gate says **"load + pen test report clean"**. The load half had a harness, a ceiling and a paired
measurement. The security half had a code-level census (§60), the answer-table gates (§51) and a list of
fixed defects — and no report produced by attacking a running server. The project cannot commission a
third-party penetration test from inside its own repository, so it did the two things it can: it shipped
the battery, and it left the report.

`scripts/security_probe.py` reads its population from the committed contract rather than from a list in
the script — the same `docs/api/openapi.json` the web client and the currency gates read. At contract
SHA-256 `31000605776d55d3cf0881358087391c65a0cd807869661ed86abe157c88b32e` that population is **212
secured operations, 52 public operations and 91 private GET paths**, with floors of 200/40/85 printed on
every run. Ten checks, each one an HTTP exchange against a live uvicorn rather than a test client:

| ident | what was measured | result |
| --- | --- | --- |
| C0 | the door population comes from the contract and is not empty | 212 / 52 / 91 |
| S1 | every secured operation refuses a caller with no credential | **212 knocked, 212 × 401**, 0 deviations |
| S2 | a token with a broken signature is refused | 401, coded `code`/`message` |
| S3 | one account's row is absent to another, in the read and the listing | owner 200; stranger **404** on read and patch; absent from the stranger's listing |
| S4 | the public cache serves, and a private cached answer never crosses callers | private A/B MISS→HIT, stranger never received the owner's row; public MISS→HIT, identical body, **different request ids** |
| S5 | a login burst is refused, coded, with a retry time | 10 × 200 then **429 at the 11th**, `Retry-After: 295`, `rate_limited` |
| S6 | refusals are one coded shape, echo nothing and leak nothing | 422 `validation_error`, exactly `loc`/`msg`/`type`, **no leak marker** in four bodies |
| S7 | the security headers and a request identity are on every answer, including a refusal | `nosniff` on 200 and 401, referrer policy, distinct ids, numeric durations |
| S8 | only a configured origin is echoed; a rogue one is never answered | configured 200 + ACAO + credentials; rogue 200 with **no** ACAO; rogue preflight 400 |
| S9 | the refresh cookie's flags and path | httpOnly, `SameSite=strict`, `Path=/api/v1/auth`; `Secure` absent in development |

Three runs, because the cache has two configurations worth attacking and the deployment engine should
not be a claim carried over from SQLite. Run A had the shared tier degraded (the default Redis on 6379
refused the handshake) and answered **10/10, 0 failed, 0 server errors** in 7.83 s. Run B pointed
`REDIS_URL` at the project's own authenticated Redis on 63790 — the tier that was the source of the
cross-account replay Item 6 fixed — and answered the same **10/10, 0 failed, 0 server errors** in 19.61 s.
Run C repeated run B's configuration against the project's PostgreSQL, the engine the deployed API runs
on, and answered the same **10/10, 0 failed, 0 server errors** in 11.37 s; its report reads the same 212
doors answering 401, the same private and public `MISS → HIT` pairs, and the same 429 at the 11th login.
S4 is constructed so the negative is not vacuous: the private `HIT` and the public `MISS → HIT` are read
before "the stranger never received the owner's row", so the cache is proven to have been serving at the
moment the isolation held.

The tier's own legs were re-measured over the same bytes, with the Redis cases now able to run:

| measurement | plane | result |
| --- | --- | --- |
| `pytest` over the 23 M12 test files | SQLite, working copy | **180 tests / 0 failures / 0 errors / 3 skipped**, 208.893 s |
| the same 23 files | PostgreSQL, `REDIS_URL` at the project Redis | **180 / 0 / 0 / 1 skipped**, 421.752 s |
| `mypy app` | working copy | 154 source files, no issues |
| `ruff check .` | `apps/api`, plus the probe under `scripts/` | all checks passed |

Two of the three SQLite skips executed on the PostgreSQL leg — the wrong-password degradation and the
cross-process shared-key case in `test_redis_shared_tier.py`. The one that remains,
`test_redis_cache_real_integration`, is marked `integration` and needs that selection as well as a live
server; it is not silently counted as a pass.

The full report, its reproduction commands and its list of boundaries is
[docs/SECURITY_PROBE_REPORT.md](SECURITY_PROBE_REPORT.md). The boundaries that belong in this document's
own ledger: an unknown path and a wrong method are still answered by Starlette with a string `detail`
(recorded by the probe, not converted — they are not doors); the refresh cookie's `Secure` flag is
production-gated and this server was development; no TLS, CSP or HSTS was exercised; and **no third-party
penetration test was commissioned**.

## What M12 does not claim

* **No third-party penetration test.** The gate's security clause is answered by the project's own probe
  — ten checks, 212 private doors, two live accounts — run against a live server with the report at
  [docs/SECURITY_PROBE_REPORT.md](SECURITY_PROBE_REPORT.md). An independent tester, a source review by an
  outsider, dependency and image scanning, and browser-side adversarial testing are all outside what this
  run did. A clean probe is the absence of ten specific failures, not the absence of vulnerabilities.

* **The Redis tier is live and authenticated (2026-10-20), and what sharing buys is now measured.**
  The project's own cache serves: `infra/docker-compose.yml` publishes an authenticated
  `redis:7-alpine` on host port 63790, CI starts the same image with the same password and URL,
  and the shared tier's own hit rate is counted where it happens (a read Redis answered is a hit,
  a read it did not is a miss) and published by the metrics door. Two server processes, one store,
  measured on this host:

  | worker | X-Cache over 12 requests | its near tier | its shared tier |
  | --- | --- | --- | --- |
  | A, alone | 9 HIT / 3 MISS | hits 9, misses 5 (0.64) | **0 hits**, 4 misses — its near tier answered first |
  | B, own tier empty | **12 HIT / 0 MISS** | hits 9, misses 5 (0.64) | **4 hits**, 0 misses, hit rate 1.0 |

  Every answer worker B served was one worker A had already paid for, and B's shared hits are
  counted in B's own process - which is what makes the figure attributable to this application
  rather than to the Redis instance. **The load figures above are still the degraded ones** and
  still a floor: they were taken before this landing, and nothing here re-measures throughput.
  What changed is the *sharing*, not the speed, and the two are not the same claim. The
  degradation paths are unchanged and still measured: a cache that refuses the handshake drops to
  the in-memory fallback, says so, and stays down for the life of the process — a Redis that
  starts after the process is not picked up until restart. One defect the landing exposed is
  fixed and one is not: the metrics door no longer publishes the cache's password, and the
  **cross-account replay the shared tier would have spread across workers is closed** (the near
  tier's key names the caller, and the shared tier never stores a credentialed response), but
  the cache still holds no user data at all only because private answers are excluded from the
  shared tier — the door that decides what a response may be cached as is `cached_response_for`,
  and a new door that returns caller-specific data has to remember that a credentialed `GET` is
  keyed by its caller and never reaches the shared store.
* **No external log sink.** The JSON formatter is the contract with a sink that deployment wires,
  and the contract itself is now tested rather than asserted — `tests/test_logging.py` parses the
  emitted line, checks the standard fields, extras and exception text, and walks a request id from
  the header through the middleware into the emitted record. That test was written because the walk
  was broken: `RequestIDFilter` built its own `ContextVar("request_id")` while `app.main` built a
  second one with the same name and set *that*, so every line carried `"request_id": ""`. An empty
  string is a legal value for a string field, so nothing failed — an aggregator grouping on the
  field would simply have put every request in one bucket. One variable now, defined where the
  filter lives and imported by `main`.
* **The trace backend now exists (2026-10-21), and a real collector followed (2026-10-22).**
  OpenTelemetry is wired and the span path is measured through an in-memory exporter; a live walk
  now also exports through OTLP into a local collector shipped in this repository
  (`infra/otel-collector.yaml`, compose profile `observability`), whose log carries the `GET
  /healthz` `SERVER` span and its `service.name=football-os-api` resource. That walk found the
  module had been POSTing to the endpoint's root instead of `/v1/traces` — the collector answered
  404 — and the fix plus its test are in `app/core/tracing.py` and `tests/test_tracing.py`. The
  project's **own** backend answers too: `app/core/span_store.py` is an ordinary OpenTelemetry
  *exporter* that writes each finished span into `request_spans`, and `GET
  /api/v1/traces/{trace_id}` reads a request's spans back. The store is off by default
  (`TRACE_STORE_ENABLED=1` turns it on) because it writes a row per span; the OTLP collector path is
  untouched and the two are independent. The door is an **operator's window**: only an admin may
  read a stored trace, because a stored `SERVER` span carries the request's concrete `http.target`
  (measured on a share route, token included) and the store has no ownership column. What is still
  not claimed: a **configurable sampling policy** is a deployment concern — the store keeps what the
  SDK produced, the provider runs the SDK's parent-based default and the tests pin both halves of it
  (a valid caller `traceparent` is continued, a `sampled=0` one is honoured), but no sampler or rate
  is exposed as configuration; the collector witness is a local container with the debug exporter,
  not a durable or queryable backend.
* **No off-host backup pathway executed.** The restore drill ran `pg_dump` → `pg_restore` inside
  the project's own container; S3 upload and WAL archiving remain inspection-verified only.
* **The load figures are a floor, and both worker counts were measured on one host.** Five runs are
  recorded above against a live uvicorn — one and four workers, two concurrency tiers and one
  unauthenticated door — on a workstation shared with some two hundred other processes. They are not
  extrapolated to production hardware. The harness's `max` is unreliable at *one* worker, where it
  reproduced at ~15.1 s against a 15-second window and fell to 656 ms once a second process
  existed, so p99 is the figure to quote; the harness now states its denominator.
* **No cost guarantee, and honouring the cap is still a per-caller duty.** The advisor reports; the
  router decides. Two doors check `budget_exhausted()` at the call instead of trusting a caller to
  stop on its own: `/knowledge/ask` refuses with 429 `ai_budget_exhausted` (2026-10-06), and
  `/coach/ask` skips the phrasing step while still shipping the arithmetic (2026-10-11), because
  the recommendation there is computed from stored data and the model only words it. Provider-side
  spend controls are not in this repository, so a door that omits the check is not stopped by it.
* **The i18n §81 work is another agent's lane.** Several web files were modified by the concurrent
  run during this milestone and are not part of it.
