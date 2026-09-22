"""Upsert a generated world into the tables — the M2 ingest pattern applied to rows.

`sync_world` walks the plan parent-first (competitions → teams → players → matches → stat lines →
training sessions → articles → links), matches every row on its natural key, and compares `content_hash`. So a re-run
against an unchanged seed is provably create 0 / update 0 / remove 0, which is what lets the
lifespan call it on boot without turning startup into a rewrite of ~3,900 rows.

Two honesty rules live here rather than in the builder:

* provenance is forced, not trusted: `data_origin='synthetic'` and `is_demo_data=True` are written
  onto every row even if a plan somehow forgot them;
* a plan that does not fit the schema is an error, never a truncation. Column drift, missing
  required columns, over-long values and rows under the spec §65 gate are collected into
  `report.errors` and the transaction is rolled back, so a half-written world cannot be browsed as
  though it were real.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    WORLD_DISCLAIMER,
    Competition,
    NewsArticle,
    NewsArticleLink,
    RealMatch,
    RealPlayer,
    RealPlayerMatchStat,
    RealTrainingSession,
    Team,
)
from app.services.world.builder import STAT_METHOD, WorldSizes, plan_world
from app.services.world.plan import Planned, WorldPlan, duplicate_keys, world_id

DELETE_CHUNK: Final = 400
PROVENANCE: Final[dict[str, Any]] = {"data_origin": "synthetic", "is_demo_data": True}


@dataclass(frozen=True)
class Collection:
    """How one planned dataset maps onto one table."""

    name: str
    kind: str
    model: Any
    key_columns: Sequence[str]
    hash_column: str | None = "content_hash"

    def columns_for(self, planned: Planned) -> dict[str, Any]:
        payload = dict(planned.payload)
        for column in self.key_columns:
            payload.setdefault(column, planned.natural_key)
        payload["id"] = world_id(self.kind, planned.natural_key)
        payload.update(PROVENANCE)
        if self.hash_column:
            payload[self.hash_column] = planned.content_hash
        return payload

    def key_of(self, values: dict[str, Any]) -> str:
        return "|".join(str(values[column]) for column in self.key_columns)

    def key_of_row(self, row: Any) -> str:
        return "|".join(str(getattr(row, column)) for column in self.key_columns)


COLLECTIONS: Final[tuple[Collection, ...]] = (
    Collection("competitions", "competition", Competition, ("slug",)),
    Collection("teams", "team", Team, ("slug",)),
    Collection("players", "player", RealPlayer, ("slug",)),
    Collection("matches", "match", RealMatch, ("slug",)),
    Collection("stat_lines", "stat_line", RealPlayerMatchStat, ("natural_key",)),
    Collection("training_sessions", "training_session", RealTrainingSession, ("natural_key",)),
    Collection("articles", "article", NewsArticle, ("slug",)),
    Collection("article_links", "article_link", NewsArticleLink, ("article_id", "entity_type", "entity_slug"), hash_column=None),
)
COUNT_MODELS: Final[dict[str, Any]] = {
    "competitions": Competition,
    "teams": Team,
    "players": RealPlayer,
    "matches": RealMatch,
    "training_sessions": RealTrainingSession,
    "articles": NewsArticle,
}
WORLD_TABLES: Final = tuple(str(collection.model.__tablename__) for collection in COLLECTIONS)
GATE: Final[dict[str, int]] = {"competitions": 10, "teams": 20, "players": 300, "matches": 100, "training_sessions": 100, "articles": 500}


@dataclass
class WorldSyncReport:
    """The M3 twin of `IngestReport`: what the world build did, and whether it may be trusted."""

    seed: int = 0
    version: str = ""
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    errors: list[str] = field(default_factory=list)
    per_collection: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def changed(self) -> int:
        return self.created + self.updated + self.removed

    @property
    def rows(self) -> int:
        return sum(stats["planned"] for stats in self.per_collection.values())

    def tally(self, name: str) -> dict[str, int]:
        return self.per_collection.setdefault(name, {"planned": 0, "created": 0, "updated": 0, "unchanged": 0, "removed": 0})

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self) | {
            "ok": self.ok,
            "changed": self.changed,
            "rows": self.rows,
            "demo_data": True,
            "data_origin": "synthetic",
            "disclaimer": WORLD_DISCLAIMER,
            "stat_method": STAT_METHOD,
        }

    def summary_line(self) -> str:
        parts = [f"{name} {stats['created']}+/ {stats['updated']}~ {stats['unchanged']}=" for name, stats in self.per_collection.items()]
        return f"seed={self.seed} created={self.created} updated={self.updated} unchanged={self.unchanged} removed={self.removed} ({'; '.join(parts)})"


def plan_problems(plan: WorldPlan) -> list[str]:
    """Reject an incomplete or self-colliding build before a single row reaches the database."""
    problems = [f"{name}: {len(plan.collections[name])} rows is under the spec §65 gate of {floor}" for name, floor in GATE.items() if len(plan.collections[name]) < floor]
    for collection in COLLECTIONS:
        rows = plan.collections[collection.name]
        duplicates = duplicate_keys(rows)
        if duplicates:
            problems.append(f"{collection.name}: {len(duplicates)} colliding natural keys, e.g. {duplicates[0]}")
        for row in rows:
            if len(row.natural_key) > 280:
                problems.append(f"{collection.name}: natural key {row.natural_key[:60]}… is {len(row.natural_key)} characters")
    return problems


def _validate(collection: Collection, planned: Planned) -> list[str]:
    """Refuse a plan that does not fit the schema instead of letting the driver truncate it."""
    columns = collection.model.__table__.c
    payload = collection.columns_for(planned)
    prefix = f"{collection.name} {planned.natural_key}"
    problems = [f"{prefix}: plan writes unknown column '{name}'" for name in sorted(set(payload) - set(columns.keys()))]
    for column in columns:
        if column.primary_key or column.name in {"created_at", "updated_at"}:
            continue
        if not column.nullable and column.default is None and column.server_default is None and column.name not in payload:
            problems.append(f"{prefix}: required column '{column.name}' is missing from the plan")
    for name, value in payload.items():
        column = columns.get(name)
        if column is None:
            continue
        if value is None and not column.nullable:
            problems.append(f"{prefix}: column '{name}' is NOT NULL but the plan gives None")
            continue
        length = getattr(column.type, "length", None)
        if length and isinstance(value, str) and len(value) > length:
            problems.append(f"{prefix}: '{name}' is {len(value)} characters, over the {length} column limit")
    return problems


def _upsert(session: Session, collection: Collection, rows: Iterable[Planned], report: WorldSyncReport, *, force: bool) -> None:
    stats = report.tally(collection.name)
    existing = {collection.key_of_row(row): row for row in session.scalars(select(collection.model)).all()}
    wanted: set[str] = set()
    for planned in rows:
        problems = _validate(collection, planned)
        if problems:
            report.errors.extend(problems)
            continue
        columns = collection.columns_for(planned)
        key = collection.key_of(columns)
        wanted.add(key)
        stats["planned"] += 1
        current = existing.get(key)
        if current is None:
            session.add(collection.model(**columns))
            stats["created"] += 1
            continue
        if collection.hash_column:
            unchanged = not force and getattr(current, collection.hash_column) == planned.content_hash
        else:
            unchanged = not force and all(getattr(current, name) == value for name, value in columns.items())
        if unchanged:
            stats["unchanged"] += 1
            continue
        for name, value in columns.items():
            if name != "id":
                setattr(current, name, value)
        stats["updated"] += 1
    stale = [row.id for key, row in existing.items() if key not in wanted]
    for offset in range(0, len(stale), DELETE_CHUNK):
        session.execute(delete(collection.model).where(collection.model.id.in_(stale[offset : offset + DELETE_CHUNK])))
    stats["removed"] = len(stale)
    report.created += stats["created"]
    report.updated += stats["updated"]
    report.unchanged += stats["unchanged"]
    report.removed += stats["removed"]
    session.flush()


def sync_world(session: Session, *, seed: int | None = None, sizes: WorldSizes | None = None, force: bool = False) -> WorldSyncReport:
    """Create or refresh the synthetic world. Returns a report; never raises at the caller."""
    world_seed = settings.world_seed if seed is None else seed
    report = WorldSyncReport(seed=world_seed)
    try:
        plan = plan_world(world_seed, sizes or WorldSizes())
    except Exception as exc:  # a generation bug belongs in the report, not in a 500
        report.errors.append(f"plan failed: {type(exc).__name__}: {exc}")
        return report
    report.version = plan.version
    problems = plan_problems(plan)
    if problems:
        report.errors.extend(problems)
        return report
    try:
        for collection in COLLECTIONS:
            _upsert(session, collection, plan.collections[collection.name], report, force=force)
    except SQLAlchemyError as exc:
        session.rollback()
        report.errors.append(f"database rejected the world build: {type(exc).__name__}: {exc}")
        return report
    if report.errors:
        session.rollback()
        return report
    session.commit()
    return report


def world_tables_present(session: Session) -> bool:
    """Cheap, side-effect-free check that migration 0003 has run on this database."""
    inspector = inspect(session.get_bind())
    return all(inspector.has_table(table) for table in WORLD_TABLES)


def world_counts(session: Session) -> dict[str, int]:
    if not world_tables_present(session):
        return dict.fromkeys(GATE, 0)
    return {name: int(session.scalar(select(func.count()).select_from(model)) or 0) for name, model in COUNT_MODELS.items()}


def world_ready(session: Session) -> bool:
    """True only when the tables exist *and* hold a full demo world on this database."""
    counts = world_counts(session)
    return all(counts[name] >= floor for name, floor in GATE.items())


__all__ = [
    "COLLECTIONS",
    "GATE",
    "WorldSyncReport",
    "plan_problems",
    "sync_world",
    "world_counts",
    "world_ready",
    "world_tables_present",
]
