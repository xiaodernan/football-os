# The load envelope

The API's published performance story, in a form a gate can read. The gate is
`apps/api/tests/test_load_envelope.py`: it boots a real uvicorn server (in a thread, against the
test run's own database — the same seeded universe the suite uses, on both the SQLite and the
PostgreSQL leg), then runs `scripts/bench_api --scenario sims` as a subprocess and asserts the
invariants in the JSON block below. The block is the single author of the ceiling figures: the
test parses it from this file, so the prose and the gate cannot drift apart.

## The scenario

`sims` is a task-count career walk, not a duration loop: register accounts, open careers, play a
fixed number of rounds in each, then re-read every career and check its own count. Concurrency is
**across** careers — one worker owns a career at a time and plays its rounds sequentially — because
two concurrent plays of the SAME career are refused by the database layer (measured below), so
racing within a career would measure the refusal, not the engine. The scenario presumes the API
runs with `ENV=test` (the rate limiter bypasses); that is exactly how the gate boots it.

## The envelope

```json
{
  "scenario": "sims",
  "shape": {"accounts": 2, "careers_per_account": 2, "rounds_per_career": 2, "workers": 2},
  "p95_ms_ceiling": 15000,
  "subprocess_seconds_ceiling": 600,
  "measured_2026_10_28": {
    "gate_shape_plays": 8,
    "gate_shape_p95_ms": 1655.61,
    "measure_shape_plays": 36,
    "measure_shape_p50_ms": 923.02,
    "measure_shape_p95_ms": 1745.49,
    "measure_shape_p99_ms": 1774.48,
    "measure_shape_plays_per_second": 3.44
  }
}
```

The gate asserts, for the gate shape (2 accounts × 2 careers × 2 rounds = 8 plays):

* the subprocess exits 0 and its summary says `ok: true`;
* **zero non-2xx play calls** and zero transport failures — every refusal is a defect the run must name;
* every opened career re-reads with exactly `rounds_per_career` played rounds — the engine may not
  drop a round under concurrency, and the refusal-driven serialisation above may not eat one either;
* play p95 ≤ `p95_ms_ceiling`.

The ceiling is deliberately generous: 15000 ms against a locally measured 1655 ms at the gate shape
(~9× headroom), because a threshold a correct tree cannot meet is not a gate. CI's runners are
slower than this machine; a regression that doubles or triples the engine's latency still trips it,
while a slow cold start does not. Throughput is **reported, not gated** — a floor measured on one
machine flakes on a slower one for reasons that are not defects.

## The same-career race, measured

Before this envelope landed, the play door's concurrency story was asserted by nobody. A probe
(`K=2` concurrent `POST /careers/{id}/play` on one fresh career, 10 trials, rounds read back from
the SQLite rows — not from the API's own word) returned:

| Trial outcome | Count |
| --- | --- |
| exactly one 200 and one 409 | 10/10 |
| duplicate round rows | 0/10 |
| `rounds_played` ≠ stored row count | 0/10 |

The loser's 409 carries the code `conflict` — not a domain answer like `no_fixture`. The mechanism:
both requests find the same next fixture available, the second write hits an `IntegrityError`, and
the global handler (apps/api/app/core/errors.py) answers 409 "That record conflicts with existing
data". The database layer serialises the race; the refusal is coarse, but the invariant holds —
a career never double-applies a round, and `rounds_played` never disagrees with the stored rows.
The scenario's worker model (one owner per career) respects this rather than leaning on it.

## The arms: the error path must bite

A gate that cannot go red proves nothing. The test runs two refusal legs against the same live
server and requires `exit 1` with the refusal named:

| Arm | Invocation change | Required verdict |
| --- | --- | --- |
| wrong prefix | `--prefix /api/v9` | exit 1, setup error `careers/options` status 404 |
| career cap | `--careers 6` (cap is 5 per account) | exit 1, setup error `open_career` status 409, code `career_limit` |

Both were exercised by hand on 2026-10-28 before the gate landed; the pipeline's own exit-code
capture (not a pipe's) read both 1s.

## Running it

```bash
# the gate alone (boots its own server on a free port; uses the test run's database)
cd apps/api && python -m pytest tests/test_load_envelope.py -v

# the scenario by hand, against any ENV=test server
python -m scripts.bench_api --scenario sims --base-url http://127.0.0.1:8731 \
  --accounts 2 --careers 2 --rounds 2 --sim-workers 2 --output sims.json

# the duration benchmark is unchanged (M12)
python -m scripts.bench_api --concurrency 10 --duration 30 --endpoint /api/v1/healthz
```
