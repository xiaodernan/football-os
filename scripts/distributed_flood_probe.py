"""A multi-process flood probe against a live FOOTBALL OS API.

`loadtest.py` measures one client's healthy-path latency; `credential_stuffing_probe.py` hammers
one auth door from one process. This harness asks the question the other two cannot: does the
service keep answering when several independent client processes simultaneously sustain load,
then dump a burst at it, then are asked to be let back in?

Each worker owns its own event loop, connection pool and socket table, so the edge sees genuinely
independent concurrent sources rather than one asyncio task tree. That is a *client-side* multi-node
simulation, not a distributed deployment: the target remains one process on one machine. The report
says so, because a harness must not advertise more than it measured.

Usage:
    python scripts/distributed_flood_probe.py [base_url] [--workers 6] [--duration 30]
        [--rps 12] [--burst 200] [--label NAME]

Exit 0 only when: no 5xx, no transport failure under load, and the door answers after the flood.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import statistics
import sys
import time
from collections import Counter
from typing import Any

import httpx

TARGETS = (
    "/healthz",
    "/api/v1/world/status",
    "/api/v1/world/competitions",
    "/api/v1/world/matches?page_size=25&page=1",
    "/api/v1/world/almanac",
    "/api/v1/world/records",
    # No /coach-read or /chronicle here: a flood must never turn into thousands of gateway calls.
)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100) * len(ordered))) - 1))
    return ordered[index]


def _worker(spec: dict[str, Any]) -> dict[str, Any]:
    """One independent process: sustained load, one burst, then a quiet probe."""
    base: str = spec["base"]
    worker_id: int = spec["worker"]
    duration: float = spec["duration"]
    rps: int = spec["rps"]
    burst: int = spec["burst"]
    latencies: list[float] = []
    codes: Counter[str] = Counter()
    errors: Counter[str] = Counter()

    async def call(client: httpx.AsyncClient, path: str) -> None:
        started = time.perf_counter()
        try:
            response = await client.get(base + path)
            codes[str(response.status_code)] += 1
        except Exception as error:  # noqa: BLE001 — a transport failure is a finding, not a reason to stop.
            errors[type(error).__name__] += 1
        latencies.append((time.perf_counter() - started) * 1000)

    async def run() -> dict[str, Any]:
        limits = httpx.Limits(max_connections=max(32, rps * 2), max_keepalive_connections=16)
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), limits= limits, follow_redirects=True) as client:
            deadline = time.monotonic() + duration
            next_tick = time.monotonic()
            sent = 0
            while time.monotonic() < deadline:
                batch = [
                    call(client, TARGETS[(sent + offset + worker_id) % len(TARGETS)])
                    for offset in range(rps)
                ]
                await asyncio.gather(*batch)
                sent += rps
                # One batch *is* one second of load: `rps` requests are dispatched together and
                # the schedule advances a full second. Sleeping `1/rps` here would multiply the
                # intended rate by `rps` and turn a measured probe into an unlabelled flood.
                next_tick += 1.0
                lag = next_tick - time.monotonic()
                if lag > 0:
                    await asyncio.sleep(lag)
                elif lag < -1.0:
                    next_tick = time.monotonic()

            burst_started = time.perf_counter()
            await asyncio.gather(*[
                call(client, TARGETS[(index + worker_id) % len(TARGETS)]) for index in range(burst)
            ])
            burst_ms = (time.perf_counter() - burst_started) * 1000
            await asyncio.sleep(1.5)
            try:
                after_flood = (await client.get(base + "/healthz")).status_code
            except Exception:  # noqa: BLE001 — a dead door after the flood is the finding.
                after_flood = 0
        return {
            "worker": worker_id,
            "sustained_requests": sent,
            "burst_requests": burst,
            "burst_ms": round(burst_ms, 1),
            "after_flood": after_flood,
            "codes": dict(codes),
            "errors": dict(errors),
            "p50_ms": round(percentile(latencies, 50), 1),
            "p99_ms": round(percentile(latencies, 99), 1),
        }

    return asyncio.run(run())


def main() -> int:
    parser = argparse.ArgumentParser(description="multi-process flood probe for a running FOOTBALL OS API")
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8100")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--rps", type=int, default=12, help="requests per second per worker")
    parser.add_argument("--burst", type=int, default=200, help="simultaneous requests per worker")
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    if args.workers < 2 or args.duration <= 0 or args.rps < 1 or args.burst < 1:
        print("workers>=2, duration>0, rps>=1, burst>=1 are required", file=sys.stderr)
        return 2

    base = args.base_url.rstrip("/")
    specs = [
        {"base": base, "worker": index, "duration": args.duration, "rps": args.rps, "burst": args.burst}
        for index in range(args.workers)
    ]
    print(f"# flood{' (' + args.label + ')' if args.label else ''} base={base} "
          f"workers={args.workers} duration={args.duration}s rps/worker={args.rps} burst/worker={args.burst}")
    started = time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        reports = list(pool.map(_worker, specs))
    elapsed = time.monotonic() - started

    codes: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    for report in reports:
        codes.update(report["codes"])
        errors.update(report["errors"])
    all_latencies: list[float] = [report["p99_ms"] for report in reports]
    total = sum(codes.values()) + sum(errors.values())
    server_errors = sum(count for code, count in codes.items() if code.startswith("5"))
    throttled = codes.get("429", 0)
    doors_after_flood = sum(1 for report in reports if report["after_flood"] == 200)

    result = {
        "target": base,
        "label": args.label,
        "shape": "multi-process clients, single-process target — client-side multi-node simulation",
        "elapsed_s": round(elapsed, 1),
        "workers": args.workers,
        "sustained_requests": sum(report["sustained_requests"] for report in reports),
        "burst_requests": sum(report["burst_requests"] for report in reports),
        "requests": total,
        "codes": dict(sorted(codes.items())),
        "transport_errors": dict(sorted(errors.items())),
        "server_errors": server_errors,
        "throttled": throttled,
        "doors_after_flood": f"{doors_after_flood}/{args.workers}",
        "worker_p99_ms": all_latencies,
        "mean_worker_p99_ms": round(statistics.mean(all_latencies), 1) if all_latencies else 0,
        "pass": server_errors == 0 and not errors and doors_after_flood == args.workers,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
