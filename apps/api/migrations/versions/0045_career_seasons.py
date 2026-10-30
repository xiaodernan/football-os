"""A career's completed seasons and the boundary verdict (M13 Phase 2 item 8)

Revision ID: 0045
Revises: 0044
Create Date: 2026-10-30

`career_seasons` is the row a career writes when the round that completes a season is played: the league
the season was played in, the absolute rounds it spanned, the points-per-round line the club was judged
against, and where the pyramid sent it next. The club's record is deliberately not stored here — it is
summed from `career_fixtures` on every read and printed beside the stored verdict, so the two can
disagree out loud rather than one silently becoming the truth.

Both competition columns are nullable and `SET NULL`: a season happened even if the generated world that
named its league is later replaced, and the row keeps the name it recorded. The career key cascades, so
§40's erasure takes a manager's season history with the career that played it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_seasons",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("season_index", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("competition_id", sa.String(length=40), nullable=True),
        sa.Column("competition_name", sa.String(length=160), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("first_round", sa.Integer(), nullable=False),
        sa.Column("last_round", sa.Integer(), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("rule", sa.String(length=20), nullable=False),
        sa.Column("line", sa.Float(), nullable=True),
        sa.Column("next_competition_id", sa.String(length=40), nullable=True),
        sa.Column("next_competition_name", sa.String(length=160), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_seasons_career_id_careers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], name=op.f("fk_career_seasons_competition_id_competitions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["next_competition_id"], ["competitions.id"], name=op.f("fk_career_seasons_next_competition_id_competitions"), ondelete="SET NULL"),
        sa.UniqueConstraint("career_id", "season_index", name="uq_career_season_index"),
    )
    op.create_index("ix_career_season_career_round", "career_seasons", ["career_id", "first_round"])


def downgrade() -> None:
    op.drop_index("ix_career_season_career_round", table_name="career_seasons")
    op.drop_table("career_seasons")
