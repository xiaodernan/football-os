"""Store the tactical catalogue: upsert by slug, refuse anything that does not fit, delete nothing silently.

The same discipline `sync_world` applies to the generated world, adapted to a plan that is
authored rather than seeded (spec §65, §88):

* the plan is authoritative — a row the plan no longer produces is removed, so a renamed system
  cannot keep answering `/tactics/old-slug` with stale geometry;
* provenance is forced from `plan.PROVENANCE`, never trusted from the payload;
* every row is validated against the model's own columns *before* the transaction commits, and
  any failure rolls the whole sync back. A partially written catalogue would be browsable as if it
  were the complete 50 the M4 gate promises, which is the one state this milestone may not ship.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import TACTICS_DISCLAIMER, TacticalSystem
from app.services.tactics.analysis import CHANGES, METRIC_KEYS
from app.services.tactics.plan import PROVENANCE, SYSTEM_COUNT, fingerprint, planned_rows, system_path
from app.services.world.plan import world_id

TACTICS_GATE: Final[Mapping[str, int]] = {"tactical_systems": SYSTEM_COUNT}
TACTICS_TABLE: Final = "tactical_systems"

# Payload keys that become columns; everything else is stored inside `board`, verbatim.
COLUMN_KEYS: Final = frozenset(
    {
        "slug",
        "name",
        "formation",
        "temperament_key",
        "press_line_y",
        "block_depth",
        "defensive_narrowing",
    }
)

# Every column the table actually has, read from the model so this cannot disagree with it.
TABLE_COLUMNS: Final = frozenset(column.key for column in TacticalSystem.__table__.columns)
# Columns filled by the sync itself rather than by a payload key.
DERIVED_COLUMNS: Final = frozenset({"id", "board", "content_hash"} | {key for key in PROVENANCE if key in TABLE_COLUMNS})
WRITE_ONLY_COLUMNS: Final = frozenset({"created_at", "updated_at"})


def _payload_column_gaps(payload: Mapping[str, Any]) -> list[str]:
    """Payload keys that name a column but are not handled — a silent drop waiting to happen."""
    unhandled = TABLE_COLUMNS - COLUMN_KEYS - DERIVED_COLUMNS - WRITE_ONLY_COLUMNS
    missing = sorted(unhandled - set(payload))
    return [f"the table column {column!r} is never filled by the plan" for column in missing]


@dataclass
class TacticsSyncReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    errors: list[str] = field(default_factory=list)
    fingerprint: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def changed(self) -> int:
        return self.created + self.updated + self.removed

    def summary_line(self) -> str:
        return f"created={self.created} updated={self.updated} unchanged={self.unchanged} removed={self.removed}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "errors": self.errors,
            "fingerprint": self.fingerprint,
            **PROVENANCE,
            "disclaimer": TACTICS_DISCLAIMER,
        }


def _validate(planned: Any) -> list[str]:
    """Would this row fit the table? Column widths, finite metres, eleven positions per phase."""
    payload = planned.payload
    problems: list[str] = []
    slug = str(payload.get("slug", ""))
    if not slug or len(slug) > 160:
        problems.append(f"{planned.natural_key}: slug is empty or longer than 160")
    if len(str(payload.get("name", ""))) > 200:
        problems.append(f"{slug}: name longer than 200")
    if len(str(payload.get("formation", ""))) > 20:
        problems.append(f"{slug}: formation longer than 20")
    if len(str(payload.get("temperament_key", ""))) > 40:
        problems.append(f"{slug}: temperament_key longer than 40")
    for key in ("press_line_y", "block_depth", "defensive_narrowing"):
        value = payload.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            problems.append(f"{slug}: {key} = {value!r} is not a finite non-negative number")
    for phase in ("phase_in", "phase_out"):
        positions = payload.get(phase)
        if not isinstance(positions, list) or len(positions) != 11:
            problems.append(f"{slug}: {phase} holds {len(positions) if isinstance(positions, list) else '?'} positions, not 11")
            continue
        if any(not isinstance(row, Mapping) or not {"x", "y", "role", "band"} <= set(row) for row in positions):
            problems.append(f"{slug}: {phase} has a position without role/band/x/y")
    for metric_key in ("metrics_in", "metrics_out"):
        metrics = payload.get(metric_key)
        if not isinstance(metrics, list) or {str(row.get("key")) for row in metrics if isinstance(row, Mapping)} != set(METRIC_KEYS):
            problems.append(f"{slug}: {metric_key} does not hold the eight measured metrics")
    if payload.get("counterfactuals") != [change.to_dict() for change in CHANGES.values()]:
        problems.append(f"{slug}: the counterfactual list does not match the offered changes")
    if payload.get("path") != system_path(slug):
        problems.append(f"{slug}: path does not match the §80 route table")
    return problems


def _columns_for(planned: Any) -> dict[str, Any]:
    """Split a payload into table columns and the `board` artefact, and only into those.

    Keys are matched against the model itself: a plan field that is not a column becomes part of
    the stored board, and one that *is* a column but is not in `COLUMN_KEYS` is a drift bug that
    `_validate` reports rather than something that silently reaches the constructor.
    """
    payload = dict(planned.payload)
    board = {key: value for key, value in payload.items() if key not in TABLE_COLUMNS and key != "natural_key"}
    columns: dict[str, Any] = {key: payload[key] for key in COLUMN_KEYS}
    columns.update(
        {
            "id": world_id("tactical_system", planned.natural_key),
            "board": board,
            "content_hash": planned.content_hash,
        }
    )
    columns.update({key: value for key, value in PROVENANCE.items() if key in TABLE_COLUMNS})
    return columns


def sync_tactics(session: Session, *, force: bool = False) -> TacticsSyncReport:
    """Bring the table in line with the plan. Returns a report; raises nothing."""
    report = TacticsSyncReport(fingerprint=fingerprint())
    planned = planned_rows()

    problems = _payload_column_gaps(planned[0].payload if planned else {})
    problems += [problem for row in planned for problem in _validate(row)]
    if len(planned) != SYSTEM_COUNT:
        problems.append(f"the plan produced {len(planned)} systems, not {SYSTEM_COUNT}")
    if problems:
        report.errors = sorted(set(problems))
        session.rollback()
        return report

    existing = {str(row.slug): row for row in session.scalars(select(TacticalSystem)).all()}
    wanted = {str(row.payload["slug"]): row for row in planned}

    for slug, row in wanted.items():
        columns = _columns_for(row)
        found = existing.get(slug)
        if found is None:
            session.add(TacticalSystem(**columns))
            report.created += 1
            continue
        if force or found.content_hash != columns["content_hash"]:
            for key, value in columns.items():
                if key != "id":
                    setattr(found, key, value)
            report.updated += 1
        else:
            report.unchanged += 1

    stale = sorted(set(existing) - set(wanted))
    if stale:
        session.execute(delete(TacticalSystem).where(TacticalSystem.slug.in_(stale)))
        report.removed = len(stale)

    try:
        session.commit()
    except SQLAlchemyError as error:  # pragma: no cover - a driver-level surprise
        session.rollback()
        report.errors = [f"commit failed: {error}"]
    return report


def tactics_tables_present(session: Session) -> bool:
    """Cheap, side-effect-free check that migration 0004 has run on this database."""
    try:
        return inspect(session.get_bind()).has_table(TACTICS_TABLE)
    except Exception:  # a half-initialised database must read as "not ready", not as a 500
        return False


def tactics_counts(session: Session) -> dict[str, int]:
    if not tactics_tables_present(session):
        return dict.fromkeys(TACTICS_GATE, 0)
    return {"tactical_systems": int(session.scalar(select(func.count()).select_from(TacticalSystem)) or 0)}


def tactics_ready(session: Session) -> bool:
    """True only when the whole catalogue is on this database — 49 systems is not the M4 gate."""
    counts = tactics_counts(session)
    return all(counts[name] >= floor for name, floor in TACTICS_GATE.items())


def stored_system(session: Session, ident: str) -> TacticalSystem | None:
    """Look a row up by slug or by public id; the web tier links by slug, API clients by id."""
    return session.scalar(select(TacticalSystem).where((TacticalSystem.slug == ident) | (TacticalSystem.id == ident)))
