"""The nearest-rank percentile, shared so the two sets of percentiles in this project cannot drift.

`services/latency_profile.py` had its own copy under a leading underscore, which was correct while it was
the only percentile in the tree. `/metrics/system` now reports a percentile over what callers waited as well
as one over what the model calls took, and two implementations of the same arithmetic in one process get a
coin-flip away from disagreeing — a p95 that differs by which door you asked. Nearest-rank rather than
interpolated, because an interpolated value between two rows is a number no request actually took, and these
figures sit beside sentences about what somebody waited.
"""

from __future__ import annotations


def nearest_rank(sorted_values: list[float], fraction: float) -> float:
    """The smallest value at or above the requested share of the sample.

    `sorted_values` must already be sorted ascending. The `+ 0.999999` is the ceiling expressed so that
    0.95 over 100 rows is the 95th rather than the 94th, which is the classic off-by-one in this formula
    and the one the latency profile's test pins.
    """
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, int(fraction * len(sorted_values) + 0.999999) - 1))
    return float(sorted_values[index])


__all__ = ["nearest_rank"]
