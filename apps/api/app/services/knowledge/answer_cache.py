"""The second identical question is free (M17, cache arc).

The knowledge door is the one place in this product where a real language model is called on a
read path, and it is also the one place where the same question arrives twice: a reader asks,
reads the answer, and asks it again from another tab, or a colleague asks the same thing an hour
later, or the reader's own browser retries a request it never saw finish. Every one of those calls
pays the full price of a prompt — and on the gateway this project is configured against, that
price is not the ~120 tokens of question and passages we send. The gateway prepends a preamble of
its own, measured at 4 386 tokens on this host, so one repeated question is roughly 4 500 input
tokens spent to produce a paragraph the platform already had.

**What this keys on, and why.** An answer is a function of four things: the question, the passages
it was grounded in, the model that phrased it, and the language contract (the system prompt). The
key is the SHA-256 of exactly those four, in a fixed order, with the question normalised
(case-folded, NFKC, whitespace collapsed, terminal punctuation dropped). Two questions that differ
only in spelling or a trailing question mark retrieve the same passages and deserve the same
answer; two questions that retrieve *different* passages are different questions even when the
words are the same, because the citation list is part of the key. That is the property that makes
this cache honest: a stored answer can only ever be served with the exact evidence it was written
from, and `AnswerResult.citations` is rebuilt every time — the cache stores prose, never a citation.

**What it never stores.** A refusal. `answered=False` is the retrieval layer saying it has nothing,
which is cheap to recompute and must stay fresh: a corpus that gains a passage tonight should
answer tomorrow. Demo-mode answers are not cached either — they are a pure function of the passages
and cost nothing, so a cache would only add a way to serve a stale one.

**Coalescing.** Two readers asking the same new question at the same moment would both miss and
both pay. `single_flight` serialises them per key and the second one re-reads the cache under the
lock, so the pair costs one call. The lock table is a dict of counters, not a global lock: a cache
hit on key A must never wait behind a slow miss on key B.

**Where it lives.** `app.core.redis_cache` — Redis when a deployment has one, the process's own
LRU when it does not, and the same `get`/`set`/TTL surface either way. A multi-worker deployment
therefore shares the hits; a single process gets the same behaviour with a smaller ceiling. The
in-memory tier is also written on a Redis write (that client always writes both), so a Redis
outage degrades to per-process hits rather than to nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Final

from app.core.config import settings
from app.core.redis_cache import get_redis_cache

#: Bumped by hand whenever the phrasing contract changes shape. An answer written under the old
#: contract is not an answer to the new one, and a key that cannot say so would serve it.
CACHE_VERSION: Final = "knowledge-answer-v1"

_KEY_PREFIX: Final = "knowledge:answer:"
_TERMINAL_PUNCTUATION: Final = "?!.。？！;；:： \t\n"

_hits = 0
_misses = 0
_stores = 0
_coalesced = 0
_counters_lock = threading.Lock()

#: key -> [lock, participants]. A participant is a thread that is holding or waiting for the lock;
#: the entry is dropped when the last one leaves, so the table is bounded by concurrency, not by
#: the number of questions the process has ever been asked.
_inflight: dict[str, list[Any]] = {}
_inflight_guard = threading.Lock()


def normalise_question(question: str) -> str:
    """The spelling-insensitive form a question is cached under.

    Case, width, surrounding whitespace and terminal punctuation are not meaning: "How should a
    six press?" and "how should a six press" are one question. Words are — nothing here touches
    them, and no stemming or synonym folding is attempted. A cache that decides two different
    questions are the same is a cache that answers the wrong one, and the retrieval layer already
    has the vocabulary control (`MIN_DISCRIMINATIVE_MATCHES`) to make near-duplicates collapse on
    their own.
    """
    folded = unicodedata.normalize("NFKC", question).casefold()
    collapsed = re.sub(r"\s+", " ", folded).strip()
    return collapsed.rstrip(_TERMINAL_PUNCTUATION).strip()


def cache_key(*, question: str, chunk_ids: list[str], model: str, locale: str) -> str:
    """The identity of one answer: this question, over these passages, phrased by this model.

    `chunk_ids` is sorted and de-duplicated, so the order retrieval happened to return them in
    cannot split one answer into two cache entries. The material is JSON with `sort_keys` and no
    ASCII escaping: a Chinese question hashes as itself rather than as its escapes, which keeps a
    cache dump readable in a Redis client.
    """
    material = json.dumps(
        {
            "version": CACHE_VERSION,
            "question": normalise_question(question),
            "chunks": sorted({chunk for chunk in chunk_ids if chunk}),
            "model": model,
            "locale": locale,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}{digest[:40]}"


def enabled() -> bool:
    return settings.knowledge_answer_cache_enabled


def ttl_seconds() -> float:
    return float(settings.knowledge_answer_cache_ttl_seconds)


def get(key: str) -> dict[str, Any] | None:
    """A stored answer, or None. Only entries written by this version are accepted.

    The version travels inside the key, so a stale entry from an older contract is unreachable
    rather than merely distrusted — belt and braces, because a rolled-back deploy would otherwise
    meet its own old entries and serve them.
    """
    global _hits, _misses
    if not enabled():
        return None
    stored = get_redis_cache().get(key)
    if not isinstance(stored, dict) or stored.get("version") != CACHE_VERSION:
        with _counters_lock:
            _misses += 1
        return None
    text = stored.get("text")
    if not isinstance(text, str) or not text.strip():
        with _counters_lock:
            _misses += 1
        return None
    with _counters_lock:
        _hits += 1
    return stored


def put(key: str, *, text: str, model: str, provider: str) -> None:
    global _stores
    if not enabled() or not text.strip():
        return
    get_redis_cache().set(
        key,
        {
            "version": CACHE_VERSION,
            "text": text,
            "model": model,
            "provider": provider,
            "ttl": int(ttl_seconds()),
        },
        ttl=ttl_seconds(),
    )
    with _counters_lock:
        _stores += 1


@contextmanager
def single_flight(key: str) -> Iterator[None]:
    """Hold the per-key lane for the duration of one provider call.

    A lock is created on first use and removed when its last participant leaves, so a long-running
    process accumulates nothing. The `coalesced` counter is incremented for a caller that arrived
    while somebody else held the lane: it is the number of provider calls this design avoided,
    which is the only number worth printing.
    """
    global _coalesced
    with _inflight_guard:
        entry = _inflight.get(key)
        waited = entry is not None
        if entry is None:
            entry = [threading.Lock(), 0]
            _inflight[key] = entry
        entry[1] += 1
    if waited:
        with _counters_lock:
            _coalesced += 1
    lock = entry[0]
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _inflight_guard:
            entry[1] -= 1
            if entry[1] <= 0:
                _inflight.pop(key, None)


def stats() -> dict[str, float]:
    """Counters this process has seen. Several workers each report their own, and the sum is the
    deployment's — the same convention `/metrics/cache` uses for the HTTP tier."""
    with _counters_lock:
        total = _hits + _misses
        return {
            "hits": _hits,
            "misses": _misses,
            "stores": _stores,
            "coalesced": _coalesced,
            "hit_rate": round(_hits / total, 4) if total else 0.0,
        }


def inflight_size() -> int:
    """How many lanes are open. A number a test can hold onto without reaching into `_inflight`."""
    with _inflight_guard:
        return len(_inflight)


def reset_stats() -> None:
    """Forget the counters (tests, and a process that wants a clean window)."""
    global _hits, _misses, _stores, _coalesced
    with _counters_lock:
        _hits = _misses = _stores = _coalesced = 0
