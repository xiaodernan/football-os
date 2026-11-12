"""The queue's claim sorts in memory; give the index its third column

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-12 20:55:00

`claim()` — and `requeue_expired()`, which orders the same way — reads
`WHERE status='QUEUED' ORDER BY created_at, id`. The index was `(status, created_at)`, so the planner
used it for the filter and the first sort term and then built a temporary B-tree for `id`:

    SEARCH jobs USING INDEX ix_jobs_status_created (status=?)
    USE TEMP B-TREE FOR LAST TERM OF ORDER BY

`id` is a `String(40)` primary key, not SQLite's rowid, so it is not free. Adding it to the index makes
the whole ORDER BY index-served. The cost is a wider index over a table that holds one row per job; the
benefit is that a claim never sorts — which matters because the claim is the queue's only hot path and it
runs on every worker tick, busy or idle.

SQLite and PostgreSQL both accept `DROP INDEX` + `CREATE INDEX` here; no batch rewrite is needed because
the table is not rebuilt.
"""

from __future__ import annotations

from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_status_created", table_name="jobs")
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"], unique=False)
