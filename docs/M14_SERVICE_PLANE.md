# M14 — the service plane: registry, config, edge (ROADMAP Phase 11, items 47–56)

Date: 2026-11-09. The product was one deployable: a FastAPI core behind a Next.js front end. This unit
gives it the shape a platform has in production — a service registry, a config server and an edge
gateway — without moving one football rule out of the core. Every claim below was read back from a
running process, not from the file that configured it.

## 1. What was built

`services/` is a Maven reactor (Spring Boot 3.5.16, Spring Cloud 2025.0.3, Java 21) with three modules:

| module | port | what it is | what it is not |
| --- | --- | --- | --- |
| `registry` | 8761 | a Eureka server: the one table that says where a service is | it answers no question about football |
| `config` | 8888 | a Spring Cloud Config server, `native` profile over `classpath:/config-repo` | configuration is not scattered across env vars; it is a file in the diff |
| `edge` | 8080 (18080 on this host) | a Spring Cloud Gateway: routes `/api/v1/**` to the core, mints/propagates `X-Trace-Id`, wraps the route in a Resilience4j circuit breaker whose fallback answers the product's refusal shape | it computes no figure, judges no request and changes no body |

The reactor builds offline: `mvn -o -B package` resolves from the local Maven repository, so the gate
has no network behind it.

Two copies of the edge's settings exist — its own `application.yml`, which must work when no config
server is up, and `config-repo/football-edge.yml`, which the config server serves when one is. They are
held equal by `apps/api/tests/test_edge_config_parity.py`: the case reads both files as data and compares
the route table (id, order, uri, predicates, filters), the whole `resilience4j` breaker block and the
whole rate-limit block, and asserts `core-api` sorts before the catch-all. A drift would be a gateway
whose behaviour depends on whether another container happens to be running.

## 2. The build, as run

```
services> mvn -o -B package
[INFO] FOOTBALL OS registry ......... SUCCESS
[INFO] FOOTBALL OS config server .... SUCCESS
[INFO] FOOTBALL OS edge ............. SUCCESS   (17 tests, 0 failures)
```

Seventeen edge tests, each a different claim:

- `EdgeRoutingTest.a_routed_request_reaches_the_core_with_its_path_and_mints_a_trace_id` — a real
  HTTP server (JDK `HttpServer`) stands in for the core; the stub records the path and the trace header
  it received, so the test compares both ends of the hop rather than the gateway's account of itself.
- `...a_trace_id_the_caller_supplied_is_the_one_both_ends_see` — idempotence.
- `...the_route_table_is_what_the_gateway_resolved` — `/edge/routes` reads `RouteDefinitionLocator`, and
  asserts the resolved target starts with the stub's real address.
- `EdgeFallbackTest.a_dead_core_answers_the_products_refusal_shape_with_the_trace_id` — route pointed at
  `127.0.0.1:1` (connection refused, the same failure a crashed core produces), 503 + body.
- `EdgeLoadBalancedRoutingTest.the_core_is_reached_by_service_name` — no `apc.core-uri` is set; the stub
  core is published only through `spring.cloud.discovery.client.simple.instances.football-core[0]`, so a
  200 proves `lb://football-core` resolved through a discovery client and arrived at that instance.
- `...the_route_table_names_the_service_not_an_address` — the resolved route is `lb://football-core`,
  not a fixed host: a configuration that silently kept the old URI would fail this case while still
  answering 200.
- `EdgeRateLimitTest.the_burst_is_served_then_the_next_request_is_refused_and_the_bucket_refills` — burst 2
  at 20/s: two 200s, a 429 in the product's shape with `Retry-After`, the stub core's call count still 2
  (the refusal was not forwarded), and a 200 again after 300 ms.
- `...the_policy_is_read_from_the_running_filter` — `/edge/limits` returns the values the filter holds.
- `EdgeRateLimitDisabledTest.a_disabled_limit_refuses_nothing_and_says_so` — with `enabled=false`, four
  requests all pass and `/edge/limits` says the limit is off.
- `EdgeBreakerStateTest.the_door_reports_a_breaker_that_has_not_been_used_yet` — before any routed call
  `/edge/breaker` answers `present=false` and `state=NOT_CREATED` rather than inventing a CLOSED breaker.
- `...a_failed_call_is_visible_with_the_thresholds_in_force` — one failed call, then the door reads
  `CLOSED`, one buffered call, one failure, `failureRate=-1`, and the thresholds actually applied
  (window 10, threshold 50, minimum 5, half-open permits 3): a config block that is present but not
  applied fails this comparison.
- `...enough_failures_open_the_breaker_and_a_further_call_is_not_permitted` — five failed calls read
  `OPEN`, buffered 5, failed 5, `failureRate=100`; the sixth answers 503 without reaching the stub and
  `notPermittedCalls=1`.
- `EdgeWebPassthroughTest.the_shell_is_served_through_the_same_door_and_its_paths_survive` — two stubs,
  one for the core and one for the shell: `/` and `/_next/static/chunks/app.js` answer from the shell
  stub, the path is unchanged, and the core stub is not called.
- `...the_api_door_still_belongs_to_the_core` — `/api/v1/health` answers from the core stub and the
  shell stub's counter stays zero, so the catch-all did not swallow the API prefix.
- `...the_route_table_publishes_both_doors` — the resolved table names `core-api` and `web`, each with
  the URI its stub was given and the web route carrying the catch-all predicate.
- `EdgeInstancesTest.the_door_reports_the_instance_the_balancer_would_use` — an instance published
  through the same simple discovery client the `lb://` route resolves through is read back with its
  host, port and URI: the test sees the gateway's view, not a field the controller kept for itself.
- `...an_unregistered_service_reads_as_zero_rather_than_an_error` — an unknown name answers 200 with
  `count=0`, because "nobody is registered" is an answer an operator needs.

One trap recorded: the first `/edge/routes` implementation called `.block()` in the controller. On a
gateway handler that runs on the netty event loop, `block()` is an `IllegalStateException`, and the door
answered 500. The controller now returns `Flux<ResolvedRoute>` — a stream, never blocked.

## 3. The live walk (sixteen checks, `.scratch/walk-plane.ps1` → `.scratch/plane-walk.json`)

Topology on this host: core `uvicorn app.main:app` on `127.0.0.1:8100` (SQLite
`.scratch/plane/core.db`, migrated to head), registry on 8761, config on 8888, edge on 18080.
Ports 8000 and 8080 were already bound by unrelated processes on this machine, which is why the walk
uses 8100/18080; `EDGE_PORT` and `--apc.core-uri` are the two knobs.

| check | value read |
| --- | --- |
| health through the edge | `200`, body is the core's own `{"status":"ok",...}` |
| trace minted | `e2d93527-6c6a-4c5d-9259-1fccf9fcf879` — a UUID for a caller that sent none |
| trace supplied | `walk-plane-0001` came back as `walk-plane-0001` |
| gateway is transparent | `/api/v1/world/competitions` byte-identical direct vs routed, same length, rows present |
| route table | one route, id `core-api`, uri `http://127.0.0.1:8100`, predicate `/api/v1/**`, filter `CircuitBreaker` |
| registry | `FOOTBALL-EDGE` present, instance status `UP` on port 18080 |
| config server | `/football-edge/default` serves `...routes[0].id = core-api` and `...filters[0].args.fallbackUri = forward:/edge/fallback` from `classpath:/config-repo/football-edge.yml` |

`PLANE WALK OK 16/16`, exit 0.

## 4. The breaker, live: down and back

With the core stopped, a request through the edge answered

```
HTTP/1.1 503 Service Unavailable
X-Trace-Id: fallback-live-2

{"trace_id":"fallback-live-2","at":"2026-11-09T11:52:03.310Z",
 "message":"the canonical core did not answer; this is the edge speaking, not the product",
 "code":"core_unavailable","retryable":true}
```

The header and the body carry the same id: the fallback is not a generic 503 page, it is the product's
refusal shape. The core was then restarted and the very first retry answered `200`, without a restart
of the edge.

That recovery was **not** the breaker closing: at that point the breaker could never open, because
`minimum-number-of-calls` was still Resilience4j's stock 100 inside a 10-call window (found and fixed in
§9, item 53). The 503 was the CircuitBreaker filter's fallback answering a failed call — which it does
in any state — so the walk proved the fallback and not the trip. Item 53 makes the breaker able to open
and adds the door that shows it.

## 5. Compose (item 50)

`infra/docker-compose.yml` gains `registry`, `config` and `edge` under the `plane` profile, each running
the jar `mvn -o package` produced, so no container resolves a dependency at boot:

```
docker compose -f infra/docker-compose.yml --profile plane up -d registry config edge
```

Start order is the dependency order in the file: registry and config first, edge last. The compose edge
still sets `APC_CORE_URI` (a host address) because the core in development runs outside the network; with
that variable unset the route uses the registry instead.

## 6. Scope, stated

- **The Python core stays canonical.** No football rule, figure or sentence is computed in Java. The
  gateway routes, traces and protects; the registry says where; the config server says with what.
- **The fallback is the edge's sentence, not the core's.** It says so in its own message.
- **Only the routed prefix is published.** `/edge/routes` and `/edge/fallback` are the edge's own two
  doors and answer nothing else.

## 7. The core registers itself, and the edge finds it by name (item 51)

The registry from items 47–50 had nobody in it but the edge. Item 51 closes that: the Python core
announces itself when a registry is configured, renews its lease, and withdraws on shutdown; the edge
routes to `lb://football-core` by default and resolves that name through the same registry.

### 7.1 The core's side

`apps/api/app/core/discovery.py`, wired into the FastAPI lifespan. Configuration is four variables, and
every one of them has a working default:

| variable | default | meaning |
| --- | --- | --- |
| `EUREKA_URL` | empty | the registry's base URL; **empty means the integration is off entirely** — no connection, no task, no log line |
| `SERVICE_NAME` | `FOOTBALL-CORE` | the application name; the VIP the edge asks for is its lower case |
| `SERVICE_HOST` | this host's name | what the registry publishes; the edge resolves the IP from it |
| `SERVICE_PORT` | `8000` | the port this process actually serves on (`--port` and this variable change together) |

With `EUREKA_URL` set, startup is one `POST /eureka/apps/FOOTBALL-CORE` with the standard instance
document (`status: UP`, `vipAddress: football-core`, port enabled, `leaseInfo` 10/30, health URLs at
`/api/v1/healthz`), followed by a `PUT .../{instanceId}` every 10 seconds and a `DELETE` on shutdown. A
404 on renewal re-registers instead of waiting for a lease that no longer exists. Every call is
best-effort: a registry that is down is a degraded platform, not a core that refuses to boot.

`tests/test_discovery.py` drives all of it against a real `ThreadingHTTPServer` standing in for Eureka
(6 cases): no URL means no traffic; a malformed URL is reported rather than raised; the registration
document is the shape the registry reads; the flow is POST → PUT… → DELETE with the encoded instance id;
a 404 lease produces a second registration; a registry that is down never propagates. `ruff` and `mypy`
clean on the changed files.

### 7.2 The edge's side

The route default is now

```
uri: ${apc.core-uri:lb://football-core}
```

so a deployment with a registry needs no address at all, and a single-process dev run sets `APC_CORE_URI`
to keep the direct route. `spring-cloud-starter-loadbalancer` was added — the gateway starter does not
bring the reactive load balancer, and without it `lb://` resolves to nothing.

### 7.3 The live walk

Topology: registry 8761 (left running from §3), core `uvicorn` on 8100 with `EUREKA_URL` and
`SERVICE_PORT=8100`, edge on 18080 with **no** `apc.core-uri`.

Read back from the running processes:

```
GET /eureka/apps/FOOTBALL-CORE
{"name":"FOOTBALL-CORE","instance":[{"instanceId":"localhost:football-core:8100",
 "hostName":"localhost","ipAddr":"127.0.0.1","status":"UP","port":{"$":8100,"@enabled":"true"},
 "vipAddress":"football-core","leaseInfo":{"renewalIntervalInSecs":10,"durationInSecs":30}}]}

GET /edge/routes
[{"id":"core-api","uri":"lb://football-core","predicates":["Path={_genkey_0=/api/v1/**}"],
  "filters":["CircuitBreaker={name=coreBreaker, fallbackUri=forward:/edge/fallback}"]}]

GET /api/v1/healthz (through the edge)
200 {"status":"ok","environment":"development",...}
```

The core was then killed and the next request through the edge answered

```
HTTP/1.1 503 Service Unavailable
X-Trace-Id: walk-down-1
{"trace_id":"walk-down-1","code":"core_unavailable","retryable":true,
 "message":"the canonical core did not answer; this is the edge speaking, not the product"}
```

The core was restarted with the same variables; a retry through the edge then answered `200` again, and
the registry listed the instance `UP`, registered afresh (`registrationTimestamp` advanced).

**Lease evidence, and one trap.** `lastRenewalTimestamp` in the registry's JSON stayed at the registration
time even though the heartbeats were arriving and answering `200` every 10 seconds. That field is written
by the *client* at registration and is not maintained by this server — reading it would wrongly suggest
the lease was dead. The honest test is survival past the lease: 86.7 seconds after registration (lease 30
seconds, eviction sweep 5 seconds) the instance was still `UP`, which is only possible if the `PUT`s are
renewing it. The core's log carries each `PUT ... HTTP/1.1 200` on the `eureka-lease-renewal` task.

### 7.4 What this changes for the product

Nothing a club reads. The core still computes every figure; the registry now says where the core is, and
the edge asks. `APC_CORE_URI` remains a supported way to run without a registry, and leaving `EUREKA_URL`
unset keeps every developer process exactly as it was before this item.

## 8. A ceiling on how fast one caller may ask (item 52)

The fallback and the breaker protect the core when it is *down*. This protects it when it is asked too
much. `RateLimitFilter` is a global gateway filter holding one token bucket per caller address: `burst`
requests may arrive back to back, and the bucket refills at `requests-per-second`. Refill is computed from
elapsed time on each request, so there is no timer thread and no scheduled work — a quiet gateway does
nothing.

Defaults are deliberately generous — a browser page makes dozens of calls and must never notice:

| variable | default | meaning |
| --- | --- | --- |
| `RATE_LIMIT_ENABLED` | `true` | the opt-out |
| `RATE_LIMIT_BURST` | `100` | back-to-back allowance per caller |
| `RATE_LIMIT_RPS` | `50` | refill rate |

Every routed response, accepted or refused, carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`; a
refusal is `429` with `Retry-After` and the product's refusal shape, so a client can back off:

```
{"code":"rate_limited","message":"this caller is asking faster than the edge accepts; the request was
 not forwarded","trace_id":"walk-rl-4","at":"2026-11-09T14:00:29.024611600Z","retry_after_seconds":1,
 "retryable":true}
```

`GET /edge/limits` reports the policy in force and how many callers are being counted, read from the
enforcing filter rather than from configuration:

```
{"enabled":true,"requestsPerSecond":1.0,"burst":3,"trackedClients":1}
```

Identity is the direct peer address, and the door is honest about the consequence: behind a proxy every
caller shares the proxy's address and the bucket becomes a global ceiling. Trusting `X-Forwarded-For`
would let any caller mint a new identity per request and make the limit meaningless. The map is bounded
at 4096 entries with access-order eviction, so memory has a ceiling even under a scan.

### 8.1 The live walk

Core on 8100, edge on 18080 with `RATE_LIMIT_BURST=3` and `RATE_LIMIT_RPS=1`:

```
req1 200 limit=3 remaining=2
req2 200 limit=3 remaining=1
req3 200 limit=3 remaining=0
req4 429 Retry-After: 1 X-RateLimit-Remaining: 0     (body above, trace_id walk-rl-4)
after ~1 s: 200 remaining=2                          (the bucket refilled)
GET /edge/limits → {"enabled":true,"requestsPerSecond":1.0,"burst":3,"trackedClients":1}
```

The first live attempt used a stale jar and `/edge/limits` answered 404 — the filter was compiled by
`mvn test` but the jar predated it. Rebuilding the jar and restarting produced the sequence above; worth
recording because a walk that does not rebuild can "prove" a missing feature.

### 8.2 What this changes for the product

No football answer changes. A caller that behaves like a browser sees two extra response headers; a loop
that asks faster than a human ever could is refused by the edge before the core is touched, and is told
how long to wait.

## 9. The breaker can be asked what it thinks (item 53)

The route has been wrapped in a breaker since item 48, but until this item the only way to know what the
breaker thought was to make a request and infer from the 503. `GET /edge/breaker` now reads the state out
of the `CircuitBreakerRegistry` that the route's filter writes to: state, the sliding window's counters,
and the thresholds actually in force. Before the first routed call it answers `present=false` /
`state=NOT_CREATED`, because Resilience4j creates a breaker lazily and reporting `CLOSED` for one that
does not exist would be an invented fact.

**The door is what found the defect.** The configuration set `sliding-window-size: 10` but left
`minimum-number-of-calls` at Resilience4j's stock 100 — a minimum larger than the window can never be
reached, so `failureRate` stayed `-1` and the breaker could never open. The fallback still answered every
failed call, because the CircuitBreaker filter's fallback runs on a failed call whichever state the
breaker is in, which is why the earlier walk's 503 looked like a working breaker. It was a working
fallback and a decorative breaker. Both `application.yml` and the config server's
`config-repo/football-edge.yml` now set `minimum-number-of-calls: 5`.

### 9.1 The test

`EdgeBreakerStateTest` points the route at a refused port so every routed call fails, and reads the door
three times in one breaker's life, in declared order:

| read | what it proves |
| --- | --- |
| before traffic | `present=false`, `state=NOT_CREATED` — the door does not invent a CLOSED breaker |
| after one failure | `present=true`, `CLOSED`, `bufferedCalls=1`, `failedCalls=1`, `failureRate=-1` (the window minimum is not reached), and the applied thresholds read back as 10 / 50 / 5 / 3 — a config block that is present but not applied fails here |
| after five failures | `OPEN`, `bufferedCalls=5`, `failedCalls=5`, `failureRate=100`; a further call answers 503 without reaching the stub and `notPermittedCalls=1` |

The third read is the one the old configuration could never produce: with minimum 100 it would still read
`CLOSED` after five failures.

### 9.2 The live walk

Edge on 18080, core on 8100 stopped, registry on 8761:

```
cold   GET /edge/breaker → {"present":false,"state":"NOT_CREATED",...,"failureRate":-1.0}
5 calls                  → 503, 503, 503, 503, 503
       GET /edge/breaker → {"present":true,"state":"OPEN","slidingWindowSize":10,
                            "failureRateThreshold":50.0,"minimumNumberOfCalls":5,
                            "permittedCallsInHalfOpenState":3,"bufferedCalls":5,
                            "failedCalls":5,"successfulCalls":0,"notPermittedCalls":0,
                            "failureRate":100.0}
```

After the 5-second wait a trial call was permitted (`HALF_OPEN`); it failed, and the door then read
`state=HALF_OPEN, bufferedCalls=1, failedCalls=1, failureRate=-1` — the trial opens a **new** window, it
does not reset the five that opened the breaker. Four further calls in one burst permitted the remaining
two trials (three in total, all failed) and refused the last two; the door read
`state=OPEN, bufferedCalls=3, failedCalls=3, notPermittedCalls=2, failureRate=100.0`.

`notPermittedCalls` is the counter that answers the operator's question — *is the core down, or is the
breaker still holding the door shut?* A 503 with that counter rising means the core was never asked.

### 9.3 What this changes for the product

No football answer changes. An operator gains a door that distinguishes a dead core from an open breaker,
and the settings that made the breaker unable to open are gone: since item 53 the protection can actually
trip, and the state it trips into is readable rather than inferred.

## 10. One door for the whole product (item 54)

Until this item the edge published only `/api/v1/**`; a browser still needed the web process's own port,
so "the gateway" was really the API's gateway. The gateway now owns one door: `core-api` is matched at
order 0, and a catch-all `web` route at order 10 forwards everything else to
`${apc.web-uri:http://localhost:3000}`. The edge's own `/edge/**` doors are Spring request mappings,
which are matched before any route, so they keep answering under a catch-all — a property the live walk
below checks rather than assumes.

`EdgeWebPassthroughTest` gives the gateway two stubs and reads which one each request arrived at:

| request | what the test proves |
| --- | --- |
| `/` and `/_next/static/chunks/app.js` | the shell stub answers both, the path is unchanged and the core stub is never called |
| `/api/v1/health` | the core stub answers and the shell stub's counter stays zero — a catch-all did not swallow the API prefix |
| `/edge/routes` | the resolved table names both doors, each with the URI its stub was given |

Live walk — edge on 18080, a marker shell stub on 3210, core stopped:

```
GET /                            → 200 {"web": true, "path": "/"}
GET /_next/static/chunks/app.js  → 200 {"web": true, "path": "/_next/static/chunks/app.js"}
GET /api/v1/health               → 503 {"code":"core_unavailable","trace_id":"ab482864-…",…}
GET /edge/routes                 → [{"id":"core-api","uri":"lb://football-core",…},
                                    {"id":"web","uri":"http://127.0.0.1:3210","predicates":["Path=/**"]}]
```

The two global filters apply to the shell as well: the `/` response carried `X-Trace-Id:
be53e974-d0b7-4005-a7ae-b2a16f8502dd` and `X-RateLimit-Limit: 100` / `X-RateLimit-Remaining: 99`, so a
page request is traced and bounded by the same policy as an API request.

**Scope, stated.** The web route has no circuit breaker. The shell is a static asset process; a fallback
page for it would be the edge inventing product UI, which is the line this plane does not cross. The API
route keeps its breaker because that is the door whose failure the product has a sentence for.

## 11. Who would the balancer ask? (item 56)

`GET /edge/instances?service=football-core` reads the `DiscoveryClient` the `lb://football-core` route
resolves through and returns the instance list: instance id, host, port, URI, secure flag. The default
name is `football-core`. An unknown name answers 200 with `count=0` — "nobody registered it" is an answer
an operator deciding between a missing registration and a dead instance needs, not a 404.

Two cases bind the door: one publishes an instance through the same simple discovery client the route
uses and reads back host / port / URI; the other asserts that an unknown name is a zero row.

The live walk, edge on 18080 and registry on 8761:

```
GET /edge/instances?service=football-edge
  {"count":1,"service":"football-edge","instances":[{"instanceId":"host.docker.internal:football-edge:18080",
   "host":"192.168.1.5","port":18080,"uri":"http://192.168.1.5:18080","secure":false}]}
GET /edge/instances?service=nobody
  {"count":0,"service":"nobody","instances":[]}
GET /edge/instances?service=football-core          (after the core registered itself)
  {"count":1,"service":"football-core","instances":[{"instanceId":"127.0.0.1:football-core:8100",
   "host":"127.0.0.1","port":8100,"uri":"http://127.0.0.1:8100","secure":false}]}
```

**The walk found a topology trap.** The first registration used the default `SERVICE_HOST`, the machine's
hostname (`xiaodernan`). The registry read `UP` and this door showed the instance, but every routed call
still answered the fallback `core_unavailable`: on this host the name resolves to IPv6 link-local
addresses (`fe80::…`), while the core listened on IPv4 loopback — the balancer dialled an address nobody
served. It also measured the door's freshness relative to the route: the door reads the registry on every
call, while the route resolves through a 30-second load-balancer cache, so the door can name an instance
seconds before the route uses it. Pinning `SERVICE_HOST=127.0.0.1` for a colocated walk (item 51's walk
did the same with `localhost`) produced `127.0.0.1:football-core:8100`; `/api/v1/world/competitions`
through the edge then returned the direct read's 5984 bytes unchanged, and the breaker door read
`CLOSED, buffered 4, failed 2` — under the minimum of 5 that item 53 set, so the count was visible
without a trip.

The rule this leaves: `SERVICE_HOST` must name an address the service really listens on for the clients
that will dial it. The hostname is right in a container, where it is the pod's network identity; on a
developer host where the name resolves to a link-local address, pin it.

## 12. One trace across both planes (item 58)

Items 48–56 made the edge a real gateway: it routes by name, traces its own requests with `X-Trace-Id`,
limits a caller, opens a breaker and serves the web shell through the same door. But the core does not
speak `X-Trace-Id` as a parent. Since M12 the Python side accepts a **W3C `traceparent`** from an upstream
caller (`qa-proxy-gate` carries a valid one, drops an invalid one and mints no ids of its own). A request
crossing the Java gateway therefore carried an id only the Java side understood: the edge's correlation
field and the core's trace were two different traces with nothing in common.

`W3cTraceContextFilter` is a `GlobalFilter` at `HIGHEST_PRECEDENCE + 1` — after `TraceIdFilter` (which
mints `X-Trace-Id`) and before `RateLimitFilter` (`+10`). Three rules, each stated in the code rather than
assumed:

- a **valid** caller `traceparent` (strict version-00 shape, non-zero trace and span ids) passes through
  byte-for-byte, with its `tracestate`; the caller's trace stays the caller's, and the edge does not
  re-parent it;
- an **absent or invalid** one is replaced by a freshly minted valid parent, and a `tracestate` that
  described the discarded parent is dropped;
- the minted trace-id is derived from the **same** `X-Trace-Id` the edge already minted — a UUID is already
  32 hex digits, and any other caller id is hashed into one — so both headers name one trace. Flags are
  `-00`: the gateway does not assert sampling on a caller's behalf. The parent is also echoed on the
  response, so a caller can read the id the core was given instead of guessing it.

### 12.1 The tests

`W3cTraceContextFilterTest` (6 cases, no Spring context) holds the pure rules: valid shape, degenerate and
malformed shapes (all-zero ids, uppercase, missing flags), minted format and `-00` flags, UUID alignment,
stable derivation from one correlation id, and the filter's order relative to the other two.
`EdgeTraceContextTest` (3 cases) stands a real JDK HTTP server in for the core and reads the headers the
core actually received: absent → minted and echoed; valid parent + state → byte-for-byte preserved;
invalid parent + state → replaced and the stale state dropped.

`mvn -o -B package` over the whole reactor: **26 tests / 0 failures / 0 errors**, all four modules
SUCCESS. The Python-side gates `test_edge_config_parity.py`, `test_spec_audit_currency.py` and
`test_openapi_contract_currency.py` stayed green (16 cases) — this filter is code, not a second copy of
the YAML settings, so the parity gate has nothing new to compare.

### 12.2 The live walk

`.scratch/walk-w3c.py` boots the built `edge-0.1.0.jar` on `18880` with a stand-in core on `18881`
(Eureka and Config disabled, rate limit off), waits for `/actuator/health`, and reads both ends of three
routed calls. **12/12 checks, 0 red**:

```
absent   -> core got 00-06adb1ff52924759986d9effa8dcbc68-d2ca5412ef005244-00
            echoed to the caller; trace-id == X-Trace-Id (06adb1ff…); flags -00
valid    -> core got 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
            with tracestate vendor=value, unchanged in both directions
invalid  -> "garbage" became 00-df7515eeaa514f46b193528b491d72bc-268fafa1b7da78b6-00
            tracestate dropped at the core; replacement echoed to the caller
```

### 12.3 What this does not claim

- It is **not** a Micrometer/OTel tracer. The edge emits no spans of its own; it only puts a valid parent
  on the wire so the core's existing tracing can parent its spans to the caller's trace. A real collector
  backend is still the local debug container item 50 named.
- It does **not** change `sampled`. A caller's flags are preserved; a minted parent says `-00`.
- It does **not** replace `X-Trace-Id`. That header remains the plane's correlation field, and the core's
  request-id logging still works as before.
- It does **not** validate `tracestate` beyond the W3C rule that it describes the current parent; a
  syntactically odd but well-formed `tracestate` is carried through when its parent is valid.

## 13. A changed setting lands without a restart (item 59)

Item 47 stood up a Spring Cloud Config server serving the edge's settings as reviewable files, but the
gateway read them **once at boot**: changing a value meant restarting the one door every caller uses.
That is a config server with half its point missing. Item 59 closes it with three pieces:

- `PlaneSettings` is a `@RefreshScope` bean holding `edge.plane.notice` (`PLANE_NOTICE` in the
  environment, default `one door, one trace`). Spring Cloud Context rebuilds it after a refresh.
- `GET /edge/config` reads the **live bean**, not the file, and names its own refresh door and formula.
  An operator can ask what the running gateway believes before and after a change.
- Both copies of the settings — the edge's own `application.yml` and the config server's
  `config-repo/football-edge.yml` — carry the same `edge.plane` block and the same actuator exposure
  (`health,info,gateway,refresh`). The parity gate gained a fourth case comparing them, because a value
  that refreshes in one gateway and not the other is two gateways again.

### 13.1 The tests

`EdgeConfigRefreshTest` (3 cases) asks the running process: `PlaneSettings` really carries
`@RefreshScope` and the door reads the boot value; `POST /actuator/refresh` is exposed and answers 200;
and changing a property source then rebuilding the scope makes the door answer the new value — twice.
`test_edge_config_parity.py` holds the two YAML copies one answer (now 4 cases).

`mvn -o -B package` over the whole reactor: **29 tests / 0 failures / 0 errors**, all four modules
SUCCESS. The Python gates `test_spec_audit_currency`, `test_security_probe_report_currency`,
`test_openapi_contract_currency` and the parity gate stayed green (28 cases together).

### 13.2 The live walk

`.scratch/walk-refresh.py` boots the **config server** on `18888` with its native search location pointed
at a scratch file, and the built edge jar on `18882` with `spring.config.import` aimed at it (Eureka and
the rate limiter off, a stand-in core on `18883`). It reads both ends, changes the file and refreshes.
**9/9 checks, 0 red**:

```
config server /football-edge/default      -> v1-before-refresh
GET /edge/config at boot                  -> v1-before-refresh
routed /api/v1/health                     -> traceparent 00-5da0beaa…-95fbc769…-00   (item 58 intact)
write v2-after-refresh
POST /actuator/refresh                    -> 200
GET /edge/config                          -> v2-after-refresh   (no restart)
write v3-third-value
POST /actuator/refresh
GET /edge/config                          -> v3-third-value     (a second refresh lands too)
```

The walk's first attempt returned **415 Unsupported Media Type**: Spring Boot's actuator POST wants a
JSON content type, and the walk sent an empty form body. That was the harness, not the service — sending
`{}` as `application/json` answered 200. The check stays in the script so the next runner sees why.

### 13.3 What this does not claim

- It does **not** refresh every setting. Only beans in `@RefreshScope` are rebuilt; the route table,
  breaker thresholds and rate-limit policy are read at boot by their own components and still need a
  restart. The one refreshed setting is deliberately a plane-level notice, not a football rule.
- It is **not** Spring Cloud Bus. A refresh must be posted to each gateway instance; broadcast to a
  fleet is a separate decision needing a broker.
- It does **not** compute anything about a club, player or season. The Python core stays canonical.

## 14. A transient failure heals at the door (item 60)

The breaker (item 53) stops asking a core that is down. It does not help a core that stumbles once: a
single 503 from a restarting instance went straight to the caller, and the fallback answered a failure
that a second attempt would have cleared. `Retry` is now the inner route filter on `core-api`, with
`CircuitBreaker` still the outer one:

```
filters: [CircuitBreaker, Retry]
```

That order is a decision, not a default. Gateway route filters are applied in declaration order, so the
breaker wraps the retry: **one caller request is one breaker observation**, however many attempts went
downstream. Had Retry been outer, three attempts would have looked like three failures to the breaker,
and a transient stumble could open a breaker sized for five calls in ten. `EdgeBreakerStateTest` still
sees `bufferedCalls == 1` after one failed call.

The policy is deliberately narrow — `retries: 2`, `series: []`, `statuses: [SERVICE_UNAVAILABLE,
BAD_GATEWAY]`, `methods: [GET]`, bounded exponential backoff (20ms → 80ms). **The `series: []` is the
part that was found by measurement**, not by reading the docs: Spring Cloud Gateway's stock default is
the whole `SERVER_ERROR` series, and the first configuration used a comma-separated `statuses` string
that did not bind. The result was that a **500 — a real application error — was replayed three times**.
Clearing the series and writing both lists as YAML lists makes 500 a single attempt. A non-idempotent
POST is never replayed.

`test_edge_config_parity.py` now has a fifth case that binds both copies of the route to this exact
order and policy, so a future edit cannot quietly widen what gets replayed.

### 14.1 The tests and the live walk

`EdgeRetryTest` (4 cases) stands a stub core that counts the attempts it actually received: two transient
503s heal into a 200 on the third attempt; a 500 is attempted once; a POST 503 is attempted once; a
permanent 503 is attempted three times and the last 503 reaches the caller.

`mvn -o -B package` over the whole reactor: **37 tests / 0 failures / 0 errors**, all four modules
SUCCESS. `.scratch/walk-retry.py` boots the built jar on `18890` with a controllable stub on `18891`:
**12/12 checks, 0 red** — including `/edge/routes` really resolving a `Retry` filter, the three attempts,
the single 500 and POST attempts, and item 58's W3C parent surviving every retry.

### 14.2 What this does not claim

- It does **not** retry connection failures differently from status failures: Gateway's default exception
  set still applies, which is why a dead core reaches the 503 fallback as before (`EdgeFallbackTest`).
- It does **not** make the fallback answer an exhausted HTTP 503. A 503 response is a response, so the
  caller sees it; the fallback is for an exception or an open breaker. The test says so.
- It does **not** retry anything on the web-shell route, and it computes no football figure.

## 15. One door for the whole plane (item 61)

Phase 11 grew a door per concern — `/edge/routes` (48), `/edge/limits` (52), `/edge/breaker` (53),
`/edge/instances` (56), `/edge/config` (59) — plus two global filters for tracing. An operator wanting
the shape of the platform had to know all five and stitch them together by hand.

`GET /edge/plane` does the stitching by **calling the very same controller methods** those doors call,
not by reimplementing their predicates. It publishes `routes`, `limits`, `breaker`, `instances` (for
`football-core`) and `config` as they are, plus a `trace` block naming the three real headers, a `doors`
map of the six entry points including `/actuator/refresh`, and a `formula` stating that the plane adds no
figure of its own. Every block is read live on each request; nothing is cached.

### 15.1 The tests and the live walk

`EdgePlaneTest` (4 cases) reads `/edge/plane` and each of the five doors over HTTP and compares parsed
JSON: every block is byte-for-byte the answer its own door gives. It also walks the `doors` map and
requires each named door to answer (POST for refresh), checks the trace block names the constants the
filters actually use, and pins the top-level key set to eight so no unpublished figure can appear.

`.scratch/walk-plane.py` boots the built jar on `18894` with a stub core on `18895`: **16/16 checks,
0 red** — `/edge/plane` is 200 with exactly eight blocks, all five blocks equal their own doors, all six
named doors answer 200, and the trace block names the real headers.

### 15.2 What this does not claim

- It is **not** a health check. It describes configuration and state; it does not decide that the plane
  is "up". `/actuator/health` remains that door.
- It does **not** aggregate across gateway replicas. One instance answers about itself, like every other
  `/edge/**` door; a fleet-wide view needs a caller that asks each instance.
- It does **not** compute a football fact. The Python core stays canonical: this door describes the
  shape of the way in, not the game behind it.
