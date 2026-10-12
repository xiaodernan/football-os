"""The harness must measure a response, not a success.

`scripts/bench_api.py` built its latency percentiles from the *successful*
requests only. Measured on this host that meant a run against an
authentication-rejected door — every request answered 401, which is what the
door is supposed to do — reported p50, p95, p99 and max as 0.00 ms. A reader
would have taken that as "instant"; the truth was 1,061 responses whose
latencies were simply never collected. The number was not low, it was missing,
and it was published in the shape of a measurement.

The distinction the fix keeps: a request that got an HTTP response has a
latency whether or not the caller liked the answer, and a request that never
got one — a timeout, a refused connection — has no latency at all. Percentiles
are computed over the first set and the second is reported separately, so the
denominator is visible instead of assumed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "bench_api.py"


def _load_bench():
    spec = importlib.util.spec_from_file_location("bench_api_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # `RequestResult` is a dataclass, and dataclasses resolve their own module through
    # sys.modules while they build — an unregistered module makes every field look like
    # it came from None. The registration has to precede exec_module, not follow it.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(module, status_code: int, latency_ms: float, error: str | None = None):
    return module.RequestResult(status_code=status_code, latency_ms=latency_ms, error=error)


def test_a_rejected_response_still_carries_a_latency() -> None:
    module = _load_bench()
    results = [_result(module, 401, 12.0 + i) for i in range(10)]
    summary = module.summarise_results(results, 1.0, endpoint="/players", concurrency=10, duration_seconds=1)

    assert summary.total_requests == 10
    assert summary.failed_requests == 10
    assert summary.errors_by_code == {401: 10}
    assert summary.latencies_ms == [12.0 + i for i in range(10)]
    assert summary.p50_ms > 0.0, "a door that always refuses still takes time to refuse"
    assert summary.measured_over == 10


def test_a_transport_failure_has_no_latency_to_report() -> None:
    module = _load_bench()
    results = [
        _result(module, 200, 5.0),
        _result(module, 0, 0.0, "timeout"),
        _result(module, 0, 0.0, "connection_error: refused"),
    ]
    summary = module.summarise_results(results, 1.0, endpoint="/x", concurrency=3, duration_seconds=1)

    assert summary.total_requests == 3
    assert summary.successful_requests == 1
    assert summary.failed_requests == 2
    assert summary.errors_by_code == {}
    assert summary.errors_by_type == {"timeout": 1, "connection_error": 1}
    assert summary.latencies_ms == [5.0], "a request that never answered is not a fast request"
    assert summary.measured_over == 1


def test_the_percentile_denominator_is_published() -> None:
    module = _load_bench()
    summary = module.summarise_results(
        [_result(module, 404, 3.0), _result(module, 0, 0.0, "timeout")],
        1.0,
        endpoint="/x",
        concurrency=2,
        duration_seconds=1,
    )

    assert summary.measured_over == 1
    assert summary.to_json()["measured_over"] == 1


def test_nearest_rank_percentiles_agree_with_the_latency_profile() -> None:
    """Two nearest-rank implementations in one repository must not disagree."""
    module = _load_bench()
    values = [float(i) for i in range(1, 101)]
    assert module.percentile(values, 50) == 50.0
    assert module.percentile(values, 95) == 95.0
    assert module.percentile(values, 99) == 99.0
    assert module.percentile([], 95) == 0.0
