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

At the latest run recorded here (run M, §2) the contract's SHA-256 was
`76341e7365ca5cccb83dead42c538f7a6c54aef33f04f189f3d8ca0c6ae5a5a5`, and the census read:

| measurement | value | floor |
| --- | --- | --- |
| secured operations | 240 | 200 |
| public operations | 55 | 40 |
| private `GET` paths | 103 | 85 |

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

Run G was the run against the contract as committed then: item 18's academy plan share added four
doors — three private (`POST /club/academy/{ident}/plans/{plan}/share`, `GET /club/academy/shares`,
`DELETE /club/academy/shares/{token}`) and one public (`GET /club/academy/shared/{token}`) — and item
21's cost-alert tier added three private doors (`GET /metrics/alerts`, `POST /metrics/alerts/check`,
`POST /metrics/alerts/{alert}/acknowledge`), so the census moved to 226 / 54 / 97. Run H is the run
against the contract as committed then: item 6's wage ceiling added the `wage_ceiling` field to
`CareerIn` (with its 0..10,000,000 bounds), which moved the contract's bytes without adding or removing
a door, so the census stayed 226 / 54 / 97. Run I was the run against the contract as committed then:
the consolidated career-milestone landed nine new private doors (five behind `/api/v1/careers*` —
cup, season-tickets (get+post), stadium, tickets (get+put), training (get+post) = five paths / eight
operations — and the new `/api/v1/transfers*` door), so secured operations moved to 235 / 54 / 100 and
the S1 column moved with them below. Run J is the run against the contract as committed then:
`GET /api/v1/leaderboard` is a public read by design and the contract now says so (`security: []`), so
one operation left the secured set and the public set grew by one — 236 / 55 / 100. Run K is the run
against the contract as committed today: M15's limiter published its own operator window
(`GET /api/v1/metrics/rate-limit`) and the notification tier published its per-kind mutes
(`GET` and `PUT /api/v1/notifications/preferences`), three private operations across two new paths, both
of them `GET`s — so the census moved to 239 / 55 / 102 and the public set did not move at all. Run L is the run against the contract as committed today: M16's Redis-Streams broker published its own operator window (`GET /api/v1/metrics/jobs-stream`, one private `GET` across one new path), so the census moved to 240 / 55 / 103 and the public set did not move; the clip-report's analyse door also grew a `background` query parameter (`POST /api/v1/video/{ident}/analyse?background=true`), which changed the contract's bytes without adding or removing a door, so every ledger naming the SHA moved with it. The run recorded here was made against the tree as committed (2026-11-12T13:26 UTC, port 8798), on the same configuration as run K. Run M is the run against the contract as committed today: §159's provider ledger publication put two additive fields on `/api/v1/metrics/providers` (`cached_input_tokens_total` and `cache_hit_rate`), the contract was re-exported on 2026-11-13 (`scripts/export_openapi.py`), its bytes moved and its SHA moved with it — without adding, removing or re-gating a door, so the census stayed 240 / 55 / 103 and every ledger naming the SHA moved with it. The run recorded here was made against the tree as committed (2026-11-13T09:15 UTC, port 8751), on a scratch SQLite database the app created on startup, `ENV=development`, `CORS_ORIGINS` set to the project's own 3210 pair.

## 2. The runs

Runs A–C were made on 2026-10-22 local time (their reports' timestamps are UTC, `2026-10-21T19:2x`)
against a live uvicorn on `127.0.0.1:8751`; run D was made on 2026-10-24 local time (`2026-10-23T19:16`
UTC) on port 8752; run E was made on 2026-10-28 local time (`2026-10-27T16:32` UTC) on port 8753; run F
was made on 2026-10-29 local time (`2026-10-29T12:17` UTC) on port 8732; run G was made on 2026-10-30 local time (`2026-10-29T19:27` UTC) on port 8751; run H was made on 2026-10-31 local time (`2026-10-30T16:18` UTC) on port 8754; run I was made on 2026-11-08 local time (`2026-11-08T13:14` UTC) on port 8755; run J was made on 2026-11-09 local time (`2026-11-09T14:52` UTC) on port 8751; run K was made on 2026-11-11 local time (`2026-11-11T08:31` UTC) on port 8799; run L was made on 2026-11-12 local time (`2026-11-12T13:26` UTC) on port 8798; run M was made on 2026-11-13 local time (`2026-11-13T09:15` UTC) on port 8751. All thirteen used
`ENV=development` — the configuration in which the response cache and the rate limiter are live, since
both return early under `ENV=test`. Each run used a fresh server process, because the limiter's window
and the near cache live in process memory. Runs A–I each used a fresh database; run J ran against the
development database (`football_os` on the project's PostgreSQL, migrated to head `0060`) while the
leaderboard contract change was being verified on it; run K ran against a scratch SQLite database the
app created on startup and migrated to head `0061`, so the limiter's own operator window and the
notification mutes were both live doors rather than paths the contract promised and the server lacked.
Run L repeated the shape — a scratch SQLite database (`.scratch/probe-l.db`, created by the app on
startup through `init_db()`'s `create_all`, not Alembic-migrated, so the contract's doors were live
whether or not a migration had been applied) on port 8798, `ENV=development` — against the contract
as re-exported then, with the broker's own operator window live rather than promised. Their evidence
is read back below.

| | run A | run B | run C | run D | run E | run F | run G | run H | run I | run J | run K | run L | run M |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| server cache tier | degraded — the default Redis on 6379 refused the handshake, so the near tier served | **live** — the project's authenticated Redis on 63790 (`REDIS_URL`), connected | **live**, same tier and URL as run B | **live**, same tier and URL as run B | **live**, same tier and URL as run B | degraded — Redis unavailable, so the near tier served | degraded — no `REDIS_URL` was set on this server, so the near tier served | degraded — no `REDIS_URL` was set on this server, so the near tier served | **live** — the project's authenticated Redis on 63790 db 7 (`REDIS_URL`), connected | degraded — no `REDIS_URL` was set on this server, so the near tier served | degraded — no `REDIS_URL` was set on this server, so the near tier served | degraded — no `REDIS_URL` was set on this server, so the near tier served | degraded - no `REDIS_URL` was set on this server, so the near tier served |
| CORS origin configured | `http://localhost:3000` (the probe's old default, set on that server) | the project's own `apps/api/.env` pair, `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://127.0.0.1:3218` (the web shell this run's page walk used) | `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | `http://localhost:3210` | the project's own pair, `http://localhost:3210` |
| database | `.scratch/m12-probe.db` (SQLite) | `.scratch/m12-probe-redis.db` (SQLite) | `football_os_probe_m12` on the project's PostgreSQL (port 54321), migrated to head | `football_os_probe_m12_d` on the project's PostgreSQL (port 54321), migrated to head `0036` | `football_os_probe_m12_e` on the project's PostgreSQL (port 54321), migrated to head `0041` | `.scratch/walk-academy.db` (SQLite, the world-synced walking database) | `.scratch/probe-g.db` (SQLite, created by the app on startup) | `.scratch/probe-h.db` (SQLite, created by the app on startup) | `football_probe_i` on the project's PostgreSQL (port 54321), migrated to head `0058` | `football_os` on the project's PostgreSQL (port 54321), migrated to head `0060` | `.scratch/probe-k.db` (SQLite, created by the app on startup, migrated to head `0061`) | `.scratch/probe-l.db` (SQLite, created by the app on startup through `init_db()`) | `.scratch/probe-live2.db` (SQLite, created by the app on startup through `init_db()`) |
| report | `.scratch/security-probe.json` | `.scratch/security-probe-redis.json` | `.scratch/security-probe-pg.json` | `.scratch/security-probe-d.json` | `.scratch/security-probe-e.json` | `.scratch/probe-18.json` | `.scratch/security-probe-g.json` | `.scratch/security-probe-h.json` | `.scratch/security-probe-run-i.json` | `.scratch/security-probe-run-j.json` | `.scratch/security-probe-run-k.json` | `.scratch/security-probe-l.json` | `.scratch/security-probe-m.json` |
| result | **10 passed / 0 failed / 0 server errors**, 7.83 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 19.61 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 11.37 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 6.88 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 9.27 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 1.58 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 17.58 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 15.7 s, rc=0 | **10 passed / 0 failed / 0 server errors**, 6.52 s | **10 passed / 0 failed / 0 server errors**, 5.86 s | **10 passed / 0 failed / 0 server errors**, 44.51 s | **10 passed / 0 failed / 0 server errors**, 41.97 s | **10 passed / 0 failed / 0 server errors**, 9.88 s |

Run M repeated the shape on a scratch SQLite database the app created on startup (`.scratch/probe-live2.db`), with no `REDIS_URL` (the near tier served the cache checks) and `CORS_ORIGINS` set to the project's own pair, against the contract as re-exported with its two additive provider-metric fields. S8 failed on the first attempt for one reason only: the server was booted with the application default `CORS_ORIGINS` (`http://localhost:3000`), so neither the configured pair nor the rogue origin echoed an `access-control-allow-origin` header and the check failed closed. Rebooted with the documented 3210 pair (`.env.example`), the same probe answered **10 / 10, 0 failed, 0 server errors, 9.88 s** — the same ten checks as runs K and L against the same door census.

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

Run G repeated the shape on a fresh SQLite database that the app created on startup, against the
contract as committed after item 18's academy plan share and item 21's cost-alert tier. It answered
the ten checks on a server with no `REDIS_URL`, so the near tier served the cache checks; S4 read the
same MISS→HIT pairs and the same separation between callers. The three alert doors are admin-only, and
S1 knocked each of them with no credential and recorded 401. The census it read is the one printed in
§1 for that run: 226 secured / 54 public / 97 private `GET` paths.

Run I repeated the shape on a fresh PostgreSQL database (`football_probe_i`, port 54321) migrated to
head `0058`, against the contract as committed after the career-milestone consolidation (`cadf3d3`).
It answered the ten checks on a live shared Redis tier (db 7); S1 knocked every secured door with no
credential and recorded 401 for all 235. The census it read is the one printed in §1: 235 secured /
54 public / 100 private `GET` paths; the S1 row in §3 records the same figures.

Run J repeated the shape on the development PostgreSQL database (`football_os`, port 54321) migrated to
head `0060`, against the contract after the leaderboard read was published as public. It answered the
ten checks with the near cache tier serving (no `REDIS_URL` was set on that server); S1 knocked every
secured door with no credential and recorded 401 for all 236 — including `POST /api/v1/leaderboard`,
which the contract still marks secured — while the now-public `GET /api/v1/leaderboard` answered 200
without one. The census it read is the one printed in §1: 236 secured / 55 public / 100 private `GET`
paths; the S1 row in §3 records the same figures.

Run K repeated the shape on a scratch SQLite database (`.scratch/probe-k.db`, created by the app on
startup and migrated to head `0061`) against the contract after M15 replaced the fixed-window limiter
with a two-tier token bucket and the notification tier published its per-kind mutes. It answered the ten
checks with the near cache tier serving (no `REDIS_URL` was set on that server); S1 knocked every secured
door with no credential and recorded 401 for all 239, including the limiter's own new operator window
`GET /api/v1/metrics/rate-limit`. The census it read is the one printed in §1: 239 secured / 55 public /
102 private `GET` paths; the S1 row in §3 records the same figures.

Run L repeated the shape on a scratch SQLite database (`.scratch/probe-l.db`, created by the app on
startup) against the contract as re-exported today — M16's operator window
`GET /api/v1/metrics/jobs-stream` knocked as one of the 240, and the analyse door's new
`?background=true` re-export moved the SHA without moving the census. It answered the ten checks with
the near cache tier serving (no `REDIS_URL` was set on that server); S1 knocked every secured door
with no credential and recorded 401 for all 240, three of them throttled first and waited out and
re-knocked (`throttle_waits`: three entries, each `retry_after: 10` on policy `"upload";q=8;w=1` — the
same three video doors the throttle lesson names). The census it read is the one printed in §1: 240
secured / 55 public / 103 private `GET` paths; the S1 row in §3 records the same figures.

**Run K is the first run whose green required the probe itself to change, and both changes are recorded
because a battery that cannot survive its own product's hardening measures the battery.** M15's limiter
answers *before* routing and before body validation, which moved two of the probe's own assumptions:

* **S1 now meets the throttle it is provoking.** Knocking 239 doors in one burst spends the upload
  policy's eight-token budget three times over, so three knocks came back 429 instead of 401 — a correct
  answer from the server and a false deviation in the census. `call()` gained an opt-in
  `throttle_retries` that waits out `Retry-After` and knocks again, and S1 uses it; the waits are
  published in the evidence rather than hidden (`throttle_waits`: three entries, each `retry_after: 10`
  on policy `"upload";q=8;w=1`). It is opt-in because S5 exists to provoke a 429 and must keep it.
* **S6's malformed post had to leave the login door.** S5 spends the login budget on purpose, and since
  the limiter now precedes FastAPI's body parser, a malformed post there measures the throttle
  (429 `rate_limited`) instead of the validation shape S6 exists to read. The malformed post is now
  `POST /api/v1/boards` as the account — the same framework refusal on a door whose budget the probe has
  not spent — and S6 read 422 `validation_error` again.

Both were observed as reds first: the run before these two edits printed **8 passed, 2 failed** with S1
reporting three deviations and S6 reporting `malformed_json: [429, "rate_limited"]`. Neither red was a
server defect, and neither is hidden by the green above.

Two further properties of this run are worth naming. The probe's HTTP clients now set `trust_env=False`:
an operator's `NO_PROXY` containing `[::1]` made httpx raise `InvalidURL: Invalid port: ':1]'` before a
single request was sent, and a proxy in the path would have made every figure describe somewhere else.
And the run recorded here was made against a **freshly started** server process, as §5 requires — an
earlier green against an already-used process read `first_429_at_burst_request: 10` because the census
knock and the burst shared a spent window, which is the arithmetic §5 warns about rather than a
different limit. the shared tier was the source of the
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

| ident | claim | measured in run L |
| --- | --- | --- |
| C0 | the private-door population is read from the committed contract and is not empty | 240 secured / 55 public / 103 private GET paths, contract SHA-256 above |
| S1 | every secured operation refuses a caller with no credential, and asks for one | **240 knocked, 240 answered 401**, 0 deviations, 3 throttled knocks waited out and re-knocked |
| S2 | a token whose signature no longer verifies is refused | 401, body keys `code`, `message` |
| S3 | one account's row is absent to another, in both the direct read and the listing | create 201; owner read 200; stranger read **404**; stranger patch **404**; stranger's listing 200 with the owner's row absent; `/auth/me` caller-scoped |
| S4 | a public answer is served from cache under its own request id, and a cached private answer never crosses callers | private: A MISS → HIT, B MISS → HIT, **stranger never received the owner's row**; public: MISS → HIT, bodies byte-identical, request ids different |
| S5 | a login burst is refused with a coded 429 that says when to retry | 10 × 200, then **429 at the 11th hit**, `Retry-After: 22`, code `rate_limited` |
| S6 | refusals are one coded shape, name the field and rule, echo no submitted value and leak no internals | malformed JSON on a board post as the account → 422 `validation_error`, row keys exactly `loc`/`msg`/`type` (no `input`, no `ctx`); short board → 422 with one detail row; **no leak marker** in any of the four bodies |
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
* **S5's first 429 lands on the 11th request**, and the check that gates it is `first_429 > 1` — not a
  fixed index, because the ceiling is a token bucket and the index depends on elapsed time. The door's
  published limit is `limit(request, 10, 300, scope="login")`, keyed per scope/method/client/path; the
  census knocked this path before the burst, and the bucket refills continuously at 10/300 s between
  that knock and the burst as well as during it. What M15 changed is the retry: `Retry-After` is now the
  seconds until *one* token returns (22 here) rather than the seconds until the window rolls over (297
  under the retired fixed window). It is a positive integer, not a placeholder.
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

Run K used a scratch SQLite database the app creates and migrates itself on startup, so no `alembic`
step is needed — only a fresh process and the two environment variables the limiter reads:

```bash
cd apps/api
ENV=development DATABASE_URL="sqlite:///D:/足球项目/.scratch/probe-k.db" \
  RATE_LIMIT_ENABLED=1 CORS_ORIGINS="http://localhost:3210,http://127.0.0.1:3210" \
  /d/足球项目/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8799
```

and, in a second shell from the repository root:

```bash
.venv/Scripts/python.exe scripts/security_probe.py \
  --base http://127.0.0.1:8799 --report .scratch/security-probe-run-k.json
```

Run L used the same shape on port 8798 against `.scratch/probe-l.db`:

```bash
cd apps/api
ENV=development DATABASE_URL="sqlite:///D:/足球项目/.scratch/probe-l.db" \
  RATE_LIMIT_ENABLED=1 CORS_ORIGINS="http://localhost:3210,http://127.0.0.1:3210" \
  /d/足球项目/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8798
```

and, in a second shell from the repository root:

```bash
.venv/Scripts/python.exe scripts/security_probe.py \
  --base http://127.0.0.1:8798 --report .scratch/security-probe-l.json
```

Three properties of the invocation matter:

1. **A fresh server process per run.** The limiter's bucket is in memory when no store is reachable, so a
   second run against the same process finds the budget already spent and S5 reads
   `first_429_at_burst_request: 10` instead of 11. Restarting refills the bucket; nothing about the API
   changed. With `RATE_LIMIT_REDIS_URL` set the bucket is shared and outlives the process, so a run
   against a used store needs either a fresh database or a wait of one refill period.
2. **`ENV` must not be `test`.** The limiter and the response cache both return early there, and the
   probe would be measuring the bypass rather than the behaviour.
3. **`REDIS_URL` is optional.** Without it the probe still passes and measures the near tier (run A);
   with it, the shared tier is in the request path (run B). `--allow-origin` defaults to
   `http://localhost:3210` and must name an origin the server's `CORS_ORIGINS` contains.

The probe registers two accounts and creates one board per run; both carry a UUID marker, so repeated
runs on one database do not collide. The process exits 0 only when every check passed and no 5xx was
recorded.
