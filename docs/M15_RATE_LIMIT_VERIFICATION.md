# M15 — one limiter, one clock, one identity

**Verified 2026-11-11.** This record covers the takeover of the rate-limiting tier: the fixed window
that had been in `app.core.security` since M1 is retired, and both callers — the middleware that prices
every `/api/v1` door and the per-door `limit()` helper — now ask one token bucket, counted by one
identity rule, on one clock, with one dresser writing the answer's headers.

Every figure below was read from a command's output. The commands are printed beside them.

---

## 1. What was wrong, stated as defects rather than as an upgrade

The old tier was not slow. It was **wrong in four ways that no tuning inside it could fix**, and each
one is now held by a case:

1. **It counted the wrong caller.** The key was the socket's peer. Behind this project's own edge every
   request arrives from the proxy's address, so one bucket counted the whole internet; and a caller
   presenting a credential was counted by address anyway, so one account could spend another's budget
   by sharing its NAT. `caller_key` is the one identity rule now.
2. **Its stated bucket bound was not one.** It evicted the least-recently-seen bucket when the dict
   grew — *including buckets still inside their window*, which hands that caller a fresh budget. The
   replacement bounds the pre-filter at `MAX_LOCAL_BUCKETS = 8192`, where eviction is safe because the
   shared store is the authority: an evicted pre-filter bucket costs a round trip, not a budget.
3. **Its `Retry-After` promised something the algorithm did not do.** A fixed window admits `2 × limit`
   across its boundary — `limit` at 00:59.9 and `limit` again at 01:00.1 — and the header it published
   was the seconds to window rollover. A token bucket admits `capacity + rate × t` over any interval,
   and the retry it publishes is the seconds until *one token* exists. Probe run K read the difference:
   `Retry-After: 22` where the fixed window's runs read `297`.
4. **Two places wrote the headers, so two kinds of answer wrote none.** The middleware dressed a
   normal response and the refusal dressed itself; a cache HIT replayed the miss's numbers, and a 500 —
   which never comes back through the middleware — carried no budget at all. A client retrying a 500 in
   a loop is exactly the client that needs to be told it is about to be refused.

## 2. What landed

| file | role |
| --- | --- |
| `apps/api/app/core/ratelimit.py` (new, 447 lines) | the algorithm: `Policy`, `Decision`, `MemoryLimiter`, `RedisLimiter`, `TwoTierLimiter`, the Lua script, the process singleton and `snapshot()` |
| `apps/api/app/core/rate_policy.py` (new, 157 lines) | the policy table, `policy_for`, `caller_key`, `EXEMPT_PATHS`, and `rate_decision_var` |
| `apps/api/app/main.py` | `judge_request` + `rate_limit_refusal`; the middleware prices before routing, before body validation and before the response cache; `PER_REQUEST_HEADERS` grows by the eight budget names |
| `apps/api/app/core/security.py` | `RateLimiter` and the `rate_limiter` singleton deleted; `limit()` now asks `get_limiter` with a door key that carries the verb |
| `apps/api/app/core/response_headers.py` | `dress_response` writes `decision.headers()` — the one list, for the 200, the HIT, the 429 and the 500 |
| `apps/api/app/api/v1/auth.py` | the account-erasure door calls `limit(...)` instead of the deleted singleton |
| `apps/api/app/api/v1/metrics.py` | `GET /api/v1/metrics/rate-limit`, an operator's window on the tier |
| `apps/api/app/core/config.py`, `apps/api/.env.example` | three settings, documented where an operator looks for them |
| `scripts/security_probe.py` | S1 waits out a throttle it caused itself; S6's malformed post moved to a door the account may call |

`git diff --stat` over the eight modified code paths: **259 insertions, 66 deletions**, plus the two new
modules and the new test file.

## 3. The algorithm, and the four questions a per-process dict cannot answer

**Which clock?** The Lua script reads `redis.call('TIME')`, so N workers share the server's clock and a
caller cannot dodge the limit by landing on the worker whose clock is slow. `elapsed` is clamped at
zero: a replica whose wall clock is behind the timestamp another worker wrote must not mint tokens by
travelling backwards.

**Which key?** A bucket expires at the instant it would have refilled to capacity —
`PEXPIRE ceil(capacity / refill_per_ms) + 1000`, floored at `MIN_TTL_MS = 1000` so a tiny policy cannot
expire between two requests in the same millisecond. From that instant the state it holds is the state
a missing key produces, so expiring it grants nothing.

**What happens when the store is down?** Neither deny-everything (a cache outage becomes a product
outage) nor allow-everything (it becomes an unbounded one). `build_cluster` pings with
`socket_connect_timeout=0.5, socket_timeout=0.5` — deliberately much shorter than the cache tier's,
because a limiter sits in front of *every* request — and returns `None` on any exception. The tier then
answers per process and **stamps `X-RateLimit-Scope: process` on every answer**, so the degraded state
is published rather than inferred.

**How much does the check cost?** `TwoTierLimiter` is an admission pre-filter in front of the shared
store. The local bucket is sized to the cluster's capacity, so it can never refuse a request the
cluster would admit. A caller inside its budget asks Redis once per request — the price of a
cluster-correct answer. A caller outside it is answered locally, so a flood reaches the store at the
*refill* rate rather than at the flood's rate. `short_circuited` counts those answers and the metrics
door publishes it.

The read-modify-write is one `EVALSHA`: `HMGET tokens ts` → refill → `HSET` → `PEXPIRE`, returning
`{allowed, floor(tokens), retry_ms}`. No worker can interleave another's refill.

## 4. The price list, read from the operator's own door

`GET /api/v1/metrics/rate-limit` as an `admin` on a live uvicorn (port 8799, the run-K server):

| policy | burst | refill/s | sustained/min | priced doors |
| --- | --- | --- | --- | --- |
| `auth` | 12 | 0.2 | 12.0 | `/api/v1/auth/` |
| `expensive` | 24 | 0.5 | 30.0 | 7 prefixes |
| `upload` | 8 | 0.1 | 6.0 | 2 prefixes |
| `write` | 60 | 1.0 | 60.0 | 5 prefixes |
| `default` | 240 | 40.0 | 2400.0 | everything else under `/api/v1/` |

The same answer carried `enabled: true`, `trusted_proxies: ["127.0.0.1/32", "::1/128"]`, and
`tiers: {configured: true, scope: "process", short_circuited: 0, process_allowed: 312, process_refused: 6}`
— that server had no `REDIS_URL`, and the door said so instead of leaving an operator to guess.

The door asks for the standing its description names: anonymous → **401 `unauthenticated`**, a `player`
→ **403 `insufficient_role`** with `held`/`required`/`roles` in the detail.

**Only `/api/v1/` is priced.** `EXEMPT_PATHS` is `healthz`, `openapi.json`, `docs`,
`docs/oauth2-redirect` — a health check that can be rate-limited is a health check that reports the
product down because a monitor was enthusiastic. A prefix is not a word: one ending in `/` matches
anything below it, one that does not must be followed by `/` or the end of the path, so
`/api/v1/coach/ask` is priced and `/api/v1/coach/askers` is not. Getting that wrong is silent — the
request is simply charged the wrong price.

## 5. Who is asking

`caller_key`, three cases in order of strength:

* `acct:<sha256[:32]>` — a credential was presented. Per-account budgets survive NAT, and one account
  cannot escape its budget by reconnecting. The key is a truncated digest because it is written to
  Redis where an operator can read it: stable for the token's life, useless without it.
* `fwd:<address>` — the peer is inside `RATE_LIMIT_TRUSTED_PROXIES` and reported an address. The
  **left-most** entry is the original client; each proxy appends, so the right-most is the proxy itself
  and would collapse every caller into one bucket.
* `ip:<peer or 'unknown'>` — the socket's own peer. An empty peer (an ASGI transport in a test) is named
  `ip:unknown` rather than `""`, because an empty key would put every such request in one bucket and
  make the gate's own tests fight each other.

A forwarded header from an untrusted peer is **not read at all**. Trusting it would let any caller mint
a new identity per request by typing one.

The middleware's key is `f"{policy.name}:{identity}"` — an account that has spent its login budget has
not spent its reading budget. The door helper's key is
`f"door:{scope}:{request.method}:{identity}:{request.url.path}"`, and both the path and the verb are
load-bearing (§7).

## 6. One dresser, seven headers

`Decision.headers()` is the only place the set is written:

```
RateLimit-Policy: "default";q=240;w=1
RateLimit-Limit: 240
RateLimit-Remaining: 239
RateLimit-Reset: 0
X-RateLimit-Limit: 240
X-RateLimit-Remaining: 239
X-RateLimit-Scope: process
```

read from a live public answer. Both spellings are sent on purpose: `RateLimit-*` is the IETF draft's
and `X-RateLimit-*` is what every client library written before it reads. A refusal adds `Retry-After`.

Two properties are asserted rather than assumed:

* **The headers describe the request being answered, not the answer.** They are computed before the
  cache is consulted, so all eight names are in `PER_REQUEST_HEADERS` and are stripped from the stored
  entry; `dress_response` then *assigns* the current decision's values. Defaulting them would replay
  the miss's `Remaining` on every hit — a budget that appears not to move while it is being spent.
* **The crash carries them too.** `install_error_handlers`'s `_unhandled` calls the same dresser, so a
  500 publishes the same seven headers as a 200. `rate_decision_var` is a `ContextVar` rather than
  `request.state` precisely because the dresser is handed a response and no request.

## 7. The door census: why the key carries the path and the verb

A read-only census over the tree's `limit(...)` call sites (`D:\probe203\census.py`, re-run at
close-out) measured **222 scoped doors**, **8 scopes reused at more than one ceiling**, and **4
`(scope, path)` pairs priced differently by verb**:

| scope | path | one verb | the other |
| --- | --- | --- | --- |
| `academy_write` | `/club/academy/{ident}/plans/{plan}` | DELETE 10/60 | PATCH 20/60 |
| `career_season_tickets` | `/careers/{ident}/season-tickets` | GET 60/60 | POST 20/60 |
| `career_tickets` | `/careers/{ident}/tickets` | GET 60/60 | PUT 20/60 |
| `career_training` | `/careers/{ident}/training` | GET 60/60 | POST 20/60 |

The eight reused scopes are `academy_write`, `career_season_tickets`, `career_tickets`,
`career_training`, `club_write`, `community_write`, `creator_write`, `scout_shortlist_write`. So a
bucket per *scope* would merge doors that were priced apart and let whichever was called last decide
the ceiling for all of them; and without the verb, twenty writes to `/careers/{ident}/tickets` would
leave the read door serving nothing against a ceiling it publishes as sixty.

## 8. The cases

`tests/test_rate_limit.py` **26 cases** (503 lines) and `tests/test_rate_limiter.py` **12 cases**
(307 lines) — **38** across the tier. `tests/test_metrics.py` adds the operator door's two.

Two of them need a live store and skip without one, which is why the tier is measured on **both legs**:

```bash
cd apps/api
REDIS_URL="redis://:football@127.0.0.1:63790/9" \
  ../../.venv/Scripts/python.exe -m pytest tests/test_rate_limit.py tests/test_rate_limiter.py \
  tests/test_metrics.py --no-header -p no:randomly
# 57 passed, 1 warning in 146.68s

../../.venv/Scripts/python.exe -m pytest tests/test_rate_limit.py tests/test_rate_limiter.py \
  tests/test_metrics.py --no-header -p no:randomly
# 55 passed, 2 skipped, 1 warning in 121.99s
```

Both legs collected **57**; the junit XML reads `failures=0 errors=0` on each, and the no-store leg's
two skips are named — `test_the_script_is_atomic_against_a_live_server` and
`test_the_crash_answer_names_the_cluster_when_a_store_answers`. No other case is conditional.

`test_the_script_is_atomic_against_a_live_server` spends a `Policy("live", capacity=3,
refill_per_second=1.0)` against a key namespaced by `time.time_ns()`, reads `Remaining` as `[2, 1, 0]`,
reads the refusal's scope as `cluster` and its retry as `1`, sleeps 1.05 s and reads the bucket
refilled — then deletes its own key. It is the only case that proves the Lua script rather than the
Python around it.

### Two harness findings this unit paid for

**A test that hard-codes the degraded tier's name lets the operator's environment decide the verdict.**
`test_the_crash_answer_carries_the_budget_too` asserted `X-RateLimit-Scope == "process"`, and it went
red — `cluster != process` — on a limiter working exactly as designed, because `REDIS_URL` was exported
in that shell. Both wired callers pass `settings.rate_limit_redis_url`, so the fixture now pins
`rate_limit_redis_url=""` and the cluster direction has its own case
(`test_the_crash_answer_names_the_cluster_when_a_store_answers`, skipped without a store). The wiring is
proved against a known tier; the live store has its own leg.

**A case that counts tokens across two HTTP calls is counting the host's speed as well.** `DEFAULT`
refills 40 tokens a second, so a 25 ms gap between two requests puts back the token the first one spent
and `Remaining` never moves. Under load this suite saw a 16 s call and the decrement case went red on a
correct limiter. The `pinned_budget_clock` fixture gives *only the tier's arithmetic* a fixed `now`
(`monkeypatch` on `tier.local.decide`), not `time.monotonic` process-wide — the event loop under
`TestClient` reads that same clock to decide when its own deadlines are due.

**An environment fault is not an assertion fault.** Both live-store cases went red together with
`ConnectionError: Error 10061 connecting to 127.0.0.1:63790` after having passed twenty minutes
earlier. `docker inspect` showed the container had exited and been restarted; the published port stays
LISTENING after the engine dies, so the port was not evidence. With the container healthy again the
same command read 57 passed. Nothing in the product changed.

## 9. Reverse controls: each claim has a mutation that reddens exactly its own cases

Three arms, run against the tree at rest (`at rest: rc=0 red=[]`), each splicing one needle, running
only `tests/test_rate_limiter.py` and `tests/test_rate_limit.py` so a red is attributable, and restoring
the file byte-exactly with a sha256 check. **3/3 MATCHED** — every arm's measured red set equalled its
predicted set, no arm reddened a case it did not predict, and every file was restored (`restored=True`).

| arm | the mutation | predicted and measured red |
| --- | --- | --- |
| A1 | `security.py`: the door key loses `:{request.method}` | `test_a_read_door_and_a_write_door_on_one_path_keep_their_own_budgets`, `test_the_door_asks_the_one_tier_with_a_door_key` |
| A2 | `config.py`: `rate_limit_redis_url` stops falling back to `REDIS_URL` | `test_the_store_defaults_to_the_cache_tiers_and_can_be_pointed_elsewhere` |
| A3 | `response_headers.py`: `decision = rate_decision_var.get()` → `decision = None` | `test_a_priced_door_publishes_its_budget_on_every_answer`, `test_the_crash_answer_carries_the_budget_too`, `test_the_refusal_publishes_the_same_header_set_as_the_success` |

A1 is the arm that pays for §7's census: without the verb, the GET priced at 60/60 and the PUT priced at
20/60 on `/careers/{ident}/tickets` become one bucket, and the case that holds them apart goes red.

**The harness itself had a defect that would have made A1's red unattributable.** `security.py` is CRLF
on this checkout while `config.py` and `response_headers.py` are LF. The first version of the arm script
matched in the decoded text and then re-encoded with a blanket `\n` → `\r\n`, which on a CRLF file writes
`\r\r\n` — a blank line between every line of the module. The mutation would still have parsed, and the
red would have been the corruption's rather than the verb's. The script now normalises to LF, matches
there, refuses a file with mixed endings, and re-encodes to the file's own EOL. It also drops only
`REDIS_URL` and `RATE_LIMIT_REDIS_URL` from the child environment (never `PATH`), so the cluster-direction
case skips instead of joining every red set, and it proves the tree green at rest before the first splice.

## 10. The whole suite

The tier's own two legs are in §8. The whole API suite was run on the SQLite engine with the limiter's
store absent, which is the configuration `scripts/check.sh` runs:

```bash
cd apps/api && ../../.venv/Scripts/python.exe -m pytest --junitxml=full2.xml
```

## 11. A behaviour change, disclosed rather than buried

**The limiter answers before routing and before body validation.** A throttled door now returns
`429 rate_limited` where FastAPI previously returned `422 validation_error` for a malformed body, because
the request never reaches the validator. That is the intended order — a refusal that costs one dict
lookup and stops short of the cache, the database and every provider — but it is a change a client can
observe, and it changed the project's own probe:

* **S1** (every secured door refuses an unauthenticated caller) knocks 239 doors as fast as it can, so
  it now throttles *itself* on the `upload` policy. It waits out a `429` it caused and re-knocks, and
  publishes the count: run K read **3 throttled knocks waited out**, `retry_after: 10`, policy
  `"upload";q=8;w=1`, on `POST /video/probe/link-player`, `DELETE /video/probe/share` and
  `POST /video/probe/share`. A probe that counted those as deviations would report a security failure
  caused by its own enthusiasm.
* **S6** (refusals are one coded shape) posted malformed JSON to a door the anonymous caller may not
  call, so it read the throttle rather than the validator. It now posts to `POST /api/v1/boards` *as the
  registered account*, and reads `422 validation_error` with exactly `loc`/`msg`/`type`.

The first run of the changed probe against the changed API read **8 passed, 2 failed** — those two. The
run recorded as current read **10 passed, 0 failed, 0 server errors in 44.51 s**.

**S5's numbers moved because the algorithm did.** Ten `200`s then `429` at the eleventh login. The
ceiling that refused it is the door's own — `limit(request, 10, 300, scope="login")` in
`apps/api/app/api/v1/auth.py:87`, a `Policy("login", capacity=10, refill_per_second=10/300)` — not the
middleware's `auth` burst of 12. The probe gates `first_429 > 1` rather than a fixed index, because a
bucket refills continuously and the index depends on elapsed time. What changed is the retry:
**`Retry-After: 22`**, the seconds until one token exists at 0.0333/s, where the fixed window's runs read
**`297`**, the seconds to window rollover.

Run K's full record is in [SECURITY_PROBE_REPORT.md](SECURITY_PROBE_REPORT.md): contract SHA-256
`03fb360b86da20886c4e0066ac381b1ec02b13e9e9857aa089d41bb6699873ff`, census **239 secured / 55 public /
102 private GET**, **239 knocked, 239 answered 401, 0 deviations**.

## 12. What this unit does not claim

* **No load figure for the limiter itself.** The paired load envelope (84.34 req/s live against 39.86
  degraded) measures the *response cache*, not this tier. The pre-filter's amplification is argued from
  its construction and counted by `short_circuited`; it has not been measured under a flood on a
  dedicated host, and the shared host this project measures on would not produce a trustworthy number.
* **`workers × capacity` when the store is absent.** That is what a process-local bucket means, and it
  is why the scope is stamped on every answer rather than left to an operator's assumption. A
  deployment that needs a cluster-wide ceiling must give the limiter a store.
* **The store's own failure modes are bounded, not eliminated.** `RedisLimiter` falls back to the local
  tier on a script error and counts it (`cluster_failures`, `cluster_fallback_answers`); a store that
  answers *slowly* rather than not at all is bounded by the 0.5 s socket timeout, not by a circuit
  breaker. There is no breaker.
* **No third-party penetration test.** Unchanged from M12's own disclosure.
## 13. The edge tier: the same bucket behind the last door (2026-11-12)

The unit above prices requests inside the Python core. The gateway in `services/edge` is the *other* door
— every caller reaches the product through it in the `plane` profile — and until this slice it held its
own `LinkedHashMap` bucket per process. Two ceilings, two identities: a caller refused by the core was
admitted by the edge in the same second, and a caller that spread its requests across gateway replicas
got `replicas × limit`, which is what a caller being refused tries next.

**What was built.**

* `RedisBucketStore` — the same Lua script the core runs, byte for byte (`HMGET tokens ts` → refill from
  `redis.call('TIME')` → `HSET` → `PEXPIRE`), executed through `ReactiveStringRedisTemplate` so the
  gateway's event loop is never parked on a round trip. The bean is `@ConditionalOnProperty`
  (`edge.rate-limit.distributed`), off by default.
* `DistributedRateLimitFilter` (order `HIGHEST_PRECEDENCE + 5`) — takes a token, writes the same seven
  budget headers, and stamps the exchange with `DECIDED_BY`; the existing `RateLimitFilter` (`+10`) sees
  the stamp and steps aside. One request is judged once, so the published ceiling is the real one.
* `CallerKey` — the same three identity branches as `app/core/rate_policy.py`, in Java: credential digest
  (`acct:`), then a forwarded address only from a configured trusted proxy (`fwd:`, left-most entry),
  then the socket's peer (`ip:`). The local filter now uses it too, so a whole office behind the web
  proxy no longer shares one budget.
* Degradation is explicit: a store that errors, exceeds the 250 ms budget, returns a malformed reply or
  is not configured at all resolves to the local bucket, and the answer says
  `X-RateLimit-Scope: process` instead of `cluster`.

**What was measured.**

* `mvn -B -pl edge -am test`: **55 tests green**, including 8 new filter cases (allowed, refused, store
  error, store timeout, no store, disabled, malformed reply, refusal body) and 6 identity cases
  (credential wins, left-most forwarded entry, untrusted peer ignored, CIDR matching, bare address, no
  peer).
* Live, with the project's own Redis and the running core: `burst=5`, `requests-per-second=1`, eight
  requests through `:18085/api/v1/healthz` answered **200 ×7** — `X-RateLimit-Remaining` reading
  4, 3, 3, 2, 1, 0, 0 (one token refilled mid-burst) — then **429** with `Retry-After: 1`. Every answer
  carried `X-RateLimit-Scope: cluster`. `/edge/limits` read
  `{"distributed":true,"distributedChecks":8,"distributedDegradations":0}`, and the bucket was readable in
  the store at `football_os:edge:rate:ip:127.0.0.1`.

**One defect found while wiring it.** An empty `spring.data.redis.host` is not "no store" to Spring Boot:
`PropertiesRedisConnectionDetails` asserts a non-empty host and the whole application context fails to
start (35 test classes red). The fix is to omit the block entirely and let a deployment name the host
through relaxed binding (`SPRING_DATA_REDIS_HOST`), with the absence documented as a supported state.

**What this does not claim.** The gateway and the core keep two copies of the identity rule rather than a
shared library; the rule is twelve lines and a third language in the build would cost more than it saves,
but the two copies must be changed together and `CallerKeyTest`/`test_rate_limit.py` are what hold them.
No load figure is claimed for the edge tier either — the store call is bounded at 250 ms, and a
saturated gateway is a measurement for a dedicated host, not this one.
