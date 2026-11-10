# Runbook — the Spring Cloud service plane

**When:** starting or debugging the optional service plane (Phase 11, `docs/M14_SERVICE_PLANE.md`). The
plane is additive: the FastAPI core and the Next.js shell still work without it. No football rule lives
in Java — the plane routes, resolves, configures, traces and protects, and answers no question the core
could answer.

## 1. Build and boot order

Versions are pinned to the local Maven repository so the build needs no network:

```bash
cd services && mvn -o -B package       # 37 tests, four modules, BUILD SUCCESS
```

The compose profile `plane` starts the jars that build produced (`infra/docker-compose.yml`). Start in
this order, because each step reads the one before it:

| step | module | port | why it is first |
| --- | --- | --- | --- |
| 1 | `registry` | 8761 | Eureka; the core registers here and the edge resolves `lb://football-core` here |
| 2 | `config` | 8888 | Config server, `native` profile over `classpath:/config-repo/` |
| 3 | the Python core | 8100 | sets `EUREKA_URL` to register, `SERVICE_HOST=127.0.0.1` on a developer host |
| 4 | `edge` | 8080 | imports the config server, resolves the core by name, serves `/api/v1/**` and the shell |

The core and the edge both degrade honestly when the plane is absent: an empty `EUREKA_URL` registers
nothing, and `optional:configserver:` is optional. `apc.core-uri` / `APC_CORE_URI` switches the edge to
a fixed address with no registry at all.

## 2. The doors, and what each one answers

```
GET  /edge/plane      the whole shape: routes, limits, breaker, instances, config, trace, doors, formula
GET  /edge/routes     the resolved route table, read from RouteDefinitionLocator (not the YAML)
GET  /edge/limits     the token-bucket policy in force and the number of tracked callers
GET  /edge/breaker    coreBreaker's state, window counters, thresholds; present=false before first call
GET  /edge/instances  ?service=football-core — what the balancer would dial; unknown name is count=0
GET  /edge/config     the live @RefreshScope value, not the file's
POST /actuator/refresh  rebuild @RefreshScope beans from the current config (JSON content type!)
GET  /actuator/health  the only health check; /edge/plane describes state but does not judge it
```

`GET /edge/plane` calls the same controller methods the other five doors call, so its blocks are the
same answers, not a second set of figures. It names each door in `doors`, including the refresh POST.

## 3. Traces across the two languages

`X-Trace-Id` is the plane's correlation field; `traceparent` / `tracestate` are the W3C parent the
Python core understands. `W3cTraceContextFilter` runs after `TraceIdFilter` and before
`RateLimitFilter`:

- a valid caller `traceparent` passes through byte-for-byte, with its `tracestate`;
- an absent or invalid one is replaced by a minted version-00 parent whose trace-id derives from the
  same `X-Trace-Id`; flags are `-00`, so the gateway does not assert sampling;
- the parent is echoed on the response, and a stale `tracestate` is dropped.

If the core's spans have no parent, check those three headers at both ends before suspecting the
collector — the collector is a local debug container, not a queryable backend.

## 4. Failures this plane has actually had

| symptom | cause | what to do |
| --- | --- | --- |
| registry says `UP` but every routed call falls back | default `SERVICE_HOST` is the hostname, which resolves to IPv6 link-local on this developer host while the core listens on IPv4 loopback | set `SERVICE_HOST=127.0.0.1`; see `docs/M14_SERVICE_PLANE.md` §11 |
| `POST /actuator/refresh` answers 415 | actuator POST wants `application/json` | send `{}` with `Content-Type: application/json` |
| a 500 gets replayed three times | Gateway's stock `SERVER_ERROR` series, or a comma-separated `statuses` string that did not bind | keep `series: []` and use YAML lists; `test_edge_config_parity.py` case 5 pins it |
| the breaker never opens | Resilience4j's stock `minimum-number-of-calls` (100) inside a 10-call window | both config copies set it to 5; the parity gate compares them |
| the two gateways disagree | the edge's `application.yml` and `config-repo/football-edge.yml` drifted | `pytest apps/api/tests/test_edge_config_parity.py` compares routes, breaker, limiter, plane setting and retry policy |
| a config change did not take effect | only `@RefreshScope` beans refresh | routes, breaker thresholds and rate-limit policy still need a restart; item 59 states this |

## 5. Verify

```bash
cd services && mvn -o -B package                              # 37 tests, all four modules SUCCESS
cd apps/api && .venv/Scripts/python.exe -m pytest tests/test_edge_config_parity.py -q
# live walks (built jars + a stand-in core): .scratch/walk-w3c.py, walk-refresh.py,
# walk-retry.py, walk-plane.py — 12/12, 9/9, 12/12, 16/16
```

## What this runbook does not claim

- It does not deploy a collector backend, Spring Cloud Bus, or a Redis-backed shared rate limiter.
  The limiter is per-process (ADR-001); see [`rate_limits.md`](rate_limits.md).
- It does not make `/edge/plane` a fleet-wide view. One instance answers about itself.
- It does not describe backups or erasure of the Java modules' state — they hold no football data.
  See [`full_restore.md`](full_restore.md) and [`erasure.md`](erasure.md) for the core's rows.
