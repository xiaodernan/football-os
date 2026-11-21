"""A tiny, token-conscious probe for the gpt-6.2-sol gateway.

Two modes:
  python scripts/probe_llm.py smoke   -> one small streaming call (validates reachability + usage)
  python scripts/probe_llm.py cache   -> stream vs non-stream, repeated prefix, reports cache fields

Never prints the API key. max_tokens kept small; the cache probe repeats the *same* prefix on
purpose to observe whether the gateway reports cached_tokens on the stream door.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))

from app.providers import OpenAIChatProvider  # noqa: E402

KEY = os.environ.get("OPENAI_API_KEY", "")
BASE = os.environ.get("OPENAI_BASE_URL", "https://api.aizzz.xyz/v1")
PROXY = os.environ.get("OPENAI_PROXY", "http://127.0.0.1:7897")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-6.2-sol")

if not KEY:
    print("NO KEY: set OPENAI_API_KEY in the environment first")
    sys.exit(1)

STABLE = (
    "You are the Football OS manual voice. Answer strictly from the manual text given. "
    "Never invent a feature. Cite the exact section heading. Keep the answer to one short "
    "paragraph. " * 60  # ~ a few thousand chars of stable prefix, intentionally identical each call
)
QUESTION = "Where do I start as a new reader? Answer in one short sentence."


def make(stream: bool) -> OpenAIChatProvider:
    return OpenAIChatProvider(
        api_key=KEY,
        model=MODEL,
        base_url=BASE,
        stream=stream,
        proxy=PROXY,
        price_in_per_mtok=0.15,
        price_out_per_mtok=0.60,
    )


def show(tag, r, started):
    print(f"[{tag}] provider={r.provider} model={r.model} demo={r.demo_mode}")
    print(f"[{tag}] in={r.input_tokens} out={r.output_tokens} cached={r.cached_input_tokens} "
          f"cache_reported={r.cache_reported} latency={int((time.time()-started)*1000)}ms")
    print(f"[{tag}] error={r.error!r} text={(r.text or '')[:120]!r}")


def smoke():
    started = time.time()
    r = make(True).complete(system=STABLE, prompt=QUESTION, max_tokens=60, temperature=0.3)
    show("stream", r, started)


def cache():
    # A stable system prefix; only the (short) user turn changes. Repeated calls should show
    # cached_input_tokens climbing if the gateway keyed on the shared prefix.
    for i in range(3):
        started = time.time()
        r = make(True).complete(system=STABLE, prompt=QUESTION, max_tokens=40, temperature=0.3)
        show(f"stream#{i+1}", r, started)
        time.sleep(0.3)
    for i in range(2):
        started = time.time()
        r = make(False).complete(system=STABLE, prompt=QUESTION, max_tokens=40, temperature=0.3)
        show(f"nonstream#{i+1}", r, started)
        time.sleep(0.3)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    {"smoke": smoke, "cache": cache}[mode]()
