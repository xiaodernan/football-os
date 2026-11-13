"""The core's scrape door: zero dependencies, zero labels, operator standing."""

from __future__ import annotations

import re
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import ModelCall
from app.services.prometheus_export import render_prometheus

_VALUE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*) (-?\d+(?:\.\d+)?)$")


def _body(snapshot: dict, model: dict, spend: float, uptime: float) -> str:
    return render_prometheus(snapshot=snapshot, model=model, spend_today_usd=spend, uptime_seconds=uptime)


def test_the_exposition_carries_the_exact_contract_and_legal_names() -> None:
    body = _body(
        snapshot={"request_count": 7, "error_count": 1, "avg_latency_ms": 12.5, "p95_latency_ms": 30.0, "request_sample_size": 100},
        model={"calls": 2, "input_tokens": 3000, "cached_input_tokens": 800, "hit_rate": 0.2667, "cost_usd": 0.0016},
        spend=0.004,
        uptime=3600.0,
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
    }
    assert set(names) == expected
    for line in lines:
        if line.startswith("#"):
            assert re.match(r"^# (HELP|TYPE) [a-zA-Z_:][a-zA-Z0-9_:]*", line), line
            continue
        match = _VALUE.match(line)
        assert match is not None, line
        assert match.group(2).lower() not in {"nan", "inf", "-inf"}


def test_no_label_brace_ever_appears() -> None:
    body = _body(
        snapshot={"request_count": 0, "error_count": 0, "avg_latency_ms": 0.0, "p95_latency_ms": None, "request_sample_size": 0},
        model={"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "hit_rate": 0.0, "cost_usd": 0.0},
        spend=0.0,
        uptime=0.0,
    )
    assert "{" not in body and "}" not in body
    # zero input tokens must not manufacture a hit rate that reads as measured
    assert "football_os_cache_hit_rate 0.0" in body
    # a p95 with no sample is absent, not invented
    assert "football_os_request_duration_p95_ms" not in body


def test_the_door_answers_the_operator_and_nobody_else(admin_client: TestClient) -> None:
    response = admin_client.get("/api/v1/metrics/prometheus")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "football_os_requests_total" in response.text
    assert "{" not in response.text

    with SessionLocal() as session:
        session.add(ModelCall(id="mc-scraper-1", provider="openai", model="gpt-6-sol", feature="probe",
                              input_tokens=1000, output_tokens=10, cached_input_tokens=800,
                              demo_mode=False, success=True))
        session.commit()
    response = admin_client.get("/api/v1/metrics/prometheus")
    assert response.status_code == 200
    assert "football_os_model_cached_input_tokens_total 800" in response.text
    cache_line = [line for line in response.text.splitlines() if line.startswith("football_os_cache_hit_rate ")][0]
    assert float(cache_line.split(" ", 1)[1]) == 0.8


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
