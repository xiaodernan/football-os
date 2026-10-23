"""Migration 0036 runs, and rewrites exactly the rows it names.

The video pipeline wrote `DONE` for a successful run; ADR-006's machine ends at `COMPLETED`. The
writer is fixed, but every database that ran the old pipeline still holds rows outside the state
machine — and a data migration that is never executed is a description, not a repair. This case
builds the two columns the revision touches, plants one row of each status, and runs the shipped
`upgrade()` and `downgrade()` through a real Alembic context on SQLite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

REVISION = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0036_jobs_done_to_completed.py"


def _revision() -> Any:
    assert REVISION.is_file(), f"the 0036 revision moved; this case reads {REVISION}"
    spec = importlib.util.spec_from_file_location("migration_0036", REVISION)
    assert spec and spec.loader, f"could not load {REVISION}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(direction: str) -> dict[str, str]:
    module = _revision()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE jobs (id VARCHAR(40) PRIMARY KEY, status VARCHAR(20) NOT NULL)"))
        connection.execute(
            sa.text("INSERT INTO jobs (id, status) VALUES ('done', 'DONE'), ('completed', 'COMPLETED'), ('failed', 'FAILED'), ('queued', 'QUEUED')")
        )
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, direction)()
        rows = connection.execute(sa.text("SELECT id, status FROM jobs")).all()
    engine.dispose()
    return {row.id: row.status for row in rows}


def test_the_upgrade_moves_every_done_row_into_the_state_the_adr_names() -> None:
    assert _run("upgrade") == {
        "done": "COMPLETED",
        "completed": "COMPLETED",
        "failed": "FAILED",
        "queued": "QUEUED",
    }, "0036 changed a row outside the DONE set, or left a DONE row behind"


def test_the_downgrade_is_the_inverse_at_this_point_in_the_history() -> None:
    module = _revision()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE jobs (id VARCHAR(40) PRIMARY KEY, status VARCHAR(20) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO jobs (id, status) VALUES ('done', 'DONE'), ('queued', 'QUEUED')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.downgrade()
        rows = {row.id: row.status for row in connection.execute(sa.text("SELECT id, status FROM jobs")).all()}
    engine.dispose()
    assert rows == {"done": "DONE", "queued": "QUEUED"}, f"the round trip left {rows!r}"
