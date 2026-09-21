"""Portable embedding column (ADR-002, spec §28-§29).

`EmbeddingVector` is one declaration that becomes a real ``vector(256)`` column on
PostgreSQL — so pgvector's cosine operator and ANN index can be used — and a JSON array
on the SQLite dev fallback, where cosine is computed in-process. The rest of the code
never has to know which dialect it is running on.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

EMBEDDING_DIM = 256


def _pgvector_type(dim: int) -> Any:
    from pgvector.sqlalchemy import Vector  # imported lazily: SQLite path must not need it

    return Vector(dim)


class EmbeddingVector(TypeDecorator[list[float]]):
    """list[float] in Python; ``vector(dim)`` in Postgres, JSON in SQLite."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == postgresql.dialect.name:
            return dialect.type_descriptor(_pgvector_type(self.dim))
        return dialect.type_descriptor(JSON())

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return None
        # pgvector hands back floats, SQLite hands back the JSON array; normalise both.
        return [float(x) for x in value]

    def compare_values(self, x: Any, y: Any) -> bool:
        if x is None or y is None:
            return x is y
        if len(x) != len(y):
            return False
        return all(abs(float(a) - float(b)) < 1e-6 for a, b in zip(x, y, strict=True))

    def __repr__(self) -> str:
        return f"EmbeddingVector(dim={self.dim})"
