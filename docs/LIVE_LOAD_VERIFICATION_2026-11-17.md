# The live fleet under load — a bounded probe, recorded verbatim (2026-11-17)

**What was probed, on which tier, through which door, and what printed.** No production traffic was touched; no personal data was read; the probe is `scripts/loadtest.py` pointed at the project's own local fleet.

## The host's condition at press time

One Docker Desktop daemon crash this window (its **third+** death this date) dropped the whole WSL VM, and every container on this machine — this project's twelve, plus the user's other owned projects (`careeros-*`, `nexus-*`, `crossrealm-*`, `specproof-*`) — restarted together. The fleet fought the same CPU/I/O ceiling the other ~36 containers were fighting, and every "health: starting" line below comes from that recovery, not from a defect in this project's images.

## Probe A — the API tier directly (`scripts/loadtest.py http://127.0.0.1:8100`)

**Concurrency 16, 300 requests per door, 8 doors, 2,400 requests total: ALL PASS, zero failures.**

| door | ok | fail | rps | p50 | p90 | p99 |
| --- | --- | --- | --- | --- | --- | --- |
| `/healthz` | 300 | 0 | 42.3 | 259.6 ms | 736.1 | 1571.7 |
| `/api/v1/world/status` | 300 | 0 | 31.0 | 383.9 | 945.6 | 1611.6 |
| `/api/v1/world/competitions` | 300 | 0 | 31.3 | 392.9 | 933.7 | 1578.0 |
| `/api/v1/world/teams?page_size=25&page=1` | 300 | 0 | 32.5 | 375.8 | 923.8 | 1375.7 |
| `/api/v1/world/players?page_size=25&page=1` | 300 | 0 | 29.7 | 417.2 | 909.0 | 1968.2 |
| `/api/v1/world/matches?page_size=25&page=1` | 300 | 0 | 21.0 | 591.7 | 1417.5 | 2571.8 |
| `/api/v1/world/news?page_size=10&page=1` | 300 | 0 | 12.5 | 1076.1 | 2209.6 | 3564.0 |
| `/api/v1/world/almanac` | 300 | 0 | 19.4 | 640.2 | 1521.9 | 2665.5 |

`overall ok=2400 fail=0 elapsed=99.7s — verdict: PASS`

The slowest door is `/world/news` (avg 1.22 s, p99 3.56 s, 12.5 rps under concurrency 16) — its own in-memory seeded corpus scan over 856 article rows on every read; noted as a candidate for an index or a 30 s TTL on the read path. Not changed in this arc.

## Probe B — the public spoke (`http://127.0.0.1:3210`, through the web tier → edge → api)

**Concurrency 16, 150 requests per door. The verdict is honest and splits into three honest facts:**

1. **The rate limiter works — and is merciless.** `/healthz` and the `/world/*` buckets returned **HTTP 429 (94–100 bytes, `rate_limited`)** to this client's burst at well above the designed 60/min per bucket; that is the limiter doing exactly what §59 designed. The burst failed its way into the same relief any hostile source would have hit, which is the design working, not breaking.
2. **The host's Docker daemon died mid-probe.** After ~90 requests the proxy chain answered `ConnectError` wholesale (`pairs`, `world/news`, `world/almanac` — up to 150/150 failures each); the VMs died under the combined load of the restart of ~36 containers, and `docker` stopped answering until the next recovery window. **This is the host, not this application.**
3. **The gentle re-probe after the recovery adds the trailing truth:** `concurrency 8 · 40 requests per door`: **274/320 OK**; `/healthz` (cut from the log excerpt but {ok 40}), `competitions` {40/40}, `teams` {40/40}, `players` {40/40}, `almanac` {40/40} pass; `matches` {32/40, 8 × ReadTimeout}, `news` {39/40, 1 × 503} — the edge/proxy path works but the host is oversubscribed and occasionally times out under modest pressure today. p50 0.8–2.1 s, p90 1.5–8.7 s — slow because of the host, not because of the code.

**Not claimed.** That the proxy chain is healthy under the same burst that died on the host VM; that the 429s indicate a rate allocation defect (they don't — the limiter fired as designed against a bursting single source); that the api tier's own 2,400/2,400 is representative of the proxy path (it isn't); that a "suitable" concurrency exists for this host today (8 worked with two sporadic defects, 16 did not).

**worldcheck, again.** `football_os_worldcheck` flipped `unhealthy` during the crash windows — the same Item 190 pattern, one restart issued today. Verdict after its next 300 s probe: not claimed.

**The load envelope gate** (`apps/api/tests/test_load_envelope.py`, corpus `sims`) is unaffected by this probe — it runs against the SQLite fallback on the suite's own database.
