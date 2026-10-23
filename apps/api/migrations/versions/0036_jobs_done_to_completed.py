"""Jobs written as DONE join ADR-006's COMPLETED (M12, spec §47)

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-24 12:00:00

ADR-006 names one state machine: `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED | RETRYING`.
The video pipeline wrote `DONE` at the end of a successful run — a seventh state the ADR never
named, and one the job doors did not treat as terminal, so a finished video job could still be
answered as "cancelled". The writer now says `COMPLETED`; this revision rewrites the rows it
already left, so an existing database's finished jobs read as the state the machine defines
rather than being stranded outside every terminal answer.

The rewrite is the inverse of the upgrade: at this point in the history every COMPLETED row with
a video.analyse payload came from `DONE`, because the doors never wrote COMPLETED on success.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

_jobs = sa.table("jobs", sa.column("status", sa.String(length=20)))


def upgrade() -> None:
    op.execute(_jobs.update().where(_jobs.c.status == "DONE").values(status="COMPLETED"))


def downgrade() -> None:
    op.execute(_jobs.update().where(_jobs.c.status == "COMPLETED").values(status="DONE"))
