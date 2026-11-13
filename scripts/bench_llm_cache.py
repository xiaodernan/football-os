"""Measure what the configured chat gateway actually reports about its prefix cache.

The complaint this script exists to answer is "the cache hit rate is low and every call shows
non-stream". Both halves are measurable in one run, and neither is answerable from the code: the
gateway's cache is its own, and what it does with a request is only visible in the `usage` object it
returns. So this script sends the same prefix twice in each of several shapes and prints the number
the gateway itself printed, with no interpretation layered on top.

Usage:
    python scripts/bench_llm_cache.py                # the standard matrix
    python scripts/bench_llm_cache.py --repeats 4    # more samples per cell
    python scripts/bench_llm_cache.py --json         # machine-readable, for a doc or a diff

What each column means:

* `prompt` — `usage.prompt_tokens` as reported. On a gateway that injects a preamble this is much
  larger than the text the caller sent; on this host it is ~4 400 tokens larger. It is the number
  the operator is billed for, so it is the denominator of the only ratio that costs money.
* `cached` — `prompt_tokens_details.cached_tokens` (OpenAI dialect) or `prompt_cache_hit_tokens`
  (DeepSeek dialect). `-` means the gateway printed no details field at all, which is a third state
  and must not be read as "zero cached": a zero is a measurement, an absent field is silence.
* `ratio` — `cached / prompt`. Blank when the gateway was silent.

The three prefixes are the two this project ships (`knowledge` 344 chars, `coach` 673 chars) and a
long stable contract, so a reader can see whether size is what the cache cares about on this host.

Exit status is 0 for a completed run even when every cell is a miss: a bench that fails when the
gateway is cold would be a bench nobody runs. It exits 2 when no key is configured, because then
there is nothing to measure and silence would read as success.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

QUESTION = "In one sentence, what should a pressing forward do when the ball goes back to the keeper?"

LONG_CONTRACT = (
    "You are the football knowledge assistant inside FOOTBALL OS. Answer only from the numbered passages "
    "provided, cite them inline as [1], [2], and say what you cannot support from the passages instead of "
    "inventing it.\n\nThe answer contract, with worked examples. Each example shows a question, the passage "
    "it rests on, and the shape of a correct answer: first sentence answers the question, the citation "
    "follows the claim, and a gap is named rather than filled.\n\n"
) + "".join(
    "Example {i}.\n"
    "Question: How should the far-side forward react when the ball is switched quickly?\n"
    "Passage: [1] On a switch of play the far-side forward's first job is to hold width until the ball "
    "travels, then attack the space behind the recovering full-back.\n"
    "Answer: Hold your width until the ball is in flight, then attack the space behind the recovering "
    "full-back [1]. If the switch is slow, do not leave early; the space closes before the ball arrives.\n\n".format(i=i)
    for i in range(1, 6)
)


@dataclass
class Sample:
    label: str
    mode: str
    attempt: int
    prompt_tokens: int
    cached_tokens: int | None
    output_tokens: int
    latency_ms: int
    text_chars: int

    @property
    def ratio(self) -> float | None:
        if self.cached_tokens is None or not self.prompt_tokens:
            return None
        return self.cached_tokens / self.prompt_tokens


def _prefixes() -> list[tuple[str, str]]:
    from app.services import coach_voice
    from app.services.knowledge.answer import SYSTEM_PROMPT

    return [
        ("knowledge (shipped)", SYSTEM_PROMPT),
        ("coach (shipped)", coach_voice.SYSTEM),
        ("long contract", LONG_CONTRACT),
    ]


def _usage_tokens(usage: dict[str, Any]) -> tuple[int, int, int | None]:
    details = usage.get("prompt_tokens_details")
    nested = details if isinstance(details, dict) else {}
    prompt = int(usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0) or 0)
    output = int(usage.get("completion_tokens", 0) or usage.get("output_tokens", 0) or 0)
    if "cached_tokens" in nested:
        cached: int | None = int(nested.get("cached_tokens") or 0)
    elif "prompt_cache_hit_tokens" in usage:
        cached = int(usage.get("prompt_cache_hit_tokens") or 0)
    else:
        cached = None
    return prompt, output, cached


def _post(base_url: str, key: str, model: str, ua: str | None, body: dict[str, Any], *, stream: bool) -> tuple[dict[str, Any], int, str]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            **({"User-Agent": ua} if ua else {}),
        },
    )
    started = time.perf_counter()
    usage: dict[str, Any] = {}
    text = ""
    with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310 - configured endpoint
        if not stream:
            raw = json.loads(response.read().decode())
            usage = raw.get("usage") or {}
            text = ((raw.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        else:
            for raw_line in response:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                for choice in event.get("choices") or []:
                    piece = (choice.get("delta") or {}).get("content")
                    if isinstance(piece, str):
                        text += piece
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
    return usage, int((time.perf_counter() - started) * 1000), text


def run(*, repeats: int, pause: float, base_url: str, key: str, model: str, ua: str | None) -> list[Sample]:
    samples: list[Sample] = []
    for label, system in _prefixes():
        for stream in (False, True):
            mode = "stream" if stream else "non-stream"
            body: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": QUESTION}],
                "max_tokens": 60,
                "temperature": 0.2,
                "stream": stream,
            }
            if stream:
                body["stream_options"] = {"include_usage": True}
            for attempt in range(1, repeats + 1):
                try:
                    usage, latency, text = _post(base_url, key, model, ua, body, stream=stream)
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                    print(f"  {label:<22} {mode:<11} #{attempt}: failed — {type(exc).__name__}", file=sys.stderr)
                    continue
                prompt, output, cached = _usage_tokens(usage)
                samples.append(
                    Sample(
                        label=label,
                        mode=mode,
                        attempt=attempt,
                        prompt_tokens=prompt,
                        cached_tokens=cached,
                        output_tokens=output,
                        latency_ms=latency,
                        text_chars=len(text),
                    )
                )
                time.sleep(pause)
    return samples


def render(samples: list[Sample]) -> None:
    print(f"{'prefix':<22} {'mode':<11} {'#':>2} {'prompt':>7} {'cached':>7} {'ratio':>7} {'out':>5} {'ms':>7}")
    print("-" * 80)
    for sample in samples:
        cached = "-" if sample.cached_tokens is None else str(sample.cached_tokens)
        ratio = "silent" if sample.ratio is None else f"{sample.ratio * 100:.1f}%"
        print(
            f"{sample.label:<22} {sample.mode:<11} {sample.attempt:>2} {sample.prompt_tokens:>7} "
            f"{cached:>7} {ratio:>7} {sample.output_tokens:>5} {sample.latency_ms:>7}"
        )


def verdict(samples: list[Sample]) -> None:
    """One paragraph of arithmetic, so the reader does not have to do it in their head."""
    warm = [s for s in samples if s.attempt > 1 and s.ratio is not None]
    silent = [s for s in samples if s.attempt > 1 and s.cached_tokens is None]
    if warm:
        best = max(warm, key=lambda s: s.ratio or 0.0)
        print(
            f"\nwarm repeats: {len(warm)} reported a cache figure, best {best.ratio * 100:.1f}% "
            f"({best.label}, {best.mode}); {len(silent)} printed no details field at all"
        )
    elif silent:
        print(f"\nwarm repeats: none reported a cache figure; {len(silent)} printed no details field at all")
    else:
        print("\nno warm repeat completed; nothing to conclude")
    sizes = sorted({(s.label, s.prompt_tokens) for s in samples if s.attempt == 1})
    if sizes:
        print("first-call prompt sizes as the gateway counted them: " + ", ".join(f"{label} {n}" for label, n in sizes))


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the chat gateway's prefix cache, per shape.")
    parser.add_argument("--repeats", type=int, default=2, help="calls per cell (default 2: one cold, one warm)")
    parser.add_argument("--pause", type=float, default=1.5, help="seconds between calls (default 1.5)")
    parser.add_argument("--json", action="store_true", help="print the samples as JSON instead of a table")
    args = parser.parse_args()

    from app.core.config import settings

    key = settings.openai_api_key
    if not key:
        print("No OPENAI_API_KEY configured; nothing to measure.", file=sys.stderr)
        return 2

    print(f"gateway={settings.openai_base_url} model={settings.openai_model} repeats={args.repeats}")
    samples = run(
        repeats=max(1, args.repeats),
        pause=max(0.0, args.pause),
        base_url=settings.openai_base_url,
        key=key,
        model=settings.openai_model,
        ua=settings.openai_user_agent,
    )
    if args.json:
        print(json.dumps([asdict(sample) | {"ratio": sample.ratio} for sample in samples], indent=2, ensure_ascii=False))
    else:
        render(samples)
        verdict(samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
