"""When this process began, for the uptime figure `/metrics/system` answers (spec §58).

The door has promised uptime since it was written, carried the field in its response model, and answered
`uptime_seconds=0.0` for every request with a comment asking for process start time tracking that nobody
made happen. A zero is not a small number. Uptime is the one figure that separates "restarted seconds ago"
from "has been up for a week", so the placeholder inverted both readings at once, and every reader of the
door — the docstring, the OpenAPI schema, the dashboard pointing at it — said the accumulation was real.

It lives here rather than in the door or in `main` because a module-level constant is captured at import,
which is the last moment shared by every process, and because the metrics door cannot read one from `main`
without an import cycle. It also cannot live in `main` usefully at all: uvicorn's `--reload` runs a supervisor
plus a worker, and each of the two imports this file independently, which is the correct answer to "how long
has *this* process been serving" rather than the supervisor's age.
"""

from __future__ import annotations

import time

# `perf_counter`, not `time`: the wall clock can step backwards, and a duration that shrinks is worse than
# one that is merely stale. `time.time()` would also make uptime depend on the host's NTP rather than on the
# process, so a clock correction would show up as an outage or as a jump into the future.
started_at: float = time.perf_counter()


def uptime_seconds() -> float:
    """How long this process has been running, in seconds."""
    return time.perf_counter() - started_at
