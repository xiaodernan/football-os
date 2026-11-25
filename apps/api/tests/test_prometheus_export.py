"""The core's scrape door: zero dependencies, zero labels, operator standing, and a queue that is
alertable rather than only readable."""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import ModelCall
from app.services.prometheus_export import render_prometheus

_VALUE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*) (-?\d+(?:\.\d+)?)$")

#: `JobStream.snapshot()` as a live store answers it (M16 §6, measured), so the exporter is judged on the
#: dictionary the door really hands it rather than on a shape invented in this file.
_LIVE_JOB: dict = {
    "available": True, "stream": "football_os:jobs", "group": "workers",
    "published": 3, "taken": 1, "acknowledged": 1, "reclaimed": 0, "dead_lettered": 0, "publish_failures": 0,
    "stream_length": 3, "dead_length": 0, "pending": 1, "undelivered": 2, "consumers": 1,
    "oldest_undelivered_seconds": 1.407, "oldest_pending_seconds": 1.408,
    "pending_idle_seconds": 1.407, "pending_sampled": 1,
}

#: The same method on `JobStream(None)`: the six counters are this process's and survive, the store's
#: numbers do not, and the three ages arrive as `None` because that is what a degraded transport says.
_STORELESS_JOB: dict = {
    "available": False, "stream": "football_os:jobs", "group": "workers",
    "published": 0, "taken": 0, "acknowledged": 0, "reclaimed": 0, "dead_lettered": 0, "publish_failures": 0,
    "oldest_undelivered_seconds": None, "oldest_pending_seconds": None,
    "pending_idle_seconds": None, "pending_sampled": 0,
}

#: The queue's own families as a scrape carries them. Named here because two cases read the list: the
#: contract test asserts it is exactly the set emitted, and the degraded case asserts none of the
#: store-shaped ones survive.
_JOB_GAUGE_NAMES = (
    "football_os_jobs_stream_length", "football_os_jobs_pending", "football_os_jobs_undelivered",
    "football_os_jobs_consumers", "football_os_jobs_dead",
    "football_os_jobs_oldest_undelivered_seconds", "football_os_jobs_oldest_pending_seconds",
    "football_os_jobs_pending_idle_seconds",
)

_JOB_COUNTER_NAMES = (
    "football_os_jobs_published_total", "football_os_jobs_taken_total", "football_os_jobs_acknowledged_total",
    "football_os_jobs_reclaimed_total", "football_os_jobs_dead_lettered_total",
    "football_os_jobs_publish_failures_total",
)


def _body(snapshot: dict, model: dict, spend: float, uptime: float, job: dict | None = None) -> str:
    return render_prometheus(
        snapshot=snapshot, model=model, spend_today_usd=spend, uptime_seconds=uptime, job_stream=job
    )


def _samples(body: str) -> dict[str, str]:
    """The scrape as name → value, so absence is judged on a whole name.

    `football_os_jobs_pending` is a prefix of two other families and `football_os_jobs_dead` of one, so
    `"football_os_jobs_pending" not in body` would be wrong in both directions: blind to a pending
    sample sitting in the text, and accusing the exporter of a family it never wrote.
    """
    return {line.split()[0]: line.split()[1] for line in body.splitlines() if line and not line.startswith("#")}


def test_the_exposition_carries_the_exact_contract_and_legal_names() -> None:
    body = _body(
        snapshot={"request_count": 7, "error_count": 1, "avg_latency_ms": 12.5, "p95_latency_ms": 30.0, "request_sample_size": 100},
        model={"calls": 2, "input_tokens": 3000, "cached_input_tokens": 800, "hit_rate": 0.2667, "cost_usd": 0.0016},
        spend=0.004,
        uptime=3600.0,
        job=_LIVE_JOB,
    )
    lines = body.splitlines()
    assert "\n" not in body or True  # LF endings asserted below
    assert "\r" not in body
    names = [line.split()[0] for line in lines if not line.startswith("#")]
    expected = {
        "football_os_uptime_seconds",
        "football_os_requests_total",
        "football_os_request_errors_total",
        "football_os_request_duration_avg_ms",
        "football_os_request_duration_p95_ms",
        "football_os_request_sample_size",
        "football_os_model_calls_total",
        "football_os_model_input_tokens_total",
        "football_os_model_cached_input_tokens_total",
        "football_os_model_cost_usd_total",
        "football_os_model_spend_today_usd",
        "football_os_cache_hit_rate",
        "football_os_cache_report_coverage",
        "football_os_jobs_available",
        "football_os_jobs_pending_sample_size",
        *(_JOB_COUNTER_NAMES),
        *(_JOB_GAUGE_NAMES),
    }
    assert set(names) == expected
    for line in lines:
        if line.startswith("#"):
            assert re.match(r"^# (HELP|TYPE) [a-zA-Z_:][a-zA-Z0-9_:]*", line), line
            continue
        match = _VALUE.match(line)
        assert match is not None, line
        assert match.group(2).lower() not in {"nan", "inf", "-inf"}
    # Every value is this process's or the store's own number: the stream's *name* — a string with a
    # colon in it, which is a label or a metric-name leak waiting to happen — never reaches the scrape.
    assert "football_os:jobs" not in body


def test_the_queue_block_reads_the_way_the_door_does() -> None:
    """The names the exporter emits are the keys `JobStream.snapshot()` publishes, under a prefix.

    The mapping is the contract: an operator alerting on `football_os_jobs_pending` is alerting on the
    same figure `GET /metrics/jobs-stream` answers, and a rename on either side that this test does not
    catch would silently split the queue's two readings of itself.
    """
    body = _body(
        snapshot={"request_count": 0, "error_count": 0, "avg_latency_ms": 0.0, "p95_latency_ms": None, "request_sample_size": 0},
        model={"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "hit_rate": 0.0, "cost_usd": 0.0},
        spend=0.0,
        uptime=0.0,
        job=_LIVE_JOB,
    )
    samples = _samples(body)
    for key in ("published", "taken", "acknowledged", "reclaimed", "dead_lettered", "publish_failures"):
        assert samples[f"football_os_jobs_{key}_total"] == str(_LIVE_JOB[key]), key
    for name, key in (
        ("football_os_jobs_stream_length", "stream_length"),
        ("football_os_jobs_pending", "pending"),
        ("football_os_jobs_undelivered", "undelivered"),
        ("football_os_jobs_consumers", "consumers"),
        ("football_os_jobs_dead", "dead_length"),
        ("football_os_jobs_oldest_undelivered_seconds", "oldest_undelivered_seconds"),
        ("football_os_jobs_oldest_pending_seconds", "oldest_pending_seconds"),
        ("football_os_jobs_pending_idle_seconds", "pending_idle_seconds"),
        ("football_os_jobs_pending_sample_size", "pending_sampled"),
    ):
        assert float(samples[name]) == float(_LIVE_JOB[key]), f"{name} must carry the door's `{key}`"
    assert samples["football_os_jobs_available"] == "1"


def test_no_label_brace_ever_appears() -> None:
    body = _body(
        snapshot={"request_count": 0, "error_count": 0, "avg_latency_ms": 0.0, "p95_latency_ms": None, "request_sample_size": 0},
        model={"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "hit_rate": 0.0, "cost_usd": 0.0},
        spend=0.0,
        uptime=0.0,
        job=_LIVE_JOB,
    )
    assert "{" not in body and "}" not in body
    # zero input tokens must not manufacture a hit rate that reads as measured
    assert "football_os_cache_hit_rate 0.0" in body
    # a p95 with no sample is absent, not invented
    assert "football_os_request_duration_p95_ms" not in body


def test_a_queue_that_was_not_read_is_not_reported_as_a_quiet_queue() -> None:
    """The `None` ≠ `0` rule of M16 §6, carried into the exposition.

    A Prometheus sample cannot be null, so the only faithful rendering of an age the store would not
    give up is no sample at all. The risk that rule creates is the one `football_os_jobs_available`
    answers: a scrape missing `football_os_jobs_pending` must read as "there is no store", which a
    dashboard doing `sum(...)` or an alert on `> 300` otherwise reads as a queue with nothing in it.
    """
    body = _body(
        snapshot={"request_count": 0, "error_count": 0, "avg_latency_ms": 0.0, "p95_latency_ms": None, "request_sample_size": 0},
        model={"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "hit_rate": 0.0, "cost_usd": 0.0},
        spend=0.0,
        uptime=0.0,
        job=_STORELESS_JOB,
    )
    samples = _samples(body)
    assert samples["football_os_jobs_available"] == "0"
    for name in _JOB_GAUGE_NAMES:
        assert name not in samples, f"{name} is a store's number; a storeless process must not publish it"
    # The process's own counters survive, because a process that never published a hint has a real zero.
    for name in _JOB_COUNTER_NAMES:
        assert samples[name] == "0", f"{name} is this process's own count and is always published"


def test_an_idle_queue_and_an_unreadable_one_are_different_scrapes() -> None:
    """The other half of the pair above: `0` is published when the store answered `0`.

    Without this arm, the case that bans the store's gauges from a degraded scrape would also be
    satisfied by an exporter that never emits them, and a genuinely idle queue would go back to
    reading as no Redis.
    """
    idle = dict(_STORELESS_JOB, available=True, stream_length=0, dead_length=0, pending=0, undelivered=0, consumers=2)
    body = _body(
        snapshot={"request_count": 0, "error_count": 0, "avg_latency_ms": 0.0, "p95_latency_ms": None, "request_sample_size": 0},
        model={"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "hit_rate": 0.0, "cost_usd": 0.0},
        spend=0.0,
        uptime=0.0,
        job=idle,
    )
    samples = _samples(body)
    assert samples["football_os_jobs_available"] == "1"
    assert samples["football_os_jobs_pending"] == "0"
    assert samples["football_os_jobs_undelivered"] == "0"
    assert samples["football_os_jobs_consumers"] == "2"
    # answered store, empty pending window: the ages are still unknown, and still absent rather than zero
    for name in ("football_os_jobs_oldest_undelivered_seconds", "football_os_jobs_oldest_pending_seconds", "football_os_jobs_pending_idle_seconds"):
        assert name not in samples, f"{name} was not measured; `pending_sample_size 0` is what says so"
    assert samples["football_os_jobs_pending_sample_size"] == "0"


def test_the_door_answers_the_operator_and_nobody_else(admin_client: TestClient) -> None:
    response = admin_client.get("/api/v1/metrics/prometheus")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "football_os_requests_total" in response.text
    assert "{" not in response.text
    # The scrape reads the transport: an exporter that renders the block and a door that never hands it
    # in are the same green test file and a very different deployment. Which of the two the process is
    # running is what `…_available` says, so it is the one line that can only come from the wiring.
    assert "football_os_jobs_available" in response.text
    assert "football_os_jobs_published_total" in response.text

    with SessionLocal() as session:
        session.add(ModelCall(id="mc-scraper-1", provider="openai", model="gpt-6-sol", feature="probe",
                              input_tokens=1000, output_tokens=10, cached_input_tokens=800,
                              cache_reported=True, demo_mode=False, success=True))
        session.commit()
    response = admin_client.get("/api/v1/metrics/prometheus")
    assert response.status_code == 200
    assert "football_os_model_cached_input_tokens_total 800" in response.text
    cache_line = [line for line in response.text.splitlines() if line.startswith("football_os_cache_hit_rate ")][0]
    assert float(cache_line.split(" ", 1)[1]) == 0.8
    coverage_line = [line for line in response.text.splitlines() if line.startswith("football_os_cache_report_coverage ")][0]
    assert float(coverage_line.split(" ", 1)[1]) == 1.0


def test_a_silent_gateway_does_not_drag_the_rate_to_zero(admin_client: TestClient) -> None:
    """The bug this pair of columns exists for, pinned.

    Two calls, same size, one where the gateway printed a cache figure and one where it printed
    nothing. The old arithmetic divided 800 by 2 000 and reported 0.4 for a cache that hit 80 % of
    everything it was asked about; a reader cannot tell that from a cache that half works. The rate
    is now taken over the reporting call only, and `coverage` says the figure covers half the bill.
    """
    with SessionLocal() as session:
        session.query(ModelCall).delete()
        session.add(ModelCall(id="mc-silent-1", provider="openai", model="gpt-6-sol", feature="probe",
                              input_tokens=1000, output_tokens=10, cached_input_tokens=800,
                              cache_reported=True, demo_mode=False, success=True))
        session.add(ModelCall(id="mc-silent-2", provider="openai", model="gpt-6-sol", feature="probe",
                              input_tokens=1000, output_tokens=10, cached_input_tokens=0,
                              cache_reported=False, demo_mode=False, success=True))
        session.commit()
    try:
        body = admin_client.get("/api/v1/metrics/prometheus").text
        rate = float([line for line in body.splitlines() if line.startswith("football_os_cache_hit_rate ")][0].split(" ", 1)[1])
        coverage = float([line for line in body.splitlines() if line.startswith("football_os_cache_report_coverage ")][0].split(" ", 1)[1])
        assert rate == 0.8, f"a silent call must not be read as a miss; got {rate}"
        assert coverage == 0.5, f"coverage must say half the bill is unseen; got {coverage}"
        # The raw total is still the whole bill, so a reader who wants it can still sum it themselves.
        assert "football_os_model_cached_input_tokens_total 800" in body
    finally:
        # Leave the ledger as empty as this test found it: the neighbouring test pins an exact rate.
        with SessionLocal() as session:
            session.query(ModelCall).delete()
            session.commit()


def test_the_door_refuses_anonymous_and_plain_accounts(client: TestClient) -> None:
    anonymous = client.get("/api/v1/metrics/prometheus")
    assert anonymous.status_code in (401, 403)
    response = client.post("/api/v1/auth/register", json={
        "email": f"player-{uuid4().hex[:12]}@example.test",
        "password": "strong-pass-1234", "display_name": "Player", "role": "player", "accepts_data_policy": True,
    })
    assert response.status_code == 201
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    plain = client.get("/api/v1/metrics/prometheus")
    assert plain.status_code == 403
