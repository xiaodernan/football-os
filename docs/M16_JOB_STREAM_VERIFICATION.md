# M16 — the job queue's transport: Redis Streams under the database state machine

ADR-006 built a job state machine and left one sentence open. This milestone keeps the promise without
trading the state machine for a second source of truth. Everything below was run on 2026-11-12 against the
project's own Redis (`127.0.0.1:63790`, password from `.env`), a migrated SQLite database
(`var/m15-real.db`) and a real uvicorn API on `127.0.0.1:8731`.

## 1. The split, stated once

| question | answered by | why not the other |
|---|---|---|
| is this job queued / running / done / failed? | the `jobs` row | a stream has no transaction with the business write that created the work |
| who owns it right now, and until when? | `lease_expires_at` on the row | Redis has no lease primitive that survives a flush |
| has anybody been told there is work? | the stream message | polling a table can only *discover* work, never *wake* a worker |

The transport is therefore allowed to be lossy and duplicative, and the claim is not. A lost hint is a late
job; a duplicated hint is one `UPDATE` that returns `rowcount = 0`.

## 2. What was built

* `app/core/job_stream.py` — `JobStream`: `publish` (XADD, `MAXLEN ~ 20000`), `read` (XREADGROUP, group
  created at `$`), `reclaim` (XAUTOCLAIM, 60 s grace), `deliveries` (XPENDING range), `ack`, `to_dead`,
  `leave` (XGROUP DELCONSUMER on a clean exit), `snapshot`. Every method degrades to a no-op instead of
  raising; `JobStream(None)` is a supported configuration.
* `app/services/jobs.py` — `claim_by_id` (the same compare-and-set, by id), `run_claimed` (one author for the
  handler contract, two callers), `requeue_expired` (the lease sweep ADR-006 deferred).
* `app/services/job_broker.py` — `publish_queued`, `drain_stream`, `tick` (stream first, poll fallback).
* `app/services/job_handlers.py` — the registry, with `system.echo` as the queue's own smoke test (it needs
  no fixture, so "is the queue alive?" is answerable without also asking "is that asset still there?").
* `app/worker.py` — `python -m app.worker`: consumer name, poll fallback, periodic sweep, SIGINT/SIGTERM
  finish the current job, `--once` / `--max-jobs` for bounded runs.
* `POST /jobs` publishes after the commit; `GET /metrics/jobs-stream` publishes the transport's numbers to
  an admin.

## 3. What was measured

**Tests.** `tests/test_job_broker.py` — 26 cases, 8 of them live-Redis integration cases:

```
..........................   26 passed   (REDIS_URL=redis://:football@127.0.0.1:63790/0)
```

They cover: a publish with no store is a no-op rather than an error; a refused publish is counted and never
raised; a hint carries id and type; drain with no store reports nothing; a raising handler leaves the row
FAILED **and the message acknowledged**; a duplicated hint runs the job once; a hint naming a missing row is
acknowledged; a message past `MAX_DELIVERIES` lands in the dead-letter stream with its reason; a claim by id
is a compare-and-set; the sweep revives a lost lease without spending an attempt; the sweep fails a job out
of attempts; the registry can run the types the doors create. Live: round-trip, group-at-`$` does not replay
history, reclaim from a dead consumer (delivery count reads 2), dead-letter clears the pending list,
end-to-end drain, clean-exit deregistration, and an unacked consumer is **not** deregistered.

**Live, through the API and a real worker.**

| step | observed |
|---|---|
| `POST /jobs {"type":"system.echo","payload":{"probe":"m16","n":7}}` | `QUEUED`, id `job_iforjX53U4vwchSh`; `XLEN football_os:jobs` = 1 |
| `python -m app.worker --once` | `worker: stopped after 1 job(s) over 2 tick(s)`, types `system.echo,video.analyse` |
| `GET /jobs/{id}` | `COMPLETED`, result `{"echo":{"probe":"m16","n":7},"job_id":…,"attempts":1}`, `XPENDING` = 0 |
| second job, worker with `JOB_STREAM_REDIS_URL` pointing at a dead port | `job stream unavailable, the poll loop carries the queue: TimeoutError`; job still `COMPLETED` |
| healthy worker afterwards | consumed the stale hint, executed 0 jobs, `pending` 0 — the message was answered, not re-run |

`GET /metrics/jobs-stream` (admin) after the run:

```json
{"available":true,"published":2,"stream_length":2,"dead_length":0,
 "pending":0,"consumers":2,"undelivered":0,"publish_failures":0}
```

`stream_length` 2 with `pending` 0 is the expected shape: `XACK` removes a message from the pending list, not
from the stream — the window is bounded by `MAXLEN`, not by acknowledgement.

## 4. Two defects found while wiring it

* **A counter shadowed a method.** `JobStream.read` was both the consumer method and the counter of messages
  taken, so `self.read = 0` in `__init__` turned every later call into `'int' object is not callable`. Three
  tests caught it; the counter is now `taken`, and the reason is written where it is set.
* **The delivery count always read zero.** redis-py 8 removed the range form of `XPENDING`; `xpending` is now
  the summary and the range form is `xpending_range`, whose bounds are *exclusive*. The old call raised
  `TypeError` straight into the `except`, so the poison-message rule could never fire. `deliveries()` now
  asks `xpending_range` with a one-millisecond window around the id and reads `times_delivered`.
* **`XGROUP DELCONSUMER` needed a guard, and the absence of a name is the safe case.** The pending summary
  lists only consumers *holding* messages, so a name missing from it has nothing outstanding; reading that
  absence as "cannot tell" left every clean exit registered forever. The first version of `leave()` did
  exactly that and the test caught it.

## 5. What this does not claim

* No throughput figure. The loop is one process, one message at a time, by design; a number taken on this
  host with a SQLite file would describe the host, not the design.
* The stream is not partitioned by job type, so a slow type delays a fast one behind it. That is a choice
  (§ADR-008), not a measurement.
* `MAXLEN ~ 20000` makes the stream a window, not a record. A consumer that is down for 20 000 jobs comes
  back to a stream that no longer mentions the oldest ones — those rows are still `QUEUED` and the poll
  fallback still finds them, which is the property that makes the cap safe.
* No age is exported to Prometheus. `/metrics/prometheus` never reads the transport, so §6's three figures
  are answerable by an operator opening a door, not by an alert rule. Making them alertable is the next
  unit's work, not this one's claim.

## 6. The two blind spots closed (2026-11-23)

§3 published four counts and one of them — `dead_length` — was a number nobody could open. An operator
could see that twelve hints were waiting but not whether they had arrived in the last second or been
ignored for an hour, and could see that two jobs were dead but not why. Both gaps are now closed on the
same door, and both are measured below against the project's own Redis (`127.0.0.1:63790`, db 9).

**The ages come from the server's clock and the server's ids.** `XADD` ids are minted by Redis, and the
`now` side of every subtraction is `TIME` on the same connection, so an age is one clock's arithmetic
rather than two processes agreeing — the same reasoning that makes M15 read `TIME` inside its Lua script.
Three figures:

| key | question it answers | how it is read |
|---|---|---|
| `oldest_undelivered_seconds` | since when has a hint existed that nobody has been given? ("the worker is not running") | `XRANGE` from one sequence past the group's `last-delivered-id`, `count=1` |
| `oldest_pending_seconds` | how old is the oldest unfinished hint? (what a caller feels as latency) | the first row of `XPENDING`, which is already in id order |
| `pending_idle_seconds` | since when has the quietest pending consumer said nothing? ("alive and stuck in a handler") | the maximum `time_since_delivered` in the window |

The third is a different number from the second by construction: a hint can be old and freshly delivered
at the same time, and a queue where those two figures agree is a queue where nothing has been retried.

**`None` and `0` are different answers.** `_UNKNOWN_AGES` is merged into every snapshot, including
`JobStream(None)`'s, so the three ages and the `pending_sampled` window are keys a reader can always
index. A degraded store answers `null`, never `0` — an operator dashboard that reads "0 s" during an
outage is a dashboard that says the queue is young when the truth is unreadable. The counts are *not* all
present without a store, and the run below is what stopped that being written up as a symmetry:
`available: false` in the same payload is the discriminator, so an absent `pending` reads as "no Redis"
and never as "an idle queue".

**The dead-letter pile has a door.** `to_dead` has written a `reason` onto every poison message since the
transport landed, and nothing in the product read it until
`GET /api/v1/metrics/jobs-stream/dead` (admin standing, like every other door on the router). Newest
first, `limit` bounded 1…500, and `returned` published next to `asked` so a reader can tell "there is one
dead letter" from "you asked for one". The total is `/jobs-stream`'s `dead_length` and is deliberately not
repeated here: two doors reading the same `XLEN` can disagree.

**A tick could overspend the budget it was given.** The runbook names `--max-jobs` the ceiling for a cron
sweep, but the loop only checked it *between* ticks, and one tick drains `limit` (8) hinted jobs plus
`poll_fallback` (4) board rows: `--max-jobs 1` was answerable with twelve executed. `TICK_LIMIT` and
`TICK_POLL_FALLBACK` are now named constants in `job_broker`, and the worker sizes each tick by
`min(default, what the caller has left)`.

### What was measured

109 cases in the queue's own lane (`test_job_stream_observability.py`, `test_job_broker.py`,
`test_jobs.py`, `test_job_runner.py`, `test_metrics.py`, `test_response_cache.py`) — §3's 26 is the
population the transport landed with, this is the population it has now:

```
109 tests, 0 failures, 0 errors, 9 skipped   70.6 s   (no REDIS_URL: the live cases skip, the poll loop carries)
109 tests, 0 failures, 0 errors, 0 skipped   74.2 s   (REDIS_URL=redis://:football@127.0.0.1:63790/9)
```

`bash scripts/lint.sh` reports "All checks passed!" and `python -m mypy app` reports no issues in 230
source files. The live evidence, taken from a three-hint queue with one consumer:

```json
{"available":true,"published":3,"stream_length":3,"taken":1,"pending":1,"consumers":1,"undelivered":2,
 "dead_length":0,"oldest_undelivered_seconds":1.407,"oldest_pending_seconds":1.408,
 "pending_idle_seconds":1.407,"pending_sampled":1}
```

The same store after the one pending hint was acknowledged and two messages were dead-lettered:

```json
{"pending":0,"undelivered":0,"dead_length":2,
 "oldest_undelivered_seconds":null,"oldest_pending_seconds":null,"pending_idle_seconds":null}
```

`JobStream(None).snapshot()` publishes those same four keys as `null` with `available: false`, and the
dead-letter door reads the pile back with the reason `to_dead` wrote and how long it has been sitting:

```json
[{"id":"1795367045315-0","job_id":"job_probe_2","job_type":"system.echo","deliveries":1,
  "reason":"handler raised: TimeoutError","original_id":"1795367043901-0","dead_for_seconds":1.203},
 {"id":"1795367045313-0","job_id":"job_probe_1","job_type":"system.echo","deliveries":1,
  "reason":"delivered 6 times","original_id":"1795367043899-0","dead_for_seconds":1.205}]
```

`original_id` is the handle back to the entry in the main stream, which is what turns "this job died" into
"this job died, here is the hint that carried it".

**The security witness for the new door.** Probe run A-12 (recorded in `docs/SECURITY_PROBE_REPORT.md` §2)
pressed the contract at SHA-256 `2e1c6394…` with `GET /api/v1/metrics/jobs-stream/dead` in its census
population: **246 knocked, 246 × 401**, 0 server errors, 4.56 s. The door's own refusal is the evidence
that its standing is the standing it documents.

### A third thing the run found

The six files above were run as one command and six cases went red — all of them in
`test_job_runner.py`, whose whole contract is that `claim(limit=1)` returns *the row this case just made*.
The cause was not in that file: `test_jobs.py` registers accounts through `POST /auth/register` and leaves
every row those doors wrote behind, and the test database is shared, so a `QUEUED` job from four files
away was the next thing the claim took. CI happens to collect `test_job_runner.py` first and never sees
it, which is the same class of latent order-dependence §4's three defects were.

`test_jobs.py` now deletes what it registers, in an autouse teardown like its three sibling modules, and
`TestNothingSurvivesItsCase` is the witness: collected last, it counts the accounts this file registered
and finds none of them still holding rows. Its arm is the fixture's absence — with the teardown
de-autoused the case fails reading "11 account(s) and 22 job row(s) outlived the case that made them",
and the lane returns to 109 green when it goes back.

