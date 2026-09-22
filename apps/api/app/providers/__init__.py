"""Provider abstraction (spec §45–46, §77, ADR-005).

Real providers activate only when credentials exist. Without keys the platform runs
in DEMO MODE with self-labelled, deterministic responses — never presented as real AI.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings
from app.services.video.vision import DemoVisionProvider

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


class RerankerProvider(Protocol):
    name: str

    def rerank(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        query_terms: dict[str, float],
        df: dict[str, int],
        total_docs: int,
        avg_doc_length: float,
    ) -> list[dict[str, Any]]: ...


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
    """Deterministic local embeddings: signed hashing trick over unigrams and bigrams.

    This is a *lexical* vector, not a semantic one — it is honest for the SQLite/DEMO
    path because hybrid retrieval pairs it with BM25 and the answer surface cites the
    chunk it used instead of the model's own opinion. A real embedding model replaces it
    as soon as a key exists (see OpenAIEmbeddingProvider), without a schema change: the
    column dimension stays 256 because text-embedding-3-* supports `dimensions`.
    """

    name = "hash-local"
    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math
        import re

        vectors: list[list[float]] = []
        for text in texts:
            words = [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]
            features = words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
            counts: dict[str, int] = {}
            for feature in features:
                counts[feature] = counts.get(feature, 0) + 1
            vector = [0.0] * self.dim
            for feature, count in counts.items():
                digest = hashlib.sha1(feature.encode()).hexdigest()  # noqa: S324 - non-crypto bucketing
                index = int(digest[:8], 16) % self.dim
                sign = 1.0 if int(digest[8:16], 16) % 2 == 0 else -1.0
                vector[index] += sign * math.log1p(count)
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([round(v / norm, 6) for v in vector])
        return vectors


class OpenAIEmbeddingProvider:
    """Real embeddings when a key is configured; otherwise never used (spec §45)."""

    name = "openai"

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dim: int = 256) -> None:
        self.api_key = api_key
        self.model = model
        self.dim = dim
        self.base_url = "https://api.openai.com/v1"
        self.fallback = HashingEmbeddingProvider()

    def embed(self, texts: list[str]) -> list[list[float]]:
        body = json.dumps({"model": self.model, "input": texts, "dimensions": self.dim}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310 - fixed provider endpoint
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("embedding_provider_failure %s — falling back to hash-local", type(exc).__name__)
            return self.fallback.embed(texts)
        rows = sorted(payload.get("data", []), key=lambda row: row.get("index", 0))
        vectors = [[float(v) for v in row["embedding"]] for row in rows]
        if len(vectors) != len(texts) or any(len(v) != self.dim for v in vectors):
            logger.warning("embedding_provider_shape_mismatch — falling back to hash-local")
            return self.fallback.embed(texts)
        return vectors


class FeatureReranker:
    """Deterministic cross-feature rerank of already-retrieved chunks (spec §29 'Reranking').

    A neural cross-encoder can replace this behind RerankerProvider; until then the
    features are declared and inspectable, so a ranking can be explained rather than
    asserted — which is the whole point of the citation surface.
    """

    name = "feature-local"
    weights = {"lexical": 0.42, "semantic": 0.33, "coverage": 0.17, "heading": 0.08}

    def rerank(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        query_terms: dict[str, float],
        df: dict[str, int],
        total_docs: int,
        avg_doc_length: float,
    ) -> list[dict[str, Any]]:
        from app.services.knowledge.text import bm25_score, coverage

        scored: list[dict[str, Any]] = []
        for candidate in candidates:
            terms = {str(k): float(v) for k, v in candidate.get("terms", {}).items()}
            lexical = bm25_score(
                query_terms,
                terms,
                doc_length=int(candidate.get("token_estimate", 0)) or 1,
                avg_doc_length=avg_doc_length,
                df=df,
                total_docs=total_docs,
            )
            semantic = max(0.0, float(candidate.get("similarity", 0.0)))
            covered = coverage(query_terms, terms)
            heading_bonus = 1.0 if _heading_matches(query, str(candidate.get("heading", ""))) else 0.0
            features = {
                "lexical": lexical,
                "semantic": semantic,
                "coverage": covered,
                "heading": heading_bonus,
            }
            row = dict(candidate)
            row["features"] = features
            row["rerank_score"] = round(
                self.weights["lexical"] * _squash(lexical) + self.weights["semantic"] * semantic + self.weights["coverage"] * covered + self.weights["heading"] * heading_bonus,
                6,
            )
            scored.append(row)
        scored.sort(key=lambda row: (-row["rerank_score"], row.get("document_slug", ""), row.get("ordinal", 0)))
        return scored


def _squash(value: float) -> float:
    return value / (1.0 + value) if value > 0 else 0.0


def _heading_matches(query: str, heading: str) -> bool:
    """Two shared content words between question and section heading is a real signal."""
    from app.services.knowledge.text import content_words

    query_words = {w for w in content_words(query) if len(w) > 3}
    heading_words = {w for w in content_words(heading) if len(w) > 3}
    return len(query_words & heading_words) >= 2


class LocalStorageProvider:
    """Filesystem storage behind the same contract object storage will use later.

    Keys are treated as relative paths and rejected if they try to escape the root, because the key
    is built partly from a user's filename. A real object store has no such directory to climb out of.
    """

    name = "local-fs"

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_dir).resolve()

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root) + os.sep):
            raise ValueError(f"storage key {key!r} escapes the storage root")
        return candidate

    def put(self, key: str, data: bytes, content_type: str) -> str:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        logger.info("stored %s (%d bytes, %s)", key, len(data), content_type)
        return self.url_for(key)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url_for(self, key: str) -> str:
        """A path the API serves under its own auth, never a public file URL."""
        return f"/api/v1/video/file/{key}"


def get_vision_provider() -> VisionProvider:
    """The demo provider measures pixels; a real model would be chosen here by credential."""
    if settings.anthropic_api_key or settings.openai_api_key:
        logger.warning("a vision model is not wired yet; staying on the demo provider (spec §45)")
    return DemoVisionProvider()


def get_storage_provider() -> StorageProvider:
    return LocalStorageProvider(settings.storage_dir)


def get_llm_provider() -> LLMProvider:
    if settings.openai_api_key:
        return OpenAIChatProvider(settings.openai_api_key, settings.openai_model)
    return MockLLMProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """A real embedding model is used the moment a key exists; the dimension never changes."""
    if settings.openai_api_key and settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embedding_model)
    return HashingEmbeddingProvider()


def get_reranker_provider() -> RerankerProvider:
    return FeatureReranker()


def provider_status() -> dict[str, Any]:
    """Which provider serves each surface, including the ones that are a labelled demo (spec §59)."""
    return {
        "demo_mode": settings.is_demo_mode,
        "llm": get_llm_provider().name,
        "embedding": get_embedding_provider().name,
        "reranker": get_reranker_provider().name,
        "vision": get_vision_provider().name,
        "storage": get_storage_provider().name,
        "football_data": "synthetic-world",
        "news": "synthetic-world" if not settings.news_api_key else "licensed-api",
    }
