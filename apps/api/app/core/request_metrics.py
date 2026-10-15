"""Request metrics this process has served, for the rows `/metrics/system` answers.

Those rows measured something else. `request_count` was `COUNT(ModelCall.id)` and `error_count` the failed
subset of the same table, so the two figures an operator looks at first answered how much AI the product
bought rather than how much traffic it took. A door returning 404 all day, a rate limiter firing, a worker
wedging, none of it moved either number — and `/metrics/providers` already answers the question they
actually answered, over the ledger, better than they did.

What replaced them is this: a count of what was served, a count of what failed, and a bounded sample of what
callers waited. The sample is bounded for the reason the latency profile's is, and the deque keeps only the
newest, which is the same population a percentile over a window would read — an unbounded list in the
request path of a long-lived process is a memory leak with a friendlier name than a memory leak.

Two scopes, stated plainly rather than discovered: the figures are *this process's*, and every uvicorn
worker holds its own. Uptime is the same, and the two answers belong together, so a reader of the row is
told which process they are looking at rather than being left to assume it is the deployment.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from app.core.percentile import nearest_rank

#: How many of the newest durations to keep. Large enough that a p95 over the sample is within a few
#: percent of the whole population, small enough that the memory is constant rather than a function of
#: how long the process has been up.
SAMPLE_SIZE: int = 2000

_durations: deque[float] = deque(maxlen=SAMPLE_SIZE)
_requests: int = 0
_errors: int = 0


def record(status_code: int, duration_ms: float) -> None:
    """Note one served request.

    Called from `request_context` in `app/main.py`, which is the outermost user middleware and therefore
    the one place that sees every response — including the exception path, where a route raised and the
    caller will nonetheless be answered, because that answer is the one that has to be counted most.
    """
    global _requests, _errors

    _requests += 1
    if status_code >= 500:
        _errors += 1
    _durations.append(duration_ms)


def reset() -> None:
    """Drop every figure. For a test that needs to know exactly what it just recorded."""
    global _requests, _errors

    _durations.clear()
    _requests = 0
    _errors = 0


def snapshot() -> dict[str, Any]:
    """The rows as the door reports them, with the sample's own honesty attached."""
    sample = sorted(_durations)
    average = sum(sample) / len(sample) if sample else 0.0
    return {
        "request_count": _requests,
        "error_count": _errors,
        "avg_latency_ms": round(average, 2),
        "p95_latency_ms": round(nearest_rank(sample, 0.95), 2),
        "request_sample_size": len(sample),
        "request_sample_is_newest": len(sample) >= SAMPLE_SIZE,
        "scope": "this process",
    }


__all__ = ["SAMPLE_SIZE", "record", "reset", "snapshot"]
