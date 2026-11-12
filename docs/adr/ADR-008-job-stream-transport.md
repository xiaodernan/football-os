# ADR-008 — Redis Streams as the wake-up under the database queue, not as the queue

- Status: Accepted (M16, 2026-11-12) · Relates to: ADR-006, ADR-007, §47, §75
- **Context**: ADR-006 chose a database-backed job state machine and closed with one promise: *"the same
  repository interface can be driven by Redis/Celery later without touching call sites."* Until this
  slice the product had only the first half. `drain_one` claimed the oldest `QUEUED` row, so a job waited
  for the poll interval of whichever process happened to be draining — the API itself, in practice, with
  a request thread paying for a video analysis.
- **Problem**: Latency and placement. A queue whose only read path is a timer cannot promise "started in a
  second", and a queue drained by the web process cannot promise "the API stays responsive". A broker
  that replaces the database as the source of truth would trade a correct state machine for a
  second one — and would have to re-implement leases, attempts and cancellation in a system that has no
  transactions across the two stores.
- **Options**: (a) poll faster (a timer is not a wake-up; at 100 ms it is a load generator); (b) Celery +
  Redis as the queue (replaces the state machine, needs a second cancellation path, and the spec's line is
  explicitly "no hosted broker"); (c) keep the database as the truth and add Redis Streams as a *transport*
  that says "something was queued, look now".
- **Decision**: (c). `app/core/job_stream.py` publishes one message per committed `QUEUED` row and consumes
  through one consumer group; `app/services/job_broker.py` is the only place the two halves meet. The claim
  stays the conditional `UPDATE … WHERE status='QUEUED'` ADR-006 wrote, now also available by id
  (`claim_by_id`), so the guarantee is unchanged: **at-least-once delivery over exactly-once execution**.
  A lost hint is a late job (the poll loop still runs); a duplicated hint is one claim that returns `None`.
- **Consequences**:
  - The API no longer runs handlers. `python -m app.worker` is a separate process with a consumer name, a
    poll fallback, a periodic lease sweep and a clean-exit deregistration.
  - A message that will not settle is moved to `football_os:jobs:dead` with a reason **before** it is
    acknowledged, so a crash between the two duplicates the dead letter rather than losing the reason.
  - `XAUTOCLAIM` is the crash recovery: a consumer killed mid-handler leaves its message pending, and
    another consumer takes it after `PENDING_GRACE_MS` (60 s). `MAX_DELIVERIES` (5) is the transport's own
    bound, separate from the job's `max_attempts` — one is "the message never settled", the other is "the
    work failed".
  - `requeue_expired` is the sweep ADR-006 left to "the operator": `RUNNING` rows with a past lease return
    to `QUEUED` without spending another attempt, unless `attempts == max_attempts`, in which case the row
    is failed with the reason. A poison job stops being claimable instead of circulating.
  - Two stores now hold queue state: the row is authoritative, the stream is a bounded window
    (`MAXLEN ~ 20000`). Redis may be absent — `JobStream(None)` is a supported configuration and the poll
    loop carries the queue; the metrics door reports `available: false` rather than pretending.
  - The stream is not sharded by job type. One stream means one pending list, one lag number and one thing
    to watch; parallelism this product does not need yet is not worth the observability it would cost.
