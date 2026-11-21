"""A small, dependency-light load probe against a live FOOTBALL OS API.

Not a production benchmark — a harness that an operator can point at a running instance
to get p50 / p90 / p99 latency and success ratio under a chosen concurrency target.

Usage:
    python scripts/loadtest.py [base_url] [--concurrency N] [--requests R] [--label NAME]
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time

import httpx

DEFAULT_TARGETS = [
    "/healthz",
    "/api/v1/world/status",
    "/api/v1/world/competitions",
    "/api/v1/world/teams?page_size=25&page=1",
    "/api/v1/world/players?page_size=25&page=1",
    "/api/v1/world/matches?page_size=25&page=1",
    "/api/v1/world/news?page_size=10&page=1",
    "/api/v1/world/almanac",
]

def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100) * len(ordered))) - 1))
    return ordered[k]


async def main() -> int:
    parser = argparse.ArgumentParser(description="load probe for a running FOOTBALL OS API")
    parser.add_argument("base_url", default="http://127.0.0.1:8100", help="base URL of the API, no trailing slash")
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--requests", type=int, default=400, help="total number of requests per target")
    parser.add_argument("--label", default="", help="label printed in the header line")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    if args.concurrency < 1:
        print("concurrency must be >= 1", file=sys.stderr)
        return 2
    if args.requests < 1:
        print("requests must be >= 1", file=sys.stderr)
        return 2

    print(f"# load probe{' (' + args.label + ')' if args.label else ''}: base={base} concurrency={args.concurrency} requests/target={args.requests}")
    print(f"targets: {len(DEFAULT_TARGETS)} endpoints")
    print()

    overall_started = time.perf_counter()
    total_ok = 0
    total_fail = 0
    total_throttled = 0

    async def fire(client: httpx.AsyncClient, endpoint: str, request_index: int) -> tuple[str, int, float, str | None]:
        try:
            started = time.perf_counter()
            response = await client.get(base + endpoint, timeout=10.0)
            latency_ms = (time.perf_counter() - started) * 1000.0
            body_size = len(response.content)
            if 200 <= response.status_code < 400:
                return endpoint, response.status_code, latency_ms, None
            # A 429 is the limiter doing its job under load, not a crash. Report it in its own
            # bucket so a healthy, throttling service is not mistaken for a failing one.
            if response.status_code == 429:
                return endpoint, response.status_code, latency_ms, "THROTTLED"
            return endpoint, response.status_code, latency_ms, f"HTTP {response.status_code} ({body_size} bytes)"
        except Exception as exc:  # noqa: BLE001 - report only
            latency_ms = (time.perf_counter() - started) * 1000.0  # type: ignore[possibly-undefined]
            return endpoint, 0, latency_ms, type(exc).__name__

    async with httpx.AsyncClient() as client:
        for endpoint in DEFAULT_TARGETS:
            latencies: list[float] = []
            ok_count = 0
            err_count = 0
            errors: list[str] = []

            semaphore = asyncio.Semaphore(args.concurrency)

            async def one(i: int, *, endpoint: str = endpoint, semaphore: asyncio.Semaphore = semaphore) -> tuple[str, int, float, str | None]:
                async with semaphore:
                    return await fire(client, endpoint, i)

            started = time.perf_counter()
            results = await asyncio.gather(*(one(i) for i in range(args.requests)))
            elapsed = time.perf_counter() - started

            throttled_count = 0
            for _, _status, latency_ms, error in results:
                if error is None:
                    ok_count += 1
                    latencies.append(latency_ms)
                elif error == "THROTTLED":
                    throttled_count += 1
                else:
                    err_count += 1
                    if len(errors) < 5:
                        errors.append(error)

            total_ok += ok_count
            total_fail += err_count
            total_throttled += throttled_count

            latencies.sort()
            p50 = percentile(latencies, 50)
            p90 = percentile(latencies, 90)
            p99 = percentile(latencies, 99)
            avg = statistics.fmean(latencies) if latencies else 0.0
            rps = (ok_count + err_count) / elapsed if elapsed > 0 else 0.0
            status = "PASS" if err_count == 0 else "FAIL"
            print(f"{status} {endpoint}")
            print(f"     ok={ok_count} throttled={throttled_count} fail={err_count}  rps={rps:.1f} avg={avg:.1f}ms p50={p50:.1f}ms p90={p90:.1f}ms p99={p99:.1f}ms")
            for error in errors:
                print(f"     err: {error}")

    overall_elapsed = time.perf_counter() - overall_started
    print()
    print(f"overall ok={total_ok} throttled={total_throttled} fail={total_fail} elapsed={overall_elapsed:.1f}s")
    # A throttled service is alive and enforcing its budgets; only crashes/timeouts/5xx are failures.
    verdict = "PASS" if total_fail == 0 else "FAIL"
    print("verdict:", verdict)
    return 0 if total_fail == 0 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
