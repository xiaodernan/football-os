#!/usr/bin/env python
"""Drain the async-job queue once, or forever with --loop (spec §47, ADR-006).

The `/jobs` doors read and write the queue; nothing ran it until this script and the drain
in `app.services.jobs`. This is the worker half, and it is deliberately a second process, not
a background task inside the API: a queue whose worker lives inside the web process dies with
it, and a wedged handler takes the product down with it.

One invocation drains everything queued at the moment the command ran — a scheduled task
(cron, the platform's scheduler, a container restart policy) runs it as often as the backlog
needs. `--loop --interval=2` polls inside one process instead, which is the right shape for a
long-lived container and the wrong shape for an interactive laptop.

Handlers are named explicitly, never imported by guessing a module path from the job's type string:
a handler registry keyed by job `type`, registered here, at the edge — the same boundary the rest of
the codebase keeps (the Java plane routes, no football rule; this worker runs, it does not decide).
With no handlers registered every queued job ends FAILED with `no handler registered for job type …`,
never silently, never stuck — that is ADR-006's contract for a queue with no workers, and it is the
correct answer, not a gap to hide.

Usage:
    python scripts/drain_jobs.py                  # drain everything queued now, then exit
    python scripts/drain_jobs.py --loop --interval=2   # poll forever, 2s between passes
    python scripts/drain_jobs.py --handlers app.services.ingest:ingest_knowledge
    python scripts/drain_jobs.py --loop --interval=5 --handlers mypackage.jobs:rebuild_cues

Handler specs are `module:attribute`; the attribute must be callable and accept exactly one
argument — the claimed `Job`. Register as many as you like; unknown types fail loudly and honestly.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.db import SessionLocal  # noqa: E402
from app.models import Job  # noqa: E402
from app.services import jobs as runner  # noqa: E402

logger = logging.getLogger("drain_jobs")


def load_handlers(specs: list[str]) -> dict[str, Callable[[Job], Any]]:
    registry: dict[str, Callable[[Job], Any]] = {}
    for spec in specs:
        module_name, sep, attribute = spec.partition(":")
        if not sep or not module_name or not attribute:
            raise SystemExit(f"handler spec {spec!r} is not module:attribute")
        module = importlib.import_module(module_name)
        target = getattr(module, attribute, None)
        if not callable(target):
            raise SystemExit(f"handler spec {spec!r} does not name a callable attribute")
        # The registry's key is the attribute's own name unless the caller wants a specific type;
        # the jobs' `type` strings are whatever the producer wrote, which is why this accepts
        # a fourth spelling — `type=module:attribute` can not be expressed here, so the queue's
        # type string must match the attribute name. Documented in the module docstring.
        registry[attribute] = target
    return registry


def drain_pass(handlers: dict[str, Callable[[Job], Any]]) -> int:
    ran = 0
    while True:
        session = SessionLocal()
        try:
            outcome = runner.drain_one(session, handlers=handlers)
        finally:
            session.close()
        if outcome is None:
            break
        ran += 1
        logger.info("job %s -> %s", outcome.id, outcome.status)
    return ran


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="poll forever instead of a single pass")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between passes in --loop mode")
    parser.add_argument("--handlers", action="append", default=[], help="module:attribute handler, repeatable")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    handlers = load_handlers(args.handlers)

    if args.loop:
        while True:
            drain_pass(handlers)
            import time

            time.sleep(args.interval)
    else:
        ran = drain_pass(handlers)
        logger.info("drained %d job(s); exiting", ran)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
