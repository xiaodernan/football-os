"""Tokenisation and scoring primitives shared by keyword search and the reranker.

Pure functions over strings and lists so the retrieval layer behaves identically on
SQLite and PostgreSQL, and so evaluation numbers are reproducible.
"""

from __future__ import annotations

import math
import re

_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """
    a an and are as at be been but by can do does for from had has have how i if in
    into is it its me my of on or our so that the their them then there these they
    this to us was we were what when where which who will with you your
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if len(t) > 1]


def content_words(text: str) -> list[str]:
    """Tokens minus stopwords — what keyword relevance should actually count."""
    return [t for t in tokenize(text) if t not in STOPWORDS]


def term_frequencies(text: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    for token in content_words(text):
        counts[token] = counts.get(token, 0.0) + 1.0
    return counts


def phrase_tokens(text: str) -> list[str]:
    """Unigrams + bigrams. Bigrams are what make 'hand ball rule' and 'hand ball' differ."""
    words = content_words(text)
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def bm25_score(
    query_terms: dict[str, float],
    doc_terms: dict[str, float],
    *,
    doc_length: int,
    avg_doc_length: float,
    df: dict[str, int],
    total_docs: int,
    k1: float = 1.4,
    b: float = 0.72,
) -> float:
    """Okapi BM25 over the content words of one chunk."""
    if not doc_terms or total_docs <= 0 or avg_doc_length <= 0:
        return 0.0
    score = 0.0
    for term, q_weight in query_terms.items():
        frequency = doc_terms.get(term, 0.0)
        if frequency <= 0:
            continue
        document_frequency = df.get(term, 0)
        idf = math.log(1.0 + (total_docs - document_frequency + 0.5) / (document_frequency + 0.5))
        denominator = frequency + k1 * (1.0 - b + b * doc_length / avg_doc_length)
        score += idf * (frequency * (k1 + 1.0)) / denominator * q_weight
    return score


def reciprocal_rank_fusion(rankings: list[list[str]], *, k: int = 60) -> dict[str, float]:
    """Fuse ranked id lists into one score map (Cormack et al. style RRF)."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for position, item_id in enumerate(ranking):
            fused[item_id] = fused.get(item_id, 0.0) + 1.0 / (k + position + 1.0)
    return fused


def coverage(query_terms: dict[str, float], doc_terms: dict[str, float]) -> float:
    """Share of the query's weighted terms that appear in the chunk — reranker feature."""
    if not query_terms:
        return 0.0
    hit = sum(weight for term, weight in query_terms.items() if term in doc_terms)
    return hit / sum(query_terms.values())
