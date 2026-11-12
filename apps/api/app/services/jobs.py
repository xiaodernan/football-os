"""The job runner: one Postgres-and-SQLite portable claim-and-drain loop (spec §47, ADR-006).

A message queue, and deliberately not a hosted one. The spec's line is: no Kafka, no Redis queue, the
job runner remains Postgres-backed — this module is that runner, and it is what the `/jobs` doors have
been waiting for since they landed with `create` writing a `QUEUED` row nothing would ever touch.

The claim algorithm is a compare-and-set, not a `SKIP LOCKED` hint: `UPDATE jobs SET status='RUNNING' …
WHERE id = :id AND status='QUEUED'`, and the rowcount is the verdict. Two workers racing the same row
cannot both win — one sees rowcount 1 and owns the lease; the other sees 0 and moves to the next
candidate. `SKIP LOCKED` would have been one statement; it does not exist on SQLite, and a queue whose
claim path only works on one of our two engines is a queue we cannot gate. The conditional update is the
same guarantee expressed as the one thing both engines honour: row-level update atomicity.

Three things are refused, and all three refusals are load-bearing:

* **A job with no handler is FAILED, not held.** A `QUEUED` row whose type nothing registered would sit
  on the board forever with no sign to the caller; failing it with `no_handler_registered` is the honest
  end state — the caller sees it, retries it if they want, and the queue moves on.
* **Lease expiry is not a sleep.** `lease_expires_at` is read at claim time only; a claim that dies
  mid-job leaves a `RUNNING` row whose lease is already in the past. This slice does not re-queue
  expired leases — that is the operator's call and it belongs in the sweep, not in the drain path, or
  one stuck handler poisons the whole board. A future M-arc may add the sweep; when it does, it must
  bump attempts by the same rule the claim does, so a poison job that keeps crashing eventually lands
  `attempts == max_attempts` and stops being claimed.
* **A job's own failure is recorded, not swallowed, and not retried inline.** `attempts` is bumped at
  claim; a handler that raises leaves status FAILED with the exception text, bounded and printable, with
  `completed_at` set — the shape the `/jobs` read doors already publish.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Job

LEASE_SECONDS: Final = 300

#: What every drainage posts to the ADR-006 state vocabulary. One author, no ambiguity.
TERMINAL_STATES: Final = ("COMPLETED", "FAILED", "CANCELLED")

Handler = Callable[[Job], Any]


def claim(session: Session, *, lease_seconds: int = LEASE_SECONDS, limit: int = 1) -> list[Job]:
    """Claim up to `limit` queued jobs for this worker, atomically. Empty list when the board is empty.

    Each candidate is claimed by a conditional update whose verdict is the rowcount, so two workers
    racing one row produce exactly one winner and zero second-chance claimants. The lease is stored,
    not implied: it is what a future sweep will read to decide whether a RUNNING row is stuck.
    """
    candidates = list(session.scalars(select(Job).where(Job.status == "QUEUED").order_by(Job.created_at.asc(), Job.id.asc()).limit(max(limit * 4, 8))))
    claimed: list[Job] = []
    now = datetime.now(UTC)
    for job in candidates:
        result = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == "QUEUED")
            .values(
                status="RUNNING",
                attempts=Job.attempts + 1,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                updated_at=now,
            )
        )
        if result.rowcount == 1:
            session.refresh(job)
            claimed.append(job)
            if len(claimed) >= limit:
                break
    session.commit()
    return claimed


def complete(session: Session, job: Job, *, result: dict[str, Any] | None = None) -> Job:
    job.status = "COMPLETED"
    job.progress = 100
    job.result = result or {}
    job.lease_expires_at = None
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    return job


def fail(session: Session, job: Job, *, error: str) -> Job:
    job.status = "FAILED"
    job.error = error[:2000]
    job.lease_expires_at = None
    job.updated_at = datetime.now(UTC)
    session.add(job)
    session.commit()
    return job


def claim_by_id(session: Session, job_id: str, *, lease_seconds: int = LEASE_SECONDS) -> Job | None:
    """Claim one *named* job, atomically. `None` when it is not queued any more — and that is success.

    This is the other half of the stream transport (`app/core/job_stream.py`). A stream message is a
    hint that names a job; the hint is at-least-once, so two workers may receive it, and the loser must
    be able to tell "somebody else has it" from "it failed". The same conditional update `claim` uses
    answers both: `rowcount == 1` means this worker owns the lease; `0` means the row is RUNNING,
    COMPLETED, FAILED or gone — in every case the message has done its job and may be acknowledged.

    Re-queueing an expired lease is deliberately *not* done here. A job whose worker died is a RUNNING
    row with a past `lease_expires_at`; `requeue_expired` is the sweep that revives it, and it belongs
    to an operator tick rather than to a claim path that would then be racing itself.
    """
    job = session.get(Job, job_id)
    if job is None:
        return None
    now = datetime.now(UTC)
    result = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "QUEUED")
        .values(
            status="RUNNING",
            attempts=Job.attempts + 1,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    session.refresh(job)
    return job


def requeue_expired(session: Session, *, limit: int = 50) -> list[Job]:
    """Release leases whose worker is gone: RUNNING rows past their lease go back to QUEUED.

    ADR-006 said the sweep was "the operator's call"; this is that call, and the rule it must honour is
    written in the module docstring above — *bump attempts by the same rule the claim does*. A row that
    has already spent `max_attempts` is not resurrected: it is failed with the reason, because a job
    that has crashed every time it ran is a job whose next run crashes too.

    Only rows a *worker* left behind are touched. `lease_expires_at IS NULL` means the row was never
    claimed, and a past `completed_at` means it ended — neither is a lost lease.
    """
    now = datetime.now(UTC)
    candidates = list(
        session.scalars(
            select(Job)
            .where(Job.status == "RUNNING", Job.lease_expires_at.is_not(None), Job.lease_expires_at < now)
            .order_by(Job.lease_expires_at.asc())
            .limit(limit)
        )
    )
    revived: list[Job] = []
    for job in candidates:
        if job.attempts >= job.max_attempts:
            fail(session, job, error=f"lease expired after {job.attempts} attempts; not retrying past max_attempts={job.max_attempts}")
            continue
        result = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == "RUNNING", Job.lease_expires_at < now)
            .values(status="QUEUED", lease_expires_at=None, updated_at=now)
        )
        session.commit()
        if result.rowcount == 1:
            session.refresh(job)
            revived.append(job)
    return revived


def run_claimed(session: Session, job: Job, *, handlers: dict[str, Handler]) -> Job:
    """Run a job this worker already owns. One author for the handler contract, two callers.

    `drain_one` (database poll) and `drain_stream` (message wake-up) differ only in *which* row they
    claim. Everything after the claim — the missing-handler verdict, the bounded error, the result
    shape — must not fork, or the queue would have two behaviours depending on how it was woken.
    """
    handler = handlers.get(str(job.type))
    if handler is None:
        return fail(session, job, error=f"no handler registered for job type {str(job.type)!r}")
    try:
        output = handler(job)
    except Exception as exc:  # noqa: BLE001 — a handler failure is the job's, not the runner's
        return fail(session, job, error=f"{exc.__class__.__name__}: {exc}")
    return complete(session, job, result=output if isinstance(output, dict) else {"value": output})


def drain_one(session: Session, *, handlers: dict[str, Handler]) -> Job | None:
    """Claim and run at most one job. Returns the claimed job, or `None` when the board is empty.

    A handler that raises is a failure the job records — never a silent one, and never a queue-killer:
    the raise does not propagate, and the job ends FAILED with the exception text bounded to 2000 chars.
    """
    claimed = claim(session, limit=1)
    if not claimed:
        return None
    return run_claimed(session, claimed[0], handlers=handlers)
