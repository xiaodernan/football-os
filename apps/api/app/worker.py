"""The worker process: the other half of the queue, and the only thing that runs a handler.

`python -m app.worker` — one process, one consumer name, one loop. It exists because the API must not
run jobs: a request thread that starts a video analysis holds a connection and a CPU for minutes, and
the first slow handler would take the API's latency with it. The split is the ordinary one, and the
reason it is written here rather than in a shell script is that the loop's two sources — the stream and
the poll — have to be interleaved with a shutdown check and a lease sweep, which is a program.

Three loop properties are deliberate:

* **A tick with nothing to do sleeps, and a tick with work does not.** The sleep is what makes an idle
  worker cost nothing; skipping it when work was found is what makes a backlog drain at handler speed
  rather than at tick speed.
* **`--max-jobs` is a real exit condition.** It is what a bounded batch run (a cron sweep, a CI smoke
  test) needs, and it is what lets this module be tested without a timeout.
* **SIGINT/SIGTERM finish the current job and leave.** A job killed mid-handler stays RUNNING until its
  lease expires and `requeue_expired` revives it, which is correct but slow; the graceful path is
  cheaper, and it is the difference between a deploy costing seconds and a deploy costing a lease.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import time
from types import FrameType

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.job_stream import close_job_stream, get_job_stream
from app.core.logging import configure_logging, get_logger
from app.services import job_broker
from app.services.job_handlers import handlers as build_handlers
from app.services.job_handlers import registered_types
from app.services.jobs import requeue_expired

logger = get_logger("worker")

_stopping = False


def _stop(signum: int, _frame: FrameType | None) -> None:
    global _stopping
    _stopping = True
    logger.info("worker: signal %s received; finishing the current job", signum)


def _default_consumer() -> str:
    #: Host and pid, because that is what an operator needs to find the process behind a pending
    #: message. A pure UUID would be unique and useless; `host:pid` is unique enough on one node.
    return f"{socket.gethostname()}:{os.getpid()}"


def run(*, consumer: str, interval: float, max_jobs: int | None, sweep_every: int, once: bool) -> int:
    """The loop. Returns the number of jobs executed — the only number a batch run can be judged on."""
    configure_logging()
    stream = get_job_stream()
    logger.info(
        "worker: starting as %s (stream=%s, available=%s, types=%s)",
        consumer,
        stream.stream,
        stream.available,
        ",".join(registered_types()) or "none",
    )
    handlers = build_handlers()
    executed = 0
    ticks = 0
    while not _stopping:
        session: Session = SessionLocal()
        try:
            done = job_broker.tick(session, consumer=consumer, handlers=handlers)
        except Exception as exc:  # noqa: BLE001 — a bad tick is logged and the loop survives it
            logger.exception("worker: tick failed: %s", exc)
            done = 0
        finally:
            session.close()
        executed += done
        ticks += 1
        if max_jobs is not None and executed >= max_jobs:
            break
        if once and done == 0:
            break
        # The sweep is cheap (one bounded query) and its whole value is that it runs when nothing else
        # is happening — a worker that only revives lost leases while busy never revives them.
        if sweep_every and ticks % sweep_every == 0:
            session = SessionLocal()
            try:
                revived = requeue_expired(session)
                if revived:
                    logger.info("worker: revived %d expired lease(s)", len(revived))
            finally:
                session.close()
        if done == 0:
            time.sleep(interval)
    # A consumer that exits cleanly stops counting as a live worker. A consumer that is killed does
    # not run this line — and that is right: its name stays in the group until its pending messages are
    # reclaimed, which is exactly when the number should still include it.
    stream.leave(consumer)
    close_job_stream()
    logger.info("worker: stopped after %d job(s) over %d tick(s)", executed, ticks)
    return executed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.worker", description="Drain the job queue (ADR-006 + Redis Streams).")
    parser.add_argument("--consumer", default=_default_consumer(), help="consumer name registered in the group")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds to sleep after an idle tick")
    parser.add_argument("--max-jobs", type=int, default=None, help="exit after this many jobs (batch mode)")
    parser.add_argument("--sweep-every", type=int, default=30, help="ticks between expired-lease sweeps; 0 disables")
    parser.add_argument("--once", action="store_true", help="one pass over the queue, then exit")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    executed = run(
        consumer=args.consumer,
        interval=max(0.0, args.interval),
        max_jobs=args.max_jobs,
        sweep_every=max(0, args.sweep_every),
        once=args.once,
    )
    return 0 if executed >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
