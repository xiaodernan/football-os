"""Career-linked development written back (M13 Phase 1 item 4, the write-back half)

`development_view` projected what a season of football would do to a player's attributes, but the
projection never reached the engine: `team_profile` reads `real_players` rows, and no career round was
allowed to rewrite them. This table is the career-owned copy that closes the loop — one row per selected
player per played round, holding the developed attribute set as of that round, read by `squad_as_of` for
the rounds *after* it. The world's rows stay exactly what the generator wrote; a replay of round N reads
only rows written before N, so a stored match keeps its digest.

No backfill: a round played before this migration wrote no development row, and `development_view`
recomputes the curve from `career_appearances` anyway, so nothing is invented for history.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_developments",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("minutes_total", sa.Integer(), nullable=False),
        sa.Column("training_units", sa.Integer(), nullable=False),
        sa.Column("effective_minutes", sa.Integer(), nullable=False),
        sa.Column("potential", sa.Integer(), nullable=False),
        sa.Column("overall_before", sa.Float(), nullable=False),
        sa.Column("overall_after", sa.Float(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_developments_career_id_careers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_career_developments_player_id_real_players"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_developments")),
        sa.UniqueConstraint("career_id", "round_index", "player_id", name="uq_career_development_round_player"),
    )
    op.create_index("ix_development_career_round", "career_developments", ["career_id", "round_index"], unique=False)
    op.create_index("ix_development_player", "career_developments", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_development_player", table_name="career_developments")
    op.drop_index("ix_development_career_round", table_name="career_developments")
    op.drop_table("career_developments")
