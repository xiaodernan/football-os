"""The bridge between the stream hint and the database claim — the only place the two meet.

Everything in this module is a policy about *when* the two halves of the queue are allowed to touch,
and each policy is here because the alternative is a queue that lies:

* **A hint is acknowledged after the row is claimed and run, never before.** Acknowledging on receipt
  would make a crashed worker's message vanish; acknowledging after the run means a duplicate hint is
  the worst case, and a duplicate hint costs one conditional `UPDATE` that returns nothing.
* **A failed job is still acknowledged.** The message did its job: it named a row, the row was claimed,
  the handler ran and the row says FAILED. Re-delivering the message would re-run a handler the state
  machine has already judged — retries belong to `attempts`/`max_attempts`, which survives a restart.
* **A message that names a row somebody else owns is acknowledged.** `claim_by_id` returning `None`
  means QUEUED is gone: this worker lost the race, or the job already ended, or the row was deleted.
  All three are answers, and none of them is "try again later" — the sweep and the poll loop own those.
* **A poison message dies at `MAX_DELIVERIES`.** The count comes from Redis's pending list, not from a
  field the producer wrote, so a message redelivered because its consumer died five times is treated
  the same as one whose claim kept raising. It moves to the dead-letter stream with the reason.

The producer side is one function, `publish_queued`, and it is called *after* the commit. A hint for a
row that rolled back would be a job nobody can claim — a message that costs one no-op and one confused
operator. A hint that arrives late costs one tick.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.job_stream import MAX_DELIVERIES, JobStream, get_job_stream
from app.services.jobs import Handler, claim_by_id, drain_one, run_claimed

logger = logging.getLogger(__name__)


def publish_queued(job: Any, *, stream: JobStream | None = None) -> str | None:
    """Announce a committed `QUEUED` row. Returns the message id, or `None` when it was not sent."""
    target = stream or get_job_stream()
    message_id = target.publish(str(job.id), str(job.type))
    if message_id is None and target.available:
        # Available but refused: the caller should know the wake-up did not happen even though the row
        # is safe. Logged rather than raised, because the request has already been answered for.
        logger.warning("job broker: queued job %s was not announced; the poll loop will find it", job.id)
    return message_id


def drain_stream(
    session: Session,
    *,
    handlers: dict[str, Handler] | None = None,
    consumer: str,
    limit: int = 8,
    stream: JobStream | None = None,
) -> int:
    """Take a batch of hints, run what this worker wins, and acknowledge every one of them.

    Returns the number of jobs *executed* (not the number of messages seen), because that is the number
    a caller can compare against a queue depth. `reclaim` is tried only when `read` came back empty: a
    worker with fresh work should do the fresh work first, and a reclaim on every tick would steal
    messages from a consumer that is merely slow.
    """
    target = stream or get_job_stream()
    if not target.available:
        return 0
    if handlers is None:
        from app.services.job_handlers import handlers as build_handlers

        handlers = build_handlers()
    entries = target.read(consumer, count=limit)
    if not entries:
        entries = target.reclaim(consumer, count=limit)
    executed = 0
    for entry in entries:
        if entry.deliveries > MAX_DELIVERIES:
            target.to_dead(
                entry,
                reason=f"delivered {entry.deliveries} times without an acknowledgement; the claim never settled",
            )
            continue
        job = claim_by_id(session, entry.job_id)
        if job is None:
            # Not queued any more: another consumer won it, or it already ended. Either way this
            # message has been answered, and leaving it pending would make an operator chase a ghost.
            target.ack(entry.id)
            continue
        run_claimed(session, job, handlers=handlers)
        target.ack(entry.id)
        executed += 1
    return executed


def tick(
    session: Session,
    *,
    consumer: str,
    handlers: dict[str, Handler] | None = None,
    limit: int = 8,
    stream: JobStream | None = None,
    poll_fallback: int = 4,
) -> int:
    """One worker iteration: the stream first, then the poll loop for anything the stream missed.

    The fallback is not a legacy path kept for compatibility — it is what makes the stream a hint. A
    hint lost to a `MAXLEN` trim, a publish that failed while Redis was restarting, or a row inserted by
    a process that does not speak the stream (a migration, an ops script) is still a QUEUED row, and the
    poll loop is what turns "still a row" into "done". `poll_fallback` bounds how much of a tick that
    costs when the board is full.
    """
    if handlers is None:
        from app.services.job_handlers import handlers as build_handlers

        handlers = build_handlers()
    executed = drain_stream(session, handlers=handlers, consumer=consumer, limit=limit, stream=stream)
    for _ in range(poll_fallback):
        if drain_one(session, handlers=handlers) is None:
            break
        executed += 1
    return executed
