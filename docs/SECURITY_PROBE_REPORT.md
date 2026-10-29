# The security probe: what M12's "pen test report clean" is answered with

M12's gate has two clauses. The load half is measured in
[docs/M12_PRODUCTION_HARDENING_VERIFICATION.md](M12_PRODUCTION_HARDENING_VERIFICATION.md). This document is
the other half, and its first line is the one that matters:

**This is a first-party probe, run by the project against its own API. It is not an external penetration
test, and it does not stand in for one.** No independent tester was commissioned. What the project can do
is ship the battery, run it against a live server, and leave a report whose every figure came from an HTTP
answer rather than from an assertion about the code.

## 1. The population is the committed contract

`scripts/security_probe.py` does not carry a list of doors. It reads `docs/api/openapi.json` — the same
artifact the web client and the currency gates read — and takes every operation that declares a
`security` requirement as a private door, every operation that declares none as a public one.

At the latest run recorded here (run F, §2) the contract's SHA-256 was
`350a93fa9919965e5780993e3aacff15d3b35eb5fd692f206fe46cb3cd9af1f6`, and the census read:

| measurement | value | floor |
| --- | --- | --- |
| secured operations | 220 | 200 |
| public operations | 53 | 40 |
| private `GET` paths | 95 | 85 |

The floors exist so an empty or half-read contract cannot pass as a clean probe; they are printed with
every run and they sit under the counts at HEAD. A door that lands in the contract without a credential
check is knocked on the next run, which is the point of deriving the population instead of typing it.

Runs A–D were made against contracts that answered the same 212 / 52 / 91 — runs A–C at
`31000605776d55d3cf0881358087391c65a0cd807869661ed86abe157c88b32e` (the description edits that landed
since — the trace, metrics, provider and jobs tiers — changed no door), run D at
`71a5f9bcd1ba3aa0cf8436ae7fde9dcd881ebd080d5e842249492e37e4fa4a04`. Run E was the run against the
contract as committed then, where the notifications tier added four private doors (two of them
`GET`s). Run F is the run against the contract as committed today, where §24's scouting report gained
four doors behind a share token — three private (`POST /scout/share`, `GET /scout/shares`,
`DELETE /scout/share/{token}`) and one public (`GET /scout/shared/{token}`, the only anonymous read of
the four) — so the census moved to 220 / 53 / 95. `apps/api/tests/test_security_probe_report_currency.py`
reads this document's SHA, census, floors and S1 count and compares them to the committed contract and
the probe's own constants.

## 2. The runs

Runs A–C were made on 2026-10-22 local time (their reports' timestamps are UTC, `2026-10-21T19:2x`)
against a live uvicorn on `127.0.0.1:8751`; run D was made on 2026-10-24 local time (`2026-10-23T19:16`
UTC) on port 8752; run E was made on 2026-10-28 local time (`2026-10-27T16:32` UTC) on port 8753; run F
was made on 2026-10-29 local time (`2026-10-29T12:17` UTC) on port 8732. All six used
`ENV=development` — the configuration in which the response cache and the rate limiter are live, since
both return early under `ENV=test`. Each run used a fresh server process and a fresh database, because
the limiter's window and the near cache live in process memory.

| | run A | run B | run C | run D | run E | run F |
| --- | --- | --- | --- | --- | --- | --- |
| server cache tier | degraded — the default Redis on 6379 refused the handshake, so the near tier served | **live** — the project's authenticated Redis on 63790 (`REDIS_URL`), connected | **live**, same tier and URL as run B | **live**, same tier and URL as run B | **live**, same tier and URL as run B | degraded — Redis unavailable, so the near tier served |
| CORS origin configured | `http://localhost:3000` (the probe's old default, set on that server) | the project's own `apps/api/.env` pair, `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://127.0.0.1:3218` (the web shell this run's page walk used) |
| database | `.scratch/m12-probe.db` (SQLite) | `.scratch/m12-probe-redis.db` (SQLite) | `football_os_probe_m12` on the project's PostgreSQL (port 54321), migrated to head | `football_os_probe_m12_d` on the project's PostgreSQL (port 54321), migrated to head `0036` | `football_os_probe_m12_e` on the project's PostgreSQL (port 54321), migrated to head `0041` | `.scratch/walk-academy.db` (SQLite, the world-synced walking database) |
| report | `.scratch/security-probe.json` | `.scratch/security-probe-redis.json` | `.scratch/security-probe-pg.json` | `.scratch/security-probe-d.json` | `.scratch/security-probe-e.json` | `.scratch/probe-18.json` |
| result | **10 passed / 0 failed / 0 server errors**, 7.83 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 19.61 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 11.37 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 6.88 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 9.27 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 1.58 s, rc=0 |

Run C differs from run B in one input — `DATABASE_URL` — so the engine is the only candidate for any
difference, and the ten checks read the same evidence: the same 212 doors answering 401, the same
MISS→HIT pairs for both callers, the same 429 at the 11th login. The probe's claim is therefore not a
SQLite-only claim, which matters because the deployed API runs on PostgreSQL.

Run D repeated run C's configuration on a fresh database migrated to head `0036`, after the contract's
descriptions changed and the jobs pipeline's terminal state was renamed. It answered the same ten
checks, so the green recorded here is against the contract committed then and not only against an
earlier snapshot of it.

Run E repeated the shape on a fresh database migrated to head `0041` — the migration that created the
notification tier's own tables — after the contract grew that tier's four doors (two `GET`s, two
`POST`s, all private). It answered the same ten checks against the contract as committed then, and the
census it read is the one printed in §1 for that run: 216 secured / 52 public / 93 private `GET` paths,
where every earlier run had read 212 / 52 / 91.

Run F repeated the shape against the walk database after §24's scouting report gained the share token's
four doors — three private and one public (`GET /scout/shared/{token}`) — moving the census to
220 / 53 / 95. It answered the ten checks on a server whose Redis was unavailable, so the near tier
served the cache checks; S4 read the same MISS→HIT pairs and the same separation between callers, which
is the evidence the near tier alone can give. The origin this run configured was the web shell's own
`http://127.0.0.1:3218` rather than the 3210 pair, because the page walk in the same session needed the
shell on that port; S8 read the configured origin echoed and the rogue one refused.

Runs B and C are the ones that matter for the cache claim: the shared tier was the source of the
cross-account replay fixed at M12 Item 6, so the probe was repeated with that tier actually in the
request path rather than with it degraded. `--allow-origin` now defaults to the project's own web origin (3210); run A had
used the previous default, which is why run A names a different origin from runs B and C.

**One red was observed before that green, and it is recorded because a battery whose failure path has
never been seen has an unproven green.** The first attempt at run B used the probe's then-default
`--allow-origin http://localhost:3000` against a server configured with the project's 3210 pair. S8 read
`allowed: [200, null]` — the request the probe believed was the configured origin came back with no
`Access-Control-Allow-Origin` — the runner printed `9 passed, 1 failed`, and exited 1. The default was
changed to the project's own origin, and run B was repeated in a fresh server process to reach the 10/10
above. S8 is the only check in this battery that has been individually watched failing on a live run; the
other nine have not, and this report does not claim otherwise.

The JSON reports are written to `.scratch/` and are not committed. This document carries their figures;
re-running the probe against the same contract is what reproduces them.

## 3. The ten checks

| ident | claim | measured in run F |
| --- | --- | --- |
| C0 | the private-door population is read from the committed contract and is not empty | 220 secured / 53 public / 95 private GET paths, contract SHA-256 above |
| S1 | every secured operation refuses a caller with no credential, and asks for one | **220 knocked, 220 answered 401**, 0 deviations |
| S2 | a token whose signature no longer verifies is refused | 401, body keys `code`, `message` |
| S3 | one account's row is absent to another, in both the direct read and the listing | create 201; owner read 200; stranger read **404**; stranger patch **404**; stranger's listing 200 with the owner's row absent; `/auth/me` caller-scoped |
| S4 | a public answer is served from cache under its own request id, and a cached private answer never crosses callers | private: A MISS → HIT, B MISS → HIT, **stranger never received the owner's row**; public: MISS → HIT, bodies byte-identical, request ids different |
| S5 | a login burst is refused with a coded 429 that says when to retry | 10 × 200, then **429 at the 11th hit**, `Retry-After: 295`, code `rate_limited` |
| S6 | refusals are one coded shape, name the field and rule, echo no submitted value and leak no internals | malformed JSON → 422 `validation_error`, row keys exactly `loc`/`msg`/`type` (no `input`, no `ctx`); short board → 422 with one detail row; **no leak marker** in any of the four bodies |
| S7 | every answer carries the security headers and its own request identity, including a refusal | `nosniff` on both 200 and 401, `Referrer-Policy: strict-origin-when-cross-origin`, distinct `X-Request-ID`s, numeric durations |
| S8 | only a configured origin is echoed, with credentials, and a rogue origin is never answered | configured origin: 200 + `Access-Control-Allow-Origin: http://localhost:3210` + credentials; rogue: 200 with **no** ACAO; preflight 200 with the configured origin; rogue preflight 400 with no ACAO |
| S9 | the refresh cookie is httpOnly, SameSite=strict and scoped to the auth path | `fo_refresh` from the registration response: httpOnly, `SameSite=strict`, `Path=/api/v1/auth`; `Secure` absent — see §4 |

Three details that make the negative results worth something:

* **S4 proves the cache was engaged before proving it did not leak.** A private `HIT` for the owning
  caller and a public `MISS → HIT` with byte-identical bodies are the evidence that the cache was serving
  at all; only then does "the stranger never received the owner's row" mean the key separated the two
  callers rather than the cache having been bypassed. The public repeat also carries a *different*
  `X-Request-ID`, which is the regression the M12 cache work fixed: a HIT replays the body, not the
  previous request's identity.
* **S5's first 429 lands on the 11th request** because the census knocked this path once before the
  burst; the published limit is 10 hits per 300 s per scope/client/path, so the arithmetic and the wire
  agree. `Retry-After` is a positive integer, not a placeholder.
* **S6 records the one shape that is not the API's own**: an unknown path and a wrong method are
  Starlette's answers, not doors, and they carry a string `detail`. The probe records that shape and turns
  green on the parts the project owns — it does not pretend the framework's 404 is a coded refusal.

## 4. What this run does not claim

* **No third-party penetration test, no independent tester, no source review by an outsider.** This is the
  project checking its own claims; a reader who needs an external report does not have one here.
* **No transport security was exercised.** The probe speaks loopback HTTP. There is no TLS handshake, no
  HSTS assertion, and the API sets no `Content-Security-Policy` header at all; the header set it does own
  is the one S7 measures.
* **No denial-of-service or saturation test.** The burst is twelve login requests. The load ceiling is a
  separate measurement with its own harness and its own caveats.
* **No dependency, container-image or secret scan.** Those are other instruments, and none ran here.
* **No browser-side testing.** XSS, DOM injection and clickjacking are outside this probe; the web tier's
  own walks check rendering and console errors, not adversarial input.
* **Two live objects, one cache path, one limiter scope.** S3 proves ownership on one board and its
  listing; S4 isolates one private path and one public path; S5 spends one login window from one client.
  The code-level population is covered by the authorization census and the answer-table gates, not by
  this probe.
* **The refresh cookie's `Secure` flag is absent here because the server runs in development.**
  `is_production` gates it; no production server was exercised.
* **The shared tier's keyspace was not inspected.** S4 proves the other caller did not receive the owner's
  answer through the API. The absence of the private key in Redis itself is the shared-tier gate's case,
  not this probe's.
* **A clean run is the absence of ten specific failures**, not the absence of vulnerabilities.

## 5. How to reproduce

```bash
cd apps/api
DB="sqlite:///D:/足球项目/.scratch/security-probe.db"
DATABASE_URL="$DB" /d/足球项目/.venv/Scripts/python.exe -m alembic upgrade head
ENV=development DATABASE_URL="$DB" \
  REDIS_URL="redis://:football@127.0.0.1:63790/0" \
  /d/足球项目/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8751
```

and, in a second shell:

```bash
cd /d/足球项目
.venv/Scripts/python.exe scripts/security_probe.py \
  --base http://127.0.0.1:8751 --report .scratch/security-probe.json
```

For run C, only the database differs — create it once, then point both `alembic` and the server at it:

```bash
docker exec football_os_db psql -U football -d postgres -c "CREATE DATABASE football_os_probe_m12"
DB="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_probe_m12"
DATABASE_URL="$DB" /d/足球项目/.venv/Scripts/python.exe -m alembic upgrade head   # from apps/api
ENV=development DATABASE_URL="$DB" REDIS_URL="redis://:football@127.0.0.1:63790/0" \
  /d/足球项目/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8751
```

Run D repeated that shape with its own database and port — `football_os_probe_m12_d`, port 8752,
`--report .scratch/security-probe-d.json` — after `alembic upgrade head` reached `0036`. Run E
repeated it again — `football_os_probe_m12_e`, port 8753, `--report .scratch/security-probe-e.json` —
after `alembic upgrade head` reached `0041`.

Three properties of the invocation matter:

1. **A fresh server process per run.** The limiter's window is in memory, so a second run against the
   same process finds the window already spent and S5 fails on `first_429_at_burst_request`. Restarting
   resets the window; nothing about the API changed.
2. **`ENV` must not be `test`.** The limiter and the response cache both return early there, and the
   probe would be measuring the bypass rather than the behaviour.
3. **`REDIS_URL` is optional.** Without it the probe still passes and measures the near tier (run A);
   with it, the shared tier is in the request path (run B). `--allow-origin` defaults to
   `http://localhost:3210` and must name an origin the server's `CORS_ORIGINS` contains.

The probe registers two accounts and creates one board per run; both carry a UUID marker, so repeated
runs on one database do not collide. The process exits 0 only when every check passed and no 5xx was
recorded.
