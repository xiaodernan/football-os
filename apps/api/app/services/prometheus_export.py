"""The core's own scrape door — Prometheus text, zero dependencies.

The edge already publishes `/actuator/prometheus`; the Python core published nothing a
Prometheus could chew on, so a fleet scrape showed half the platform. This module renders the
counters this process already keeps as exposition text. No new dependency, no PII-shaped label,
no cardinality trap: every metric here carries no label, which is why the door is safe to serve
to the operator tier and nothing else adds a series per account.

Figures are this process's own, matching the `/metrics/system` door's honesty about scope; a
fleet view is the sum of the workers, which is what any node-local scrape produces.
"""

from __future__ import annotations

import re
from typing import Any

_NAME = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")


def _check_name(name: str) -> str:
    if not _NAME.match(name):
        raise ValueError(f"metric name {name!r} is not Prometheus-legal")
    return name


def _metric(name: str, type_: str, help_: str, value: float | int) -> list[str]:
    _check_name(name)
    # HELP lines are comment-shaped; strip newlines so a bad help string cannot break the format.
    safe_help = help_.replace("\n", " ").replace("\\", "\\\\")
    return [
        f"# HELP {name} {safe_help}",
        f"# TYPE {name} {type_}",
        f"{name} {value}",
    ]


def render_prometheus(
    *,
    snapshot: dict[str, Any],
    model: dict[str, Any],
    spend_today_usd: float,
    uptime_seconds: float,
) -> str:
    """One exposition body from the pieces each caller already owns.

    `snapshot` is `app.core.request_metrics.snapshot()`. `model` is `app.services.model_ledger.cache_hit_rate()`.
    Both are dictionaries of plain numbers; nothing here is read from a hidden global so a test can hand
    in a fixture instead of the live counters.
    """
    out: list[str] = []
    out += _metric("football_os_uptime_seconds", "gauge", "Seconds since this process booted.", round(float(uptime_seconds), 2))
    out += _metric("football_os_requests_total", "counter", "Requests this process answered since boot.", int(snapshot.get("request_count", 0) or 0))
    out += _metric("football_os_request_errors_total", "counter", "Responses with status >= 500 this process answered.", int(snapshot.get("error_count", 0) or 0))
    out += _metric("football_os_request_duration_avg_ms", "gauge", "Mean duration of the newest sampled responses.", round(float(snapshot.get("avg_latency_ms", 0.0) or 0.0), 2))
    p95 = snapshot.get("p95_latency_ms")
    if p95 is not None:
        out += _metric("football_os_request_duration_p95_ms", "gauge", "p95 of the newest sampled responses (nearest rank).", round(float(p95), 2))
    out += _metric("football_os_request_sample_size", "gauge", "How many durations the two gauges above are read over.", int(snapshot.get("request_sample_size", 0) or 0))
    out += _metric("football_os_model_calls_total", "counter", "AI calls this deployment recorded.", int(model.get("calls", 0) or 0))
    out += _metric("football_os_model_input_tokens_total", "counter", "Input tokens across recorded AI calls.", int(model.get("input_tokens", 0) or 0))
    out += _metric("football_os_model_cached_input_tokens_total", "counter", "Cached input tokens across recorded AI calls.", int(model.get("cached_input_tokens", 0) or 0))
    out += _metric("football_os_model_cost_usd_total", "counter", "Estimated cost of recorded AI calls in USD.", round(float(model.get("cost_usd", 0.0) or 0.0), 6))
    out += _metric("football_os_model_spend_today_usd", "gauge", "Actual AI spend today, this deployment, USD.", round(float(spend_today_usd), 6))
    out += _metric("football_os_cache_hit_rate", "gauge", "Cached input tokens divided by input tokens over recorded AI calls; 0 when none recorded.", round(float(model.get("hit_rate", 0.0) or 0.0), 4))
    return "\n".join(out) + "\n"


__all__ = ["render_prometheus"]
