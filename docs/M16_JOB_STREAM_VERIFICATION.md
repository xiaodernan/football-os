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
* ~~No age is exported to Prometheus.~~ This stood for eleven days and §7 closes it: the scrape now reads
  the transport, so the three ages are answerable by an alert rule and not only by an operator opening a
  door. Everything §7 claims was measured after this line was written.

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

## 7. The queue becomes alertable (2026-11-23)

§6 gave an operator seven counts and three ages — every one of them readable by opening a door. A door is
what someone looks at when they already suspect something. The scrape is what says so first, and until now
the scrape said nothing about the queue at all (§5's retired bullet). This unit moves §6's payload into
exposition form and adds nothing to it: no new read, no new number, no new dependency.

**Sixteen families, in the three groups that already existed in the payload.**
`football_os_jobs_available` is the discriminator; the six `…_published/taken/acknowledged/reclaimed/
dead_lettered/publish_failures_total` are this process's own counters; `…_stream_length/_pending/
_undelivered/_consumers/_dead` and `…_pending_sample_size` are the store's; and the three ages
(`…_oldest_undelivered_seconds`, `…_oldest_pending_seconds`, `…_pending_idle_seconds`) are §6's, unchanged.
`app/services/prometheus_export.py` names the mapping in three tuples so the door's key, the metric's name
and the sentence that tells an operator how to read it travel on one line.

**The rule that shaped the block: an exposition sample cannot be null.** The door answers `null` for an age
the store would not give up, and there were exactly two renderings available here — print `0`, or print no
series. Printing `0` is the one that lies: `football_os_jobs_oldest_pending_seconds 0` in a scrape taken
during a Redis outage is an alert that stays silent about the oldest unfinished job in the deployment. So
the series is *absent*, following the rule `football_os_request_duration_p95_ms` has always followed for a
window with no sample, and `football_os_jobs_available` is published on every scrape to make the absence
readable as "the store did not answer" rather than "nothing is waiting". `_sample()` is the two-line helper
that carries that decision, and it is the only place the nullability is decided.

**Still zero labels.** `snapshot()` carries two strings — `stream` and `group`, i.e. `football_os:jobs` —
and neither reaches the text: a colon is legal in a metric name and would be a cardinality decision in a
label, and this door's safety argument is that it has no label to grow. The contract test asserts the exact
set of emitted names, which is what makes a new string-valued family impossible rather than discouraged.

### What was measured

`tests/test_prometheus_export.py` 5 → 8 cases. §6's queue lane with that module added, both legs rerun over
this unit's source:

```
117 tests, 0 failures, 0 errors, 9 skipped   81.0 s   (no REDIS_URL)
117 tests, 0 failures, 0 errors, 0 skipped   80.8 s   (REDIS_URL=redis://:football@127.0.0.1:63790/9)
```

The live leg is the one that exercises the block on the request thread: the door now performs the
transport's five-to-seven round trips inside a scrape. No timing figure is claimed for that, for §3's reason
— a number taken on this host with a SQLite file describes the host. What was checked instead is that the
leg is green with a store present, so the scrape path is not only the fixture path. db 9 was flushed of the
keys both legs made.

The live evidence for the block itself, run against the project's own Redis
(`127.0.0.1:63790`, db 9) on a stream that still held §6's probe residue — a 27-entry window and a group
18 minutes behind it, which is a more useful witness than a clean fixture because it makes §6's claim about
the two ages visible rather than asserted:

```
-- GET /metrics/jobs-stream answers this --
{'available': True, 'published': 3, 'taken': 1, 'acknowledged': 0, 'reclaimed': 0, 'dead_lettered': 0,
 'publish_failures': 0, 'stream_length': 27, 'dead_length': 0, 'pending': 1, 'undelivered': 26,
 'consumers': 3, 'oldest_undelivered_seconds': 1102.347, 'oldest_pending_seconds': 1102.98,
 'pending_idle_seconds': 0.906, 'pending_sampled': 1}

-- the same process, scraped --
football_os_jobs_available 1
football_os_jobs_published_total 3
football_os_jobs_taken_total 1
football_os_jobs_acknowledged_total 0
football_os_jobs_reclaimed_total 0
football_os_jobs_dead_lettered_total 0
football_os_jobs_publish_failures_total 0
football_os_jobs_stream_length 27
football_os_jobs_pending 1
football_os_jobs_undelivered 26
football_os_jobs_consumers 3
football_os_jobs_dead 0
football_os_jobs_pending_sample_size 1
football_os_jobs_oldest_undelivered_seconds 1102.347
football_os_jobs_oldest_pending_seconds 1102.98
football_os_jobs_pending_idle_seconds 0.906

-- and the same exporter on a process with no store --
football_os_jobs_available 0
football_os_jobs_published_total 0
football_os_jobs_taken_total 0
football_os_jobs_acknowledged_total 0
football_os_jobs_reclaimed_total 0
football_os_jobs_dead_lettered_total 0
football_os_jobs_publish_failures_total 0
football_os_jobs_pending_sample_size 0
```

`oldest_pending_seconds` 1102.98 beside `pending_idle_seconds` 0.906 is the two clocks §6 separates, read
off one queue: the work is eighteen minutes old, and the consumer holding it has been silent for a second.
`undelivered` 26 with `consumers` 3 is the other pair the block exists to make alertable — three workers are
registered and 1 102 seconds of hints are sitting untouched, which is a group that has fallen behind the
stream, not a fleet that is idle. The storeless rendering keeps the six counters and the sample size and
loses every store-shaped family, which is §6's `None`-is-not-`0` rule with the `0` taken out.

**The scrape door kept its standing under a live press.** Probe run A-13 (`docs/SECURITY_PROBE_REPORT.md` §2)
walked the committed contract at SHA-256 `7f40714e…c3668`: no door moved — only this door's description did —
and the census stayed **246 secured / 96 public / 106 private `GET` paths**. A fresh uvicorn on
`127.0.0.1:61248`, scratch `.scratch/probe-r.db`, `ENV=development`, the project's own 3210 CORS pair and no
`REDIS_URL` answered **10 passed / 0 failed / 0 server errors, 3.67 s**; all 246 secured doors refused the
anonymous caller with 401, 0 deviations and 0 throttled knocks. That is the standing witness for a scrape
that now reads the broker, not a latency claim for the read.

**Seven arms, one control.** Each was spliced into the shipped source, the module re-run, and the bytes
restored and SHA-checked:

| arm | mechanism removed | killed |
|---|---|---|
| A1 | `_sample` stops honouring `None` | the degraded-store case, the idle-vs-unreadable case |
| A2 | an unknown age renders as `0` | the same two, from the other direction |
| A3 | the door stops passing `job_stream=` | the door case — the only rule that can tell an exporter that works from a scrape that carries it |
| A4 | `football_os_jobs_dead` renamed | the name-set case, the mapping case |
| A5 | one process counter dropped | name-set, mapping, degraded-store |
| A6 | the stream's own key name exported as a value | the name-set case (both its `_VALUE` clause and its no-`football_os:jobs` clause) |
| A7 | `football_os_jobs_available` dropped | five of the eight cases |
| C0 | a HELP line reworded | nothing — the control, proving the cases read samples, not prose |

A7 is the widest kill and the reason the gauge is first in the block: remove the discriminator and every
rule about absence stops being checkable.

### Three things the unit found on the way

* **`football_os_jobs_pending` is a prefix of two other family names.** The first cut of the absence
  assertions was `"football_os_jobs_pending" not in body`, which is wrong in both directions — blind to a
  real `football_os_jobs_pending_idle_seconds`, and accusing the exporter of a family it never emitted when
  `football_os_jobs_dead_lettered_total` is on the page and `football_os_jobs_dead` is not. The cases now
  parse the body into name → value with `_samples()` and index that.
* **An arm harness must splice bytes.** Restoring with `Path.write_text` on Windows rewrote every LF in
  `prometheus_export.py` as CRLF, so the SHA check fired on the *first* arm — after the file had been
  mutated. The battery now reads and writes bytes and re-checks the digest after every restore; the
  flip was caught and undone the same day, and it is why the restore assertion belongs inside the arm
  runner rather than in the person running it.
* **`mypy` found a type the tests could not.** `_JOB_GAUGES` was annotated
  `tuple[tuple[str, str, str, str], ...]` while every entry is a triple and every reader unpacks three. The
  eight cases stayed green throughout, because a test can only exercise the shape the loop reads — the
  annotation is the sole place the *declared* width is checked, and it was the thing that was wrong. Both
  errors are the same defect seen twice (`assignment` at the table, `Too many values to unpack` at the
  loop), which is why the annotation is now the same triple as `_JOB_AGES`' and why a wrong arity in either
  table is a compile-time fact rather than a runtime hope.

### What this does not claim

* No alert rule is deployed. `docs/runbooks/service_plane.md` prints the three PromQL expressions the block
  supports, and nothing in the repository evaluates them: there is no Prometheus in the deployment, so the
  rules are unexecuted advice, not a tested pipeline.
* The scrape now costs what `GET /metrics/jobs-stream` costs — five to seven round trips on a healthy
  store, and up to half a second of socket timeout each on a dead one. At a 15 s scrape interval that is
  the same order as the ledger queries the door already runs; a deployment scraping faster than that should
  gate the block behind a longer-interval job, which is not built here.
* `taken`, `acknowledged` and the rest remain per-process, so a fleet's counters are a sum and its ages are
  a maximum over whoever was asked. That is what node-local scrapes produce, and the block says so in the
  same words §2 of this record uses about the door.

