"""Performance benchmarking suite (M12 Performance).

Runs configurable load tests against the API and reports latency percentiles, throughput,
and error rates. Designed to be run as a standalone script or in CI.

Usage:
    python -m scripts.bench_api [--concurrency N] [--duration SECONDS] [--endpoint PATH]
    python -m scripts.bench_api --scenario sims [--accounts N] [--careers N] [--rounds N]

Example:
    python -m scripts.bench_api --concurrency 10 --duration 30 --endpoint /api/v1/healthz
    python -m scripts.bench_api --scenario sims --accounts 2 --careers 2 --rounds 2

Two scenarios:

* `steady` (default) — the M12 duration-loop benchmark against one endpoint.
* `sims` — a task-count career walk: registers accounts, opens careers, and plays a fixed
  number of rounds in each. Concurrency is *across* careers: one worker owns a career at a
  time and plays its rounds sequentially, because two concurrent plays of the SAME career are
  refused (the database layer serialises them — probed 2026-10-28, 10/10 trials one 200 one
  409, zero duplicate rounds), so racing within a career would measure the refusal, not the
  engine. The scenario presumes the API runs with `ENV=test` (the rate limiter bypasses) or
  limits generous enough for the account count it is given.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class BenchmarkConfig:
    base_url: str
    endpoint: str
    concurrency: int
    duration_seconds: int
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    timeout: float = 30.0


@dataclass
class RequestResult:
    status_code: int
    latency_ms: float
    error: str | None = None


@dataclass
class BenchmarkResult:
    endpoint: str
    concurrency: int
    duration_seconds: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration_seconds: float
    requests_per_second: float
    error_rate: float
    latencies_ms: list[float]
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    errors_by_code: dict[int, int] = field(default_factory=dict)
    errors_by_type: dict[str, int] = field(default_factory=dict)
    measured_over: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "concurrency": self.concurrency,
            "duration_seconds": self.duration_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "requests_per_second": round(self.requests_per_second, 2),
            "error_rate": round(self.error_rate, 4),
            "latency_percentiles": {
                "p50_ms": round(self.p50_ms, 2),
                "p95_ms": round(self.p95_ms, 2),
                "p99_ms": round(self.p99_ms, 2),
            },
            "max_ms": round(self.max_ms, 2),
            "errors_by_code": self.errors_by_code,
            "errors_by_type": self.errors_by_type,
            "measured_over": self.measured_over,
        }


def percentile(sorted_values: list[float], percentile: float) -> float:
    """Nearest-rank percentile (same as latency_profile.py)."""
    if not sorted_values:
        return 0.0
    index = min(
        len(sorted_values) - 1,
        max(0, int(percentile / 100 * len(sorted_values) + 0.999999) - 1),
    )
    return sorted_values[index]


async def make_request(
    client: httpx.AsyncClient, config: BenchmarkConfig
) -> RequestResult:
    start = time.perf_counter()
    try:
        if config.method == "GET":
            response = await client.get(
                config.endpoint, headers=config.headers, timeout=config.timeout
            )
        elif config.method == "POST":
            response = await client.post(
                config.endpoint,
                headers=config.headers,
                json=config.json_body,
                timeout=config.timeout,
            )
        else:
            return RequestResult(0, 0, f"Unsupported method: {config.method}")
        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(response.status_code, latency_ms)
    except httpx.TimeoutException:
        return RequestResult(0, (time.perf_counter() - start) * 1000, "timeout")
    except httpx.ConnectError as e:
        return RequestResult(
            0, (time.perf_counter() - start) * 1000, f"connection_error: {e}"
        )
    except Exception as e:
        return RequestResult(
            0, (time.perf_counter() - start) * 1000, f"error: {type(e).__name__}: {e}"
        )


def summarise_results(
    all_results: list[RequestResult],
    total_duration_seconds: float,
    *,
    endpoint: str,
    concurrency: int,
    duration_seconds: int,
) -> BenchmarkResult:
    """Turn raw results into a report.

    Latency is measured over every request that **received an HTTP response**, not
    over the successful ones. A 401 is an answer: it took the server as long to
    refuse as it would have taken to serve, and a door that refuses everything is
    exactly the shape a rate-limit storm or a broken token sees. Building the
    percentiles from `successful` alone made such a run publish p50, p95, p99 and
    max as 0.00 ms — not low, *missing* — because the denominator was empty.

    A request that never got a response at all (timeout, refused connection) has
    no latency to report and is excluded rather than recorded as zero, since zero
    is a claim about how long it took. `measured_over` publishes the denominator
    so a reader can see how much of the run the percentiles actually describe.
    """
    total_requests = len(all_results)
    responded = [r for r in all_results if r.status_code > 0]
    successful = [r for r in all_results if 200 <= r.status_code < 400]
    failed = [r for r in all_results if not (200 <= r.status_code < 400)]

    latencies = sorted(r.latency_ms for r in responded)

    errors_by_code: dict[int, int] = {}
    errors_by_type: dict[str, int] = {}
    for r in failed:
        if r.status_code > 0:
            errors_by_code[r.status_code] = errors_by_code.get(r.status_code, 0) + 1
        else:
            error_type = r.error.split(":")[0] if r.error else "unknown"
            errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1

    return BenchmarkResult(
        endpoint=endpoint,
        concurrency=concurrency,
        duration_seconds=duration_seconds,
        total_requests=total_requests,
        successful_requests=len(successful),
        failed_requests=len(failed),
        total_duration_seconds=total_duration_seconds,
        requests_per_second=total_requests / total_duration_seconds
        if total_duration_seconds > 0
        else 0.0,
        error_rate=len(failed) / total_requests if total_requests > 0 else 0.0,
        latencies_ms=latencies,
        p50_ms=percentile(latencies, 50) if latencies else 0.0,
        p95_ms=percentile(latencies, 95) if latencies else 0.0,
        p99_ms=percentile(latencies, 99) if latencies else 0.0,
        max_ms=max(latencies) if latencies else 0.0,
        errors_by_code=errors_by_code,
        errors_by_type=errors_by_type,
        measured_over=len(responded),
    )


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run the benchmark with the given configuration."""
    limits = httpx.Limits(
        max_connections=config.concurrency, max_keepalive_connections=config.concurrency
    )
    timeout = httpx.Timeout(config.timeout)

    stop_event = asyncio.Event()

    async with httpx.AsyncClient(
        base_url=config.base_url, limits=limits, timeout=timeout
    ) as client:
        # Warmup
        warmup_tasks = [
            make_request(client, config) for _ in range(min(5, config.concurrency))
        ]
        await asyncio.gather(*warmup_tasks)

        async def run_worker() -> list[RequestResult]:
            local_results: list[RequestResult] = []
            while not stop_event.is_set():
                result = await make_request(client, config)
                local_results.append(result)
            return local_results

        start_time = time.perf_counter()

        # Run workers for the specified duration
        tasks = [asyncio.create_task(run_worker()) for _ in range(config.concurrency)]

        await asyncio.sleep(config.duration_seconds)
        stop_event.set()

        # Wait for all workers to finish their current request
        all_results: list[RequestResult] = []
        for task in tasks:
            try:
                local = await asyncio.wait_for(task, timeout=5.0)
                all_results.extend(local)
            except TimeoutError:
                pass

        end_time = time.perf_counter()
        # Measured inside the client's lifetime: the window is the worker phase, not
        # however long closing the connection pool happens to take.
        total_duration = end_time - start_time

    return summarise_results(
        all_results,
        total_duration,
        endpoint=config.endpoint,
        concurrency=config.concurrency,
        duration_seconds=config.duration_seconds,
    )


@dataclass
class SimsConfig:
    """The career-sims scenario's shape: accounts → careers → rounds, workers own careers."""

    base_url: str
    accounts: int = 2
    careers_per_account: int = 2
    rounds_per_career: int = 2
    workers: int = 2
    timeout: float = 60.0
    prefix: str = "/api/v1"


def _refusal_code(response: httpx.Response) -> str | None:
    """The API's own refusal code, when the body carries one."""
    try:
        detail = response.json().get("detail")
    except Exception:
        return None
    if isinstance(detail, dict):
        code = detail.get("code")
        return code if isinstance(code, str) else None
    return None


async def run_career_sims(config: SimsConfig) -> dict[str, Any]:
    """Register accounts, open careers, play rounds, verify each career's own count.

    Every phase is measured; a summary dict is returned whether or not the walk succeeded,
    so a refusal leg produces a readable report (and exit 1) rather than a traceback.
    """
    problems: list[str] = []
    setup_errors: list[dict[str, Any]] = []
    play_latencies: list[float] = []
    errors_by_code: dict[int, int] = {}
    refusals_by_reason: dict[str, int] = {}
    errors_by_type: dict[str, int] = {}
    slugs: list[tuple[str, dict[str, str]]] = []
    played_calls = 0
    failed_calls = 0

    started = time.perf_counter()

    async with httpx.AsyncClient(
        base_url=config.base_url, timeout=httpx.Timeout(config.timeout)
    ) as client:

        def record_setup(
            step: str, response: httpx.Response | None, exc: Exception | None = None
        ) -> bool:
            ok = (
                exc is None
                and response is not None
                and 200 <= response.status_code < 400
            )
            if ok:
                return True
            if exc is not None:
                setup_errors.append({"step": step, "error": type(exc).__name__})
                problems.append(f"{step}: {type(exc).__name__}: {exc}")
            else:
                assert response is not None
                setup_errors.append(
                    {
                        "step": step,
                        "status": response.status_code,
                        "code": _refusal_code(response),
                    }
                )
                problems.append(f"{step}: answered {response.status_code}")
            return False

        options = await client.get(f"{config.prefix}/careers/options")
        if not record_setup("careers/options", options):
            return _sims_summary(
                config,
                problems,
                setup_errors,
                play_latencies,
                errors_by_code,
                refusals_by_reason,
                errors_by_type,
                slugs,
                played_calls,
                failed_calls,
                started,
                careers_opened=0,
            )
        clubs = options.json().get("clubs") or []
        if not clubs:
            problems.append("careers/options listed no clubs")
            return _sims_summary(
                config,
                problems,
                setup_errors,
                play_latencies,
                errors_by_code,
                refusals_by_reason,
                errors_by_type,
                slugs,
                played_calls,
                failed_calls,
                started,
                careers_opened=0,
            )
        club = clubs[0]
        club_slug = (
            club.get("slug")
            or club.get("club_slug")
            or next(value for key, value in club.items() if key.endswith("slug"))
        )

        for account in range(config.accounts):
            email = f"bench-sims-{uuid.uuid4().hex[:12]}-{account}@footballos.test"
            try:
                register = await client.post(
                    f"{config.prefix}/auth/register",
                    json={
                        "email": email,
                        "password": "strong-pass-1234",
                        "display_name": "Bench Sims",
                        "role": "player",
                        "accepts_data_policy": True,
                    },
                )
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                record_setup(f"register[{account}]", None, exc)
                return _sims_summary(
                    config,
                    problems,
                    setup_errors,
                    play_latencies,
                    errors_by_code,
                    refusals_by_reason,
                    errors_by_type,
                    slugs,
                    played_calls,
                    failed_calls,
                    started,
                    careers_opened=0,
                )
            if not record_setup(f"register[{account}]", register):
                return _sims_summary(
                    config,
                    problems,
                    setup_errors,
                    play_latencies,
                    errors_by_code,
                    refusals_by_reason,
                    errors_by_type,
                    slugs,
                    played_calls,
                    failed_calls,
                    started,
                    careers_opened=0,
                )
            headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

            for career in range(config.careers_per_account):
                try:
                    create = await client.post(
                        f"{config.prefix}/careers",
                        headers=headers,
                        json={
                            "club": club_slug,
                            "manager_name": f"Bench Sims {account}.{career}",
                            "objectives": [{"kind": "wins", "target": 10}],
                        },
                    )
                except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                    record_setup(f"open_career[{account}.{career}]", None, exc)
                    return _sims_summary(
                        config,
                        problems,
                        setup_errors,
                        play_latencies,
                        errors_by_code,
                        refusals_by_reason,
                        errors_by_type,
                        slugs,
                        played_calls,
                        failed_calls,
                        started,
                        careers_opened=len(slugs),
                    )
                if not record_setup(f"open_career[{account}.{career}]", create):
                    return _sims_summary(
                        config,
                        problems,
                        setup_errors,
                        play_latencies,
                        errors_by_code,
                        refusals_by_reason,
                        errors_by_type,
                        slugs,
                        played_calls,
                        failed_calls,
                        started,
                        careers_opened=len(slugs),
                    )
                body = create.json()
                slug = body["career"]["slug"] if "career" in body else body["slug"]
                slugs.append((slug, headers))

        queue: asyncio.Queue[tuple[str, dict[str, str]]] = asyncio.Queue()
        for entry in slugs:
            queue.put_nowait(entry)

        play_started = time.perf_counter()

        async def play_worker() -> None:
            nonlocal played_calls, failed_calls
            while not queue.empty():
                try:
                    slug, headers = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                for _ in range(config.rounds_per_career):
                    start = time.perf_counter()
                    try:
                        response = await client.post(
                            f"{config.prefix}/careers/{slug}/play", headers=headers
                        )
                    except Exception as exc:  # noqa: BLE001 - counted, not raised
                        kind = type(exc).__name__
                        errors_by_type[kind] = errors_by_type.get(kind, 0) + 1
                        failed_calls += 1
                        play_latencies.append((time.perf_counter() - start) * 1000)
                        continue
                    play_latencies.append((time.perf_counter() - start) * 1000)
                    if 200 <= response.status_code < 400:
                        played_calls += 1
                        continue
                    failed_calls += 1
                    errors_by_code[response.status_code] = (
                        errors_by_code.get(response.status_code, 0) + 1
                    )
                    reason = _refusal_code(response)
                    if reason:
                        refusals_by_reason[reason] = (
                            refusals_by_reason.get(reason, 0) + 1
                        )

        await asyncio.gather(*(play_worker() for _ in range(max(1, config.workers))))
        play_seconds = time.perf_counter() - play_started

        mismatches: list[dict[str, Any]] = []
        for slug, headers in slugs:
            try:
                view = await client.get(
                    f"{config.prefix}/careers/{slug}", headers=headers
                )
            except Exception as exc:  # noqa: BLE001 - reported as a mismatch cause
                mismatches.append(
                    {
                        "slug": slug,
                        "expected": config.rounds_per_career,
                        "found": f"unreadable: {type(exc).__name__}",
                    }
                )
                continue
            if view.status_code != 200:
                mismatches.append(
                    {
                        "slug": slug,
                        "expected": config.rounds_per_career,
                        "found": f"status {view.status_code}",
                    }
                )
                continue
            found = view.json().get("record", {}).get("played")
            if found != config.rounds_per_career:
                mismatches.append(
                    {"slug": slug, "expected": config.rounds_per_career, "found": found}
                )

    return _sims_summary(
        config,
        problems,
        setup_errors,
        play_latencies,
        errors_by_code,
        refusals_by_reason,
        errors_by_type,
        slugs,
        played_calls,
        failed_calls,
        started,
        careers_opened=len(slugs),
        play_seconds=play_seconds,
        mismatches=mismatches,
    )


def _sims_summary(
    config: SimsConfig,
    problems: list[str],
    setup_errors: list[dict[str, Any]],
    play_latencies: list[float],
    errors_by_code: dict[int, int],
    refusals_by_reason: dict[str, int],
    errors_by_type: dict[str, int],
    slugs: list[tuple[str, dict[str, str]]],
    played_calls: int,
    failed_calls: int,
    started: float,
    *,
    careers_opened: int,
    play_seconds: float | None = None,
    mismatches: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The scenario's report. Latency is measured over plays that received a response —
    a refusal is an answer (the server spent its time refusing), so it is in the denominator;
    a transport failure has no latency and is counted only in errors_by_type."""
    sorted_latencies = sorted(play_latencies)
    total_calls = played_calls + failed_calls
    mismatches = mismatches or []
    ok = not problems and failed_calls == 0 and not mismatches
    summary: dict[str, Any] = {
        "scenario": "sims",
        "base_url": config.base_url,
        "accounts": config.accounts,
        "careers_per_account": config.careers_per_account,
        "rounds_per_career": config.rounds_per_career,
        "workers": config.workers,
        "setup": {
            "careers_opened": careers_opened,
            "errors": setup_errors,
        },
        "play": {
            "total_calls": total_calls,
            "successful": played_calls,
            "failed": failed_calls,
            "error_rate": round(failed_calls / total_calls, 4) if total_calls else 0.0,
            "plays_per_second": round(played_calls / play_seconds, 2)
            if play_seconds
            else 0.0,
            "latency_percentiles": {
                "p50_ms": round(percentile(sorted_latencies, 50), 2)
                if sorted_latencies
                else 0.0,
                "p95_ms": round(percentile(sorted_latencies, 95), 2)
                if sorted_latencies
                else 0.0,
                "p99_ms": round(percentile(sorted_latencies, 99), 2)
                if sorted_latencies
                else 0.0,
            },
            "max_ms": round(max(sorted_latencies), 2) if sorted_latencies else 0.0,
            "measured_over": len(sorted_latencies),
            "errors_by_code": errors_by_code,
            "refusals_by_reason": refusals_by_reason,
            "errors_by_type": errors_by_type,
        },
        "verify": {
            "careers_checked": len(slugs),
            "mismatches": mismatches,
        },
        "problems": problems,
        "total_duration_seconds": round(time.perf_counter() - started, 3),
        "ok": ok,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FOOTBALL OS API Performance Benchmark"
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8731", help="Base URL of the API"
    )
    parser.add_argument(
        "--endpoint", default="/api/v1/healthz", help="Endpoint to benchmark"
    )
    parser.add_argument(
        "--concurrency", type=int, default=10, help="Number of concurrent workers"
    )
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument(
        "--method", default="GET", choices=["GET", "POST"], help="HTTP method"
    )
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="Request timeout in seconds"
    )
    parser.add_argument(
        "--scenario",
        default="steady",
        choices=["steady", "sims"],
        help="steady: duration-loop one endpoint; sims: register/open/play career walk",
    )
    parser.add_argument(
        "--accounts", type=int, default=2, help="sims: accounts to register"
    )
    parser.add_argument(
        "--careers", type=int, default=2, help="sims: careers per account (cap 5)"
    )
    parser.add_argument(
        "--rounds", type=int, default=2, help="sims: rounds played per career"
    )
    parser.add_argument(
        "--sim-workers", type=int, default=2, help="sims: concurrent career owners"
    )
    parser.add_argument("--prefix", default="/api/v1", help="sims: API version prefix")

    args = parser.parse_args()

    if args.scenario == "sims":
        config = SimsConfig(
            base_url=args.base_url,
            accounts=args.accounts,
            careers_per_account=args.careers,
            rounds_per_career=args.rounds,
            workers=args.sim_workers,
            timeout=args.timeout,
            prefix=args.prefix,
        )
        print(
            f"Starting career sims: {config.base_url}{config.prefix} "
            f"accounts={config.accounts} careers={config.careers_per_account} "
            f"rounds={config.rounds_per_career} workers={config.workers}"
        )
        summary = asyncio.run(run_career_sims(config))

        print("\n=== CAREER SIMS RESULTS ===")
        print(f"Setup careers opened: {summary['setup']['careers_opened']}")
        if summary["setup"]["errors"]:
            print(f"Setup errors: {summary['setup']['errors']}")
        play = summary["play"]
        print(
            f"Play calls: {play['total_calls']} (successful {play['successful']}, failed {play['failed']})"
        )
        print(f"Plays per second: {play['plays_per_second']:.2f}")
        print(
            f"Latency measured over: {play['measured_over']} responses that actually answered"
        )
        print(f"Latency p50: {play['latency_percentiles']['p50_ms']:.2f}ms")
        print(f"Latency p95: {play['latency_percentiles']['p95_ms']:.2f}ms")
        print(f"Latency p99: {play['latency_percentiles']['p99_ms']:.2f}ms")
        print(f"Max Latency: {play['max_ms']:.2f}ms")
        if play["errors_by_code"]:
            print(f"Errors by code: {play['errors_by_code']}")
        if play["refusals_by_reason"]:
            print(f"Refusals by reason: {play['refusals_by_reason']}")
        if play["errors_by_type"]:
            print(f"Errors by type: {play['errors_by_type']}")
        verify = summary["verify"]
        print(
            f"Verified careers: {verify['careers_checked']} with {len(verify['mismatches'])} mismatch(es)"
        )
        if verify["mismatches"]:
            print(f"Mismatches: {verify['mismatches'][:4]}")
        if summary["problems"]:
            print(f"Problems: {summary['problems'][:4]}")
        print(f"Total duration: {summary['total_duration_seconds']:.2f}s")

        if args.output:
            with open(args.output, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"\nResults written to {args.output}")

        return 0 if summary["ok"] else 1

    config = BenchmarkConfig(
        base_url=args.base_url,
        endpoint=args.endpoint,
        concurrency=args.concurrency,
        duration_seconds=args.duration,
        method=args.method,
        timeout=args.timeout,
    )

    print(f"Starting benchmark: {config.method} {config.base_url}{config.endpoint}")
    print(f"Concurrency: {config.concurrency}, Duration: {config.duration_seconds}s")

    result = asyncio.run(run_benchmark(config))

    print("\n=== BENCHMARK RESULTS ===")
    print(f"Endpoint: {result.endpoint}")
    print(f"Concurrency: {result.concurrency}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Total Requests: {result.total_requests}")
    print(f"Successful: {result.successful_requests}")
    print(f"Failed: {result.failed_requests}")
    print(f"Duration: {result.total_duration_seconds:.2f}s")
    print(f"Throughput: {result.requests_per_second:.2f} req/s")
    print(f"Error Rate: {result.error_rate:.2%}")
    print(
        f"Latency measured over: {result.measured_over} responses that actually answered"
    )
    print(f"Latency p50: {result.p50_ms:.2f}ms")
    print(f"Latency p95: {result.p95_ms:.2f}ms")
    print(f"Latency p99: {result.p99_ms:.2f}ms")
    print(f"Max Latency: {result.max_ms:.2f}ms")

    if result.errors_by_code:
        print(f"Errors by code: {result.errors_by_code}")
    if result.errors_by_type:
        print(f"Errors by type: {result.errors_by_type}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result.to_json(), f, indent=2)
        print(f"\nResults written to {args.output}")

    return 0 if result.failed_requests == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
