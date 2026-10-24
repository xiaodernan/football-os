"""M13 item 2: tactical_shift_minute on sim_matches

Revision ID: 0038
Revises: 0037
Create Date: 2026-10-25 01:45:00.000000

The match engine gained an optional `tactical_shift_minute: int = 0` input (M13 item 2): from a set
minute the side trailing on goals pushes, recomputing possession share. A stored match must keep the
minute it was played with so `replay_is_identical` rebuilds the same `MatchInputs` — a replay that
silently drops the shift would compare two different fixtures and blame the model.

Same SQLite-safe pattern as 0037: nullable first, backfill to 0, then NOT NULL through batch mode, no
`server_default` (the model declares the Python-side default; a server default it does not know about is
what `alembic check` flags as drift).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sim_matches", sa.Column("tactical_shift_minute", sa.Integer(), nullable=True))
    op.execute("UPDATE sim_matches SET tactical_shift_minute = 0 WHERE tactical_shift_minute IS NULL")
    with op.batch_alter_table("sim_matches") as batch:
        batch.alter_column("tactical_shift_minute", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("sim_matches") as batch:
        batch.alter_column("tactical_shift_minute", existing_type=sa.Integer(), nullable=True)
    op.drop_column("sim_matches", "tactical_shift_minute")
