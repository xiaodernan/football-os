"""world training sessions: the last spec §65 gate row (100 Training Sessions)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-23 10:00:00.000000

One new table, and it is deliberately *not* `training_sessions`. That table is a real person's own
log — it is walked by the export and erasure paths — while these rows are the demo world's history
for generated players. `drill_slug` is a plain string rather than a FK to `training_drills`: the
world plan is built in memory from `app.services.training_catalog.DRILLS`, and a boot-time world
sync must not depend on the catalogue having been synced first. `tests/test_world.py` asserts every
slug resolves, which is the stronger guarantee a FK would only approximate.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "real_training_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("natural_key", sa.String(length=200), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=False),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("session_date", sa.String(length=10), nullable=False),
        sa.Column("drill_slug", sa.String(length=140), nullable=False),
        sa.Column("drill_title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("rpe", sa.Integer(), nullable=False),
        sa.Column("load_units", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=12), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["player_id"], ["real_players.id"], name=op.f("fk_real_training_sessions_player_id_real_players"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_real_training_sessions_team_id_teams"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_real_training_sessions")),
        sa.UniqueConstraint("natural_key", name="uq_world_training_natural_key"),
    )
    op.create_index("ix_world_training_player_date", "real_training_sessions", ["player_id", "session_date"], unique=False)
    op.create_index("ix_world_training_team", "real_training_sessions", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_world_training_team", table_name="real_training_sessions")
    op.drop_index("ix_world_training_player_date", table_name="real_training_sessions")
    op.drop_table("real_training_sessions")
