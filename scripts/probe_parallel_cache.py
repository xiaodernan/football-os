"""Parallel-session cache stability probe on gpt-6.2-sol.

The user's concern: do parallel sessions hitting the gateway at once fragment the prefix
cache and drop the hit rate? This fires N concurrent requests sharing one byte-identical
system prefix (the real charter), then a second wave, and reports the cached-token share
per wave. max_tokens is tiny — this is about cache metadata, not generation.

Usage: set the OPENAI_API_KEY env var, then: python scripts/probe_parallel_cache.py [N]
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))

from app.providers import OpenAIChatProvider  # noqa: E402
from app.services.knowledge.answer import SYSTEM_CHARTER  # noqa: E402

KEY = os.environ.get("OPENAI_API_KEY", "")
BASE = os.environ.get("OPENAI_BASE_URL", "https://api.aizzz.xyz/v1")
PROXY = os.environ.get("OPENAI_PROXY", "")  # no proxy by default: the owner removed the Clash Verge dependency
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4


def call(idx: int) -> dict:
    p = OpenAIChatProvider(KEY, "gpt-6.2-sol", base_url=BASE, stream=True, proxy=PROXY)
    r = p.complete(system=SYSTEM_CHARTER, prompt="Reply with exactly: OK", max_tokens=6, temperature=0.2)
    return {"idx": idx, "in": r.input_tokens, "cached": r.cached_input_tokens,
            "reported": r.cache_reported, "demo": r.demo_mode, "err": r.error}


def wave(label: str) -> None:
    started = time.perf_counter()
    # Sequential provider objects in a thread pool — each is an independent "session" hitting the
    # same gateway with the same prefix. The gateway keys on the prefix bytes, not on any session id.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=N) as ex:
        rows = list(ex.map(call, range(N)))
    cached_total = sum(r["cached"] for r in rows)
    in_total = sum(r["in"] for r in rows)
    share = cached_total / in_total if in_total else 0.0
    print(f"[{label}] N={N} elapsed={int((time.perf_counter()-started)*1000)}ms "
          f"cached={cached_total}/{in_total} share={share:.1%} "
          f"reported={sum(1 for r in rows if r['reported'])}/{N} "
          f"errors={sum(1 for r in rows if r['err'])}")
    for r in rows:
        print(f"  #{r['idx']} in={r['in']} cached={r['cached']} demo={r['demo']} err={r['err']!r}")


if __name__ == "__main__":
    if not KEY:
        print("NO KEY")
        sys.exit(1)
    print(f"prefix chars={len(SYSTEM_CHARTER)} ~tokens={len(SYSTEM_CHARTER)//4}")
    wave("cold-wave")
    wave("warm-wave")
