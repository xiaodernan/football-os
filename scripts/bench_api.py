"""Performance benchmarking suite (M12 Performance).

Runs configurable load tests against the API and reports latency percentiles, throughput,
and error rates. Designed to be run as a standalone script or in CI.

Usage:
    python -m scripts.bench_api [--concurrency N] [--duration SECONDS] [--endpoint PATH]

Example:
    python -m scripts.bench_api --concurrency 10 --duration 30 --endpoint /api/v1/healthz
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

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
            "error_rate": round(self.error_rate, 4),
            "errors_by_code": self.errors_by_code,
            "errors_by_type": self.errors_by_type,
        }


def percentile(sorted_values: list[float], percentile: float) -> float:
    """Nearest-rank percentile (same as latency_profile.py)."""
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, int(percentile / 100 * len(sorted_values) + 0.999999) - 1))
    return sorted_values[index]


async def make_request(client: httpx.AsyncClient, config: BenchmarkConfig) -> RequestResult:
    start = time.perf_counter()
    try:
        if config.method == "GET":
            response = await client.get(config.endpoint, headers=config.headers, timeout=config.timeout)
        elif config.method == "POST":
            response = await client.post(config.endpoint, headers=config.headers, json=config.json_body, timeout=config.timeout)
        else:
            return RequestResult(0, 0, f"Unsupported method: {config.method}")
        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(response.status_code, latency_ms)
    except httpx.TimeoutException:
        return RequestResult(0, (time.perf_counter() - start) * 1000, "timeout")
    except httpx.ConnectError as e:
        return RequestResult(0, (time.perf_counter() - start) * 1000, f"connection_error: {e}")
    except Exception as e:
        return RequestResult(0, (time.perf_counter() - start) * 1000, f"error: {type(e).__name__}: {e}")


async def worker(
    client: httpx.AsyncClient,
    config: BenchmarkConfig,
    results: list[RequestResult],
    stop_event: asyncio.Event,
) -> None:
    """Worker that continuously makes requests until stop_event is set."""
    while not stop_event.is_set():
        result = await make_request(client, config)
        results.append(result)


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run the benchmark with the given configuration."""
    limits = httpx.Limits(max_connections=config.concurrency, max_keepalive_connections=config.concurrency)
    timeout = httpx.Timeout(config.timeout)
    
    results: list[RequestResult] = []
    stop_event = asyncio.Event()
    
    async with httpx.AsyncClient(base_url=config.base_url, limits=limits, timeout=timeout) as client:
        # Warmup
        warmup_tasks = [make_request(client, config) for _ in range(min(5, config.concurrency))]
        await asyncio.gather(*warmup_tasks)
        
        # Start workers
        stop_event.clear()
        workers = [worker(client, config, [], asyncio.Event()) for _ in range(config.concurrency)]
        
        # Actually we'll use a simpler approach - spawn concurrent tasks
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
            except asyncio.TimeoutError:
                pass
        
        end_time = time.perf_counter()
    
    # Process results
    total_requests = len(all_results)
    successful = [r for r in all_results if 200 <= r.status_code < 400]
    failed = [r for r in all_results if not (200 <= r.status_code < 400)]
    
    latencies = sorted(r.latency_ms for r in successful)
    
    errors_by_code: dict[int, int] = {}
    errors_by_type: dict[str, int] = {}
    for r in failed:
        if r.status_code > 0:
            errors_by_code[r.status_code] = errors_by_code.get(r.status_code, 0) + 1
        else:
            error_type = r.error.split(":")[0] if r.error else "unknown"
            errors_by_type[error_type] = errors_by_type.get(error_type, 0) + 1
    
    total_duration = time.perf_counter() - start_time
    
    return BenchmarkResult(
        endpoint=config.endpoint,
        concurrency=config.concurrency,
        duration_seconds=config.duration_seconds,
        total_requests=total_requests,
        successful_requests=len(successful),
        failed_requests=len(failed),
        total_duration_seconds=total_duration,
        requests_per_second=total_requests / total_duration if total_duration > 0 else 0,
        error_rate=len(failed) / total_requests if total_requests > 0 else 0,
        latencies_ms=latencies,
        p50_ms=percentile(latencies, 50) if latencies else 0,
        p95_ms=percentile(latencies, 95) if latencies else 0,
        p99_ms=percentile(latencies, 99) if latencies else 0,
        max_ms=max(latencies) if latencies else 0,
        errors_by_code=errors_by_code,
        errors_by_type=errors_by_type,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="FOOTBALL OS API Performance Benchmark")
    parser.add_argument("--base-url", default="http://127.0.0.1:8731", help="Base URL of the API")
    parser.add_argument("--endpoint", default="/api/v1/healthz", help="Endpoint to benchmark")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--method", default="GET", choices=["GET", "POST"], help="HTTP method")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    
    args = parser.parse_args()
    
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