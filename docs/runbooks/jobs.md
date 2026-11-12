# Runbook — the async-job queue

**When:** operating `/api/v1/jobs`, debugging a job that will not finish, or wiring a new worker process.
Spec §47, ADR-006. The `/jobs` doors own the *vocabulary* and the *read side*; nothing ran the queue until
`scripts/drain_jobs.py` landed with it.

## 1. What a job is

A job is one account's background work — a video analysis, a simulation batch, a knowledge re-ingest. ADR-006's
state vocabulary is `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED`; `RETRYING` is named by the ADR and not
implemented here, deliberately: a retry loop without a policy is a poison loop, and this runner fails loudly
instead of guessing one.

## 2. The claim algorithm — and why it is not `SKIP LOCKED`

The queue must be drainable on both engines this project runs on, and SQLite has no `SKIP LOCKED` and no
`FOR UPDATE`. The claim is a conditional update instead:

```
UPDATE jobs SET status='RUNNING', attempts=attempts+1, lease_expires_at=:now+:lease, updated_at=:now
WHERE id = :id AND status='QUEUED'
```

The rowcount is the verdict. Two workers racing one row produce exactly one winner and zero double claimants —
the one row they raced goes to whichever update landed first, and the other moves to the next candidate. A
`SKIP LOCKED` statement would have been one line shorter and one engine poorer; a queue that only works on
Postgres is a queue you cannot gate in the SQLite leg.

## 3. Running the worker

```bash
python scripts/drain_jobs.py                     # drain everything queued right now, exit
python scripts/drain_jobs.py --loop --interval=2 # poll forever, 2s between passes
python scripts/drain_jobs.py --handlers app.services.video.drain:drain_analyse   # one production handler
```

**A production handler ships registered by name**: `--handlers app.services.video.drain:drain_analyse` executes
the same `probe → extract_frames → vision → writes` sequence the synchronous `/video/{ident}/analyse` door runs,
against a claimed job row instead of the request lifecycle. The `tests/test_video_drain.py` suite walks that exact
path on a clip the test builds: queued → drained → `COMPLETED` with frames and events.

A handler is `module:attribute`; the attribute must be callable and take exactly one argument — the claimed
`Job`. The registry is explicit, at the process edge, never a guessed import. Running with no `--handlers` and
an empty board drains 0 jobs and exits 0 — which is the correct answer, not a hang.

## 4. The empty-board contract — no silent holds, ever

With no handler registered for a job's `type`, `drain_one` ends the job `FAILED` with
`no handler registered for job type '…'` in the error. With a handler that raises, the job ends `FAILED` with
`HandlerName: message`, bounded to 2000 characters, `completed_at` set. Nothing is ever left in `RUNNING` unless
a handler is in-flight right now; nothing is ever quietly re-queued; nothing is deleted.

## 5. The operator's checklist when a job will not finish

1. Read the job: `GET /api/v1/jobs/{job_id}` — status, attempts, error, lease (`lease_expires_at`).
2. `RUNNING` with an expired lease means a worker died mid-job. This slice **does not** re-queue expired leases —
   that is the operator's judgment call, not the drain's, or one wedged handler poisons the board.
3. `FAILED` with `no handler registered` means the producer wrote a `type` nothing claims. Register a handler on
   the worker invocation, or agree with the producer on the vocabulary.
4. `FAILED` with a handler exception is the handler's own text — fix the handler; the queue is not at fault.

## 6. What this queue does not claim

No priority, no deadline, no dependency DAG, no heartbeat-renewed leases, no dead-letter table — those are
future arcs, each of which must land with a walk proving it. The queue earns its keep on the ADR-006 vocabulary
and the claim algorithm, verified by `tests/test_job_runner.py` (6 cases, both engines).
