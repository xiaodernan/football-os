"""tactical systems: the 50-store catalogue behind the Tactical Lab (spec §11–§13, §65)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22 08:00:00.000000

One new table, created rather than recreated: nothing in M4 touches an M3 table, so the world's
rows are left alone. `board` holds the measured artefact the plan produces (both phases'
coordinates, the eight metrics with their formulas, the graded strengths/risks, the role
catalogue entries in the field and the named counterfactuals). It is JSON on purpose — those
numbers are the *output* of the geometry, and storing them verbatim is what lets the API serve
exactly what was computed. Anything a browse path filters, orders or counts by is a real column.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tactical_systems",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("formation", sa.String(length=20), nullable=False),
        sa.Column("temperament_key", sa.String(length=40), nullable=False),
        sa.Column("press_line_y", sa.Float(), nullable=False),
        sa.Column("block_depth", sa.Float(), nullable=False),
        sa.Column("defensive_narrowing", sa.Float(), nullable=False),
        sa.Column("board", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tactical_systems")),
        sa.UniqueConstraint("slug", name=op.f("uq_tactical_systems_slug")),
    )
    op.create_index("ix_tactics_formation", "tactical_systems", ["formation"], unique=False)
    op.create_index("ix_tactics_temperament", "tactical_systems", ["temperament_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tactics_temperament", table_name="tactical_systems")
    op.drop_index("ix_tactics_formation", table_name="tactical_systems")
    op.drop_table("tactical_systems")
