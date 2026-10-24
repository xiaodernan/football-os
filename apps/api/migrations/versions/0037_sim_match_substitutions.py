"""M13 item 1: substitutions on sim_matches

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-25 01:30:00.000000

The match engine gained an optional `substitutions: int = 0` input (M13 item 1). A stored match must
keep the count it was played with so `replay_is_identical` rebuilds the same `MatchInputs` — a replay
that silently drops the subs would compare two different fixtures and blame the model.

SQLite, which is the leg every local run and `scripts/check.sh` use, cannot add a NOT NULL column in
one statement when rows already exist, and it cannot leave a column it does not know the default for
behind a Python-side `default` without `alembic check` flagging drift. So: nullable first, backfill to
0, then make it NOT NULL through batch mode (the table rebuild both engines route through). No
`server_default`: the model declares the Python-side `default`, and a server default the model does not
know about is exactly what `alembic check` reports as drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sim_matches", sa.Column("substitutions", sa.Integer(), nullable=True))
    op.execute("UPDATE sim_matches SET substitutions = 0 WHERE substitutions IS NULL")
    with op.batch_alter_table("sim_matches") as batch:
        batch.alter_column("substitutions", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("sim_matches") as batch:
        batch.alter_column("substitutions", existing_type=sa.Integer(), nullable=True)
    op.drop_column("sim_matches", "substitutions")
