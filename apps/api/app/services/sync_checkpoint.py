"""Persistent proof that a deterministic catalogue already matches its recipe."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SyncCheckpoint, utcnow


def recipe_hash(recipe: dict[str, Any], sources: Sequence[Path]) -> str | None:
    payload = json.dumps(recipe, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(payload)
    try:
        for path in sorted(sources, key=lambda item: item.name):
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    except OSError:
        return None
    return digest.hexdigest()


def dataset_fingerprint(
    session: Session,
    datasets: Iterable[tuple[str, Any, tuple[str, ...], tuple[str, ...]]],
) -> tuple[str, dict[str, int]]:
    """Hash ordered identity/content columns without materialising ORM entities."""
    digest = hashlib.sha256()
    counts: dict[str, int] = {}
    for name, model, columns, order_by in datasets:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        for column in columns:
            digest.update(column.encode("utf-8"))
            digest.update(b"\0")
        statement = select(*(getattr(model, column) for column in columns)).order_by(
            *(getattr(model, column) for column in order_by)
        )
        count = 0
        for values in session.execute(statement):
            encoded = json.dumps(tuple(values), ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
            count += 1
        counts[name] = count
        digest.update(b"\0")
    return digest.hexdigest(), counts


def load_checkpoint(session: Session, scope: str, recipe: str) -> SyncCheckpoint | None:
    row = session.get(SyncCheckpoint, scope)
    return row if row is not None and row.recipe_hash == recipe else None


def save_checkpoint(
    session: Session,
    *,
    scope: str,
    recipe: str,
    fingerprint: str,
    database_hash: str,
    row_counts: dict[str, int],
) -> None:
    row = session.get(SyncCheckpoint, scope)
    if row is None:
        row = SyncCheckpoint(scope=scope)
        session.add(row)
    row.recipe_hash = recipe
    row.fingerprint = fingerprint
    row.database_hash = database_hash
    row.row_counts = row_counts
    row.updated_at = utcnow()
