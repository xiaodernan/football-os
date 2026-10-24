"""M13 item 3: home_momentum / away_momentum on sim_matches

Revision ID: 0039
Revises: 0038
Create Date: 2026-10-25 01:52:00.000000

The match engine gained `home_momentum` / `away_momentum` (0..1) inputs (M13 item 3): a side riding
form attacks and presses with more conviction from kick-off. A stored match must keep the two values it
was played with so `replay_is_identical` rebuilds the same `MatchInputs` — a replay that silently drops
the momentum would compare two different fixtures and blame the model.

Same SQLite-safe pattern as 0037/0038: nullable first, backfill to 0.0, then NOT NULL through batch
mode, no `server_default` (the model declares the Python-side default; a server default it does not
know about is what `alembic check` flags as drift).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sim_matches", sa.Column("home_momentum", sa.Float(), nullable=True))
    op.add_column("sim_matches", sa.Column("away_momentum", sa.Float(), nullable=True))
    op.execute("UPDATE sim_matches SET home_momentum = 0.0 WHERE home_momentum IS NULL")
    op.execute("UPDATE sim_matches SET away_momentum = 0.0 WHERE away_momentum IS NULL")
    with op.batch_alter_table("sim_matches") as batch:
        batch.alter_column("home_momentum", existing_type=sa.Float(), nullable=False)
        batch.alter_column("away_momentum", existing_type=sa.Float(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("sim_matches") as batch:
        batch.alter_column("home_momentum", existing_type=sa.Float(), nullable=True)
        batch.alter_column("away_momentum", existing_type=sa.Float(), nullable=True)
    op.drop_column("sim_matches", "away_momentum")
    op.drop_column("sim_matches", "home_momentum")
