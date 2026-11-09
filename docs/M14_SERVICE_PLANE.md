# M14 — the service plane: registry, config, edge (ROADMAP Phase 11, items 47–50)

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
[INFO] FOOTBALL OS edge ............. SUCCESS   (4 tests, 0 failures)
```

Four edge tests, each a different claim:

- `EdgeRoutingTest.a_routed_request_reaches_the_core_with_its_path_and_mints_a_trace_id` — a real
  HTTP server (JDK `HttpServer`) stands in for the core; the stub records the path and the trace header
  it received, so the test compares both ends of the hop rather than the gateway's account of itself.
- `...a_trace_id_the_caller_supplied_is_the_one_both_ends_see` — idempotence.
- `...the_route_table_is_what_the_gateway_resolved` — `/edge/routes` reads `RouteDefinitionLocator`, and
  asserts the resolved target starts with the stub's real address.
- `EdgeFallbackTest.a_dead_core_answers_the_products_refusal_shape_with_the_trace_id` — route pointed at
  `127.0.0.1:1` (connection refused, the same failure a crashed core produces), 503 + body.

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

Start order is the dependency order in the file: registry and config first, edge last. The edge reaches
the host's core through `host.docker.internal` by default (`APC_CORE_URI` overrides it).

## 6. Scope, stated

- **The Python core stays canonical.** No football rule, figure or sentence is computed in Java. The
  gateway routes, traces and protects; the registry says where; the config server says with what.
- **The gateway does not yet load-balance.** It routes to one core address. `lb://` and a registered
  `FOOTBALL-CORE` instance are a later item; the registry already accepts the registration.
- **The fallback is the edge's sentence, not the core's.** It says so in its own message.
- **Only the routed prefix is published.** `/edge/routes` and `/edge/fallback` are the edge's own two
  doors and answer nothing else.
