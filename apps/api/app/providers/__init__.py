"""Provider abstraction (spec §45–46, §77, ADR-005).

Real providers activate only when credentials exist. Without keys the platform runs
in DEMO MODE with self-labelled, deterministic responses — never presented as real AI.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from app.core.config import settings

logger = logging.getLogger("football_os.providers")


@dataclass
class LlmResult:
    text: str
    provider: str
    model: str
    demo_mode: bool
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: int = 0
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    structured: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMProvider(Protocol):
    name: str

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4) -> LlmResult: ...


class EmbeddingProvider(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class VisionProvider(Protocol):
    name: str

    def analyze_frames(self, frames: list[bytes], *, task: str) -> dict[str, Any]: ...


class FootballDataProvider(Protocol):
    name: str
    available: bool


class NewsProvider(Protocol):
    name: str
    available: bool


class StorageProvider(Protocol):
    name: str

    def put(self, key: str, data: bytes, content_type: str) -> str: ...

    def url_for(self, key: str) -> str: ...


class MockLLMProvider:
    """DEMO MODE phrasing only. Recommendation logic lives in coach_engine."""

    name = "mock"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4) -> LlmResult:
        started = time.perf_counter()
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(prompt)
        except (json.JSONDecodeError, TypeError):
            payload = {"prompt": prompt}
        intent = str(payload.get("intent", "general"))
        lines = [
            f"[DEMO MODE — deterministic template, no model call] {intent}:",
            "This surface would be phrased by a language model once a provider key is configured.",
            "The underlying recommendation is computed by the rule-based coach engine and is not a placeholder.",
        ]
        latency = int((time.perf_counter() - started) * 1000)
        return LlmResult(
            text="\n".join(lines),
            provider=self.name,
            model="template-demo",
            demo_mode=True,
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=max(1, len("\n".join(lines)) // 4),
            latency_ms=latency,
        )


class OpenAIChatProvider:
    """Minimal, dependency-free chat completions adapter."""

    name = "openai"
    _PRICE_IN = 0.15 / 1_000_000 * 100  # gpt-4o-mini style defaults, USD per token batch
    _PRICE_OUT = 0.60 / 1_000_000 * 100

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4) -> LlmResult:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310 - fixed internal endpoint
                raw = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("openai_provider_failure %s", type(exc).__name__)
            return MockLLMProvider().complete(system=system, prompt=prompt, max_tokens=max_tokens, temperature=temperature)
        latency = int((time.perf_counter() - started) * 1000)
        usage = raw.get("usage", {})
        text = (raw.get("choices") or [{}])[0].get("message", {}).get("content", "")
        in_tok, out_tok = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
        est = in_tok * self._PRICE_IN / 100 + out_tok * self._PRICE_OUT / 100
        return LlmResult(
            text=text,
            provider=self.name,
            model=self.model,
            demo_mode=False,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency,
            estimated_cost_usd=round(est, 6),
            actual_cost_usd=round(est, 6),
        )


class HashingEmbeddingProvider:
    """Deterministic local embeddings for the SQLite/DEMO path (ADR-002 fallback).

    Not semantically strong; keeps the RAG interface honest until pgvector +
    a real embedding provider are wired in M2.
    """

    name = "hash-local"
    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math

        vectors: list[list[float]] = []
        for text in texts:
            counts: dict[str, int] = {}
            for token in "".join(c if c.isalnum() else " " for c in text.lower()).split():
                counts[token] = counts.get(token, 0) + 1
            vector = [0.0] * self.dim
            for token, count in counts.items():
                index = int(hashlib.sha1(token.encode()).hexdigest(), 16) % self.dim  # noqa: S324 - non-crypto hashing
                vector[index] += math.log1p(count)
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([round(v / norm, 6) for v in vector])
        return vectors


class LocalStorageProvider:
    """Filesystem storage behind the same contract object storage will use later."""

    name = "local-fs"

    def __init__(self, root: str | None = None) -> None:
        from pathlib import Path

        self.root = Path(root or (settings.database_url.split("//")[-1] and "."))

    def put(self, key: str, data: bytes, content_type: str) -> str:
        raise NotImplementedError("Lands with M5 video upload; interface pinned here (spec §45).")

    def url_for(self, key: str) -> str:
        raise NotImplementedError("Lands with M5 video upload.")


def get_llm_provider() -> LLMProvider:
    if settings.openai_api_key:
        return OpenAIChatProvider(settings.openai_api_key, settings.openai_model)
    return MockLLMProvider()


def get_embedding_provider() -> EmbeddingProvider:
    return HashingEmbeddingProvider()


def provider_status() -> dict[str, Any]:
    return {
        "demo_mode": settings.is_demo_mode,
        "llm": get_llm_provider().name,
        "embedding": get_embedding_provider().name,
        "vision": "none-yet",
        "football_data": "synthetic-world",
        "news": "synthetic-world" if not settings.news_api_key else "licensed-api",
    }
