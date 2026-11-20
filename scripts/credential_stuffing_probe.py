"""A credential-stuffing probe against a live FOOTBALL OS API.

This is not a benchmark of how fast a login can be. It is an abuse test: many wrong passwords across
many addresses, fired concurrently at the two doors an attacker would actually knock on
(`/auth/login` and `/auth/register`), asking three questions of the system at once:

  1. **Does it stay up?** Any 5xx, reset or timeout under the burst is a finding — the auth door must
     answer, not collapse, when it is being hammered.
  2. **Does the limiter bite?** A password oracle is only as good as its budget; a stuffing burst must
     draw coded 429s with a `Retry-After`, not a stream of 401s forever.
  3. **Is the door still usable?** A real victim must be able to sign in after the burst ends. A limiter
     that locks everybody out, or state left poisoned by concurrent rotation, fails as surely as one that
     never fired.

Usage:
    python scripts/credential_stuffing_probe.py [base_url] [--concurrency N] [--attempts N]
        [--victim-password PASSWORD] [--label NAME]

The victim account is created for the run and deleted from the probe's own state afterwards; nothing in the
target is cleaned up (the API has no admin delete), so use a scratch database. Exit 0 only when all three
questions pass.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import string
import sys
import time
from collections import Counter
from typing import Any

import httpx

AUTH_LOGIN = "/api/v1/auth/login"
AUTH_REGISTER = "/api/v1/auth/register"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100) * len(ordered))) - 1))
    return ordered[k]


def _address(rng: random.Random, tag: str) -> str:
    return f"stuff-{tag}-{rng.getrandbits(48):012x}@example.test"


def _password(rng: random.Random) -> str:
    return "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(14))


async def _post(client: httpx.AsyncClient, base: str, path: str, payload: dict[str, Any]) -> tuple[int, float, dict[str, Any]]:
    started = time.perf_counter()
    try:
        response = await client.post(base + path, json=payload, timeout=15.0)
        latency = (time.perf_counter() - started) * 1000.0
        try:
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
            code = detail.get("code") if isinstance(detail, dict) else None
        except Exception:  # noqa: BLE001 — a non-JSON error body is itself a finding, not a crash of the probe.
            code = None
        return response.status_code, latency, {"code": code, "retry_after": response.headers.get("retry-after")}
    except Exception:  # noqa: BLE001 — a connection error is a 0 status and counts against availability.
        return 0, (time.perf_counter() - started) * 1000.0, {"code": "transport_error", "retry_after": None}


async def _burst(
    client: httpx.AsyncClient,
    base: str,
    path: str,
    attempts: int,
    concurrency: int,
    make_payload: Any,
    seed: int,
) -> tuple[Counter[int], list[float], int]:
    rng = random.Random(seed)
    semaphore = asyncio.Semaphore(concurrency)

    async def one(i: int) -> tuple[int, float, dict[str, Any]]:
        async with semaphore:
            return await _post(client, base, path, make_payload(rng, i))

    statuses: Counter[int] = Counter()
    latencies: list[float] = []
    coded_429 = 0
    for status, latency, meta in await asyncio.gather(*(one(i) for i in range(attempts))):
        statuses[status] += 1
        latencies.append(latency)
        if status == 429 and meta.get("code") == "rate_limited" and (meta.get("retry_after") or "").isdigit():
            coded_429 += 1
    return statuses, latencies, coded_429


def _report(label: str, statuses: Counter[int], latencies: list[float]) -> None:
    print(f"  {label}: " + " ".join(f"{code}={count}" for code, count in sorted(statuses.items())))
    print(
        f"     p50={percentile(latencies, 50):.1f}ms p90={percentile(latencies, 90):.1f}ms "
        f"p99={percentile(latencies, 99):.1f}ms avg={statistics.fmean(latencies):.1f}ms"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="credential-stuffing / high-concurrency auth probe")
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8100")
    parser.add_argument("--concurrency", type=int, default=48)
    parser.add_argument("--attempts", type=int, default=600)
    parser.add_argument("--victim-password", default="victim-pass-1234")
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    head = f"# credential-stuffing probe{' (' + args.label + ')' if args.label else ''}: base={base} concurrency={args.concurrency} attempts={args.attempts}"
    print(head)

    checks: list[tuple[str, bool, str]] = []
    async with httpx.AsyncClient() as client:
        # Health first: the probe is meaningless if the target was already down.
        health_response = await client.get(base + "/api/v1/healthz", timeout=10.0)
        health = health_response.status_code
        if health != 200:
            print(f"FAIL health={health} — target not up")
            return 2

        # A real victim account, created before the burst, to test availability after it.
        victim = _address(random.Random(7), "victim")
        created, _, _ = await _post(
            client,
            base,
            AUTH_REGISTER,
            {"email": victim, "password": args.victim_password, "display_name": "Stuffing Victim", "role": "coach", "accepts_data_policy": True},
        )
        if created not in (200, 201):
            # A 429 here means the door was already limited; wait for the window and retry once.
            await asyncio.sleep(65)
            created, _, _ = await _post(
                client,
                base,
                AUTH_REGISTER,
                {"email": victim, "password": args.victim_password, "display_name": "Stuffing Victim", "role": "coach", "accepts_data_policy": True},
            )
        print(f"victim register={created}")

        started = time.perf_counter()
        login_statuses, login_latencies, login_limited = await _burst(
            client,
            base,
            AUTH_LOGIN,
            args.attempts,
            args.concurrency,
            lambda rng, i: {"email": _address(rng, "login"), "password": _password(rng)},
            seed=1101,
        )
        register_statuses, register_latencies, register_limited = await _burst(
            client,
            base,
            AUTH_REGISTER,
            max(40, args.attempts // 10),
            args.concurrency,
            lambda rng, i: {"email": _address(rng, "reg"), "password": _password(rng), "display_name": "Ghost", "role": "coach", "accepts_data_policy": True},
            seed=1102,
        )
        elapsed = time.perf_counter() - started

        print()
        _report("login burst", login_statuses, login_latencies)
        _report("register burst", register_statuses, register_latencies)
        print(f"  elapsed={elapsed:.1f}s")

        all_statuses = login_statuses + register_statuses
        server_errors = sum(count for code, count in all_statuses.items() if code >= 500 or code == 0)
        checks.append(("no 5xx / transport failure under the burst", server_errors == 0, f"found {server_errors}"))
        checks.append(
            ("the limiter answered with coded 429 + Retry-After", (login_limited + register_limited) > 0, f"login={login_limited} register={register_limited}"),
        )

        # The limiter refills at 12/min; give it a window before testing the victim, so we measure
        # "the door is usable after an attack", not "the victim's own shared-budget bucket is still cold".
        await asyncio.sleep(65)
        victim_status, victim_latency, victim_meta = await _post(client, base, AUTH_LOGIN, {"email": victim, "password": args.victim_password})
        checks.append(
            ("the victim can still sign in after the burst", victim_status in (200, 201), f"status={victim_status} meta={victim_meta} latency={victim_latency:.1f}ms"),
        )

    print()
    verdict = True
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name} — {detail}")
        verdict = verdict and ok
    print("verdict:", "PASS" if verdict else "FAIL")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
