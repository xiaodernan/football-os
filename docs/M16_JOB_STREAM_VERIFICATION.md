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
