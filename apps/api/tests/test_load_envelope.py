"""The load envelope gate: a real server, a real subprocess, the record's own figures.

TestClient cannot stand for a load measurement — the whole question is how the server behaves
under concurrent HTTP, and a WSGI-style in-process transport answers a different question. So this
gate boots uvicorn.Server in a thread against the test run's own database (conftest has already
seeded it and set ENV=test, which is exactly the standing the scenario presumes), waits for
healthz, then drives ``scripts/bench_api --scenario sims`` as a subprocess three times: the gate
shape, which must come back green against the ceilings published in docs/LOAD_ENVELOPE.md, and two
refusal arms, which must come back exit 1 with the refusal named.

The ceilings' single author is the JSON block in docs/LOAD_ENVELOPE.md; this file parses it, so
the prose and the gate cannot drift apart. A subprocess's exit code is read from the return code,
never through a pipe (a pipeline reports the last command's exit, not the script's).
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[3]
ENVELOPE_DOC = REPO_ROOT / "docs" / "LOAD_ENVELOPE.md"


def _read_envelope() -> dict[str, Any]:
    text = ENVELOPE_DOC.read_text(encoding="utf-8")
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.strip() == "```json":
            current = []
        elif line.strip() == "```" and current is not None:
            blocks.append(current)
            current = None
        elif current is not None:
            current.append(line)
    for block in blocks:
        parsed = json.loads("\n".join(block))
        if "p95_ms_ceiling" in parsed:
            return parsed
    raise RuntimeError("docs/LOAD_ENVELOPE.md carries no ```json block with p95_ms_ceiling; " "the gate refuses to run without its published ceilings")


ENVELOPE = _read_envelope()


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    from app.main import app

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/api/v1/healthz", timeout=2.0).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        instance.should_exit = True
        thread.join(timeout=10.0)
        pytest.fail(f"the envelope server never answered {url}/api/v1/healthz within 60s")
    yield url
    instance.should_exit = True
    thread.join(timeout=10.0)


def _run_sims(server_url: str, tmp_path: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    out = tmp_path / f"sims-{uuid.uuid4().hex[:8]}.json"
    command = [
        sys.executable,
        "-m",
        "scripts.bench_api",
        "--scenario",
        "sims",
        "--base-url",
        server_url,
        "--output",
        str(out),
        *extra,
    ]
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=ENVELOPE["subprocess_seconds_ceiling"],
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(f"the bench subprocess exceeded the published ceiling of " f"{ENVELOPE['subprocess_seconds_ceiling']}s\n{error}")
    if not out.exists():
        pytest.fail(f"the bench subprocess wrote no summary (exit {completed.returncode})\n" f"stdout tail:\n{completed.stdout[-1500:]}\nstderr tail:\n{completed.stderr[-1500:]}")
    return completed.returncode, json.loads(out.read_text(encoding="utf-8"))


def test_the_gate_shape_meets_the_published_envelope(server: str, tmp_path: Path) -> None:
    code, summary = _run_sims(
        server,
        tmp_path,
        "--accounts",
        str(ENVELOPE["shape"]["accounts"]),
        "--careers",
        str(ENVELOPE["shape"]["careers_per_account"]),
        "--rounds",
        str(ENVELOPE["shape"]["rounds_per_career"]),
        "--sim-workers",
        str(ENVELOPE["shape"]["workers"]),
    )
    play = summary["play"]
    expected_plays = ENVELOPE["shape"]["accounts"] * ENVELOPE["shape"]["careers_per_account"] * ENVELOPE["shape"]["rounds_per_career"]
    assert code == 0, f"the gate shape must exit 0; the run reported ok={summary.get('ok')} with " f"{play.get('failed')} failed plays and problems {summary.get('problems')}"
    assert summary["ok"] is True, f"the summary says ok={summary['ok']}: {summary['problems']}"
    assert summary["setup"]["careers_opened"] == (ENVELOPE["shape"]["accounts"] * ENVELOPE["shape"]["careers_per_account"]), f"setup errors: {summary['setup']['errors']}"
    assert play["successful"] == expected_plays, (
        f"expected {expected_plays} successful plays, saw {play['successful']} " f"(failed {play['failed']}, by code {play['errors_by_code']}, by type {play['errors_by_type']})"
    )
    assert play["failed"] == 0, f"refusals: {play['refusals_by_reason']}"
    assert play["errors_by_type"] == {}, f"transport failures: {play['errors_by_type']}"
    mismatches = summary["verify"]["mismatches"]
    assert mismatches == [], f"careers must re-read with exactly {ENVELOPE['shape']['rounds_per_career']} played " f"rounds; the engine may not drop a round under concurrency: {mismatches}"
    p95 = play["latency_percentiles"]["p95_ms"]
    assert p95 <= ENVELOPE["p95_ms_ceiling"], f"play p95 {p95}ms exceeds the published ceiling {ENVELOPE['p95_ms_ceiling']}ms " f"(measured_over {play['measured_over']})"


def test_arm_wrong_prefix_refuses_red(server: str, tmp_path: Path) -> None:
    code, summary = _run_sims(server, tmp_path, "--prefix", "/api/v9", "--accounts", "1", "--careers", "1", "--rounds", "1")
    errors = summary["setup"]["errors"]
    assert code == 1, f"the wrong-prefix arm must exit 1, saw {code}: ok={summary.get('ok')}"
    assert summary["ok"] is False
    assert errors and errors[0]["step"] == "careers/options" and errors[0]["status"] == 404, f"the setup must name the 404 it hit: {errors}"
    assert summary["play"]["total_calls"] == 0, "a run whose setup failed must not play"


def test_arm_career_cap_refuses_red(server: str, tmp_path: Path) -> None:
    code, summary = _run_sims(server, tmp_path, "--accounts", "1", "--careers", "6", "--rounds", "1", "--sim-workers", "2")
    errors = summary["setup"]["errors"]
    assert code == 1, f"the career-cap arm must exit 1, saw {code}: ok={summary.get('ok')}"
    assert summary["ok"] is False
    assert (
        errors and errors[0]["step"] == "open_career[0.5]" and errors[0]["status"] == 409 and errors[0]["code"] == "career_limit"
    ), f"the 6th career must be refused with the API's own cap code: {errors}"
    assert summary["setup"]["careers_opened"] == 5, f"the cap allows 5 careers; the run opened {summary['setup']['careers_opened']}"
    assert summary["play"]["total_calls"] == 0, "a run whose setup failed must not play"
