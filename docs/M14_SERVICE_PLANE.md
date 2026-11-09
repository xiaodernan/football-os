# M14 — the service plane: registry, config, edge (ROADMAP Phase 11, items 47–51)

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

## 2. The build, as run

```
services> mvn -o -B package
[INFO] FOOTBALL OS registry ......... SUCCESS
[INFO] FOOTBALL OS config server .... SUCCESS
[INFO] FOOTBALL OS edge ............. SUCCESS   (6 tests, 0 failures)
```

Six edge tests, each a different claim:

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
refusal shape. The core was then restarted and the very first retry answered `200` — the breaker's
half-open trial succeeded and closed it without a restart of the edge.

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
