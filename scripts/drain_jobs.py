#!/usr/bin/env python
"""Drain the async-job queue once, or forever with --loop (spec §47, ADR-006, ADR-008).

A thin front end over `app.worker`: the loop itself lives there so this script, the container command
in `infra/docker-compose.yml` and a laptop invocation cannot drift into three behaviours. What this file
adds is what a shell entry point needs and a process entry point does not — `--handlers
module:attribute` for a one-off type, and a single-pass default that returns when the board is empty.

Handlers come from `app.services.job_handlers` — the registry — *before* any `--handlers` are applied.
That default is the difference between a worker and a queue-shaped hole: this script used to register
nothing unless asked, so the documented invocation drained every queued job straight to FAILED with
`no handler registered for job type …`. The registry is what makes `python scripts/drain_jobs.py` mean
"run the jobs this build knows how to run".

A type nothing registered is still FAILED, with the reason in the row — ADR-006's contract for a queue
with no worker for that type, and the correct answer rather than a gap to hide.

Usage:
    python scripts/drain_jobs.py                        # one pass over the queue, then exit
    python scripts/drain_jobs.py --loop --interval=2    # long-lived consumer
    python scripts/drain_jobs.py --handlers mypkg.jobs:rebuild_cues
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.job_handlers import register  # noqa: E402
from app.worker import main as worker_main  # noqa: E402

logger = logging.getLogger("drain_jobs")


def load_handlers(specs: list[str]) -> list[str]:
    """Register `module:attribute` handlers under the attribute's own name, and return those names.

    The key is the attribute name because a job's `type` string is whatever the producer wrote; the
    registry's built-in types are dotted (`video.analyse`) and cannot be expressed as a module path, so
    a caller who needs one of those uses the registry, not a flag.
    """
    registered: list[str] = []
    for spec in specs:
        module_name, sep, attribute = spec.partition(":")
        if not sep or not module_name or not attribute:
            raise SystemExit(f"handler spec {spec!r} is not module:attribute")
        module = importlib.import_module(module_name)
        target = getattr(module, attribute, None)
        if not callable(target):
            raise SystemExit(f"handler spec {spec!r} does not name a callable attribute")
        register(attribute, target)
        registered.append(attribute)
    return registered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drain the async-job queue (ADR-006 + ADR-008).")
    parser.add_argument("--loop", action="store_true", help="poll forever instead of a single pass")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between passes in --loop mode")
    parser.add_argument("--handlers", action="append", default=[], help="module:attribute handler, repeatable")
    parser.add_argument("--consumer", default=None, help="consumer name registered in the stream's group")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    extra = load_handlers(args.handlers)
    if extra:
        logger.info("registered %d handler(s) from the command line: %s", len(extra), ", ".join(extra))

    forwarded = ["--interval", str(args.interval)]
    if args.consumer:
        forwarded += ["--consumer", args.consumer]
    if not args.loop:
        forwarded.append("--once")
    return worker_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
