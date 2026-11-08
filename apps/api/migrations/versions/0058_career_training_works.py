"""The club builds a training ground (M13 Phase 11 item 47)

Item 4 gave a career a development curve fed by the world's training sessions, but every club trained
on the same ground. This migration stores the career's facility level and one row per upgrade, so the
money that buys a level is a ledger row and the level that remains is what the next development
projection reads.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("careers", sa.Column("training_level", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "career_training_works",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("level_before", sa.Integer(), nullable=False),
        sa.Column("level_after", sa.Integer(), nullable=False),
        sa.Column("bonus_pct_before", sa.Integer(), nullable=False),
        sa.Column("bonus_pct_after", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("amount_units", sa.String(length=40), nullable=False),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_training_work_career_round", "career_training_works", ["career_id", "round_index"]
    )


def downgrade() -> None:
    op.drop_index("ix_training_work_career_round", table_name="career_training_works")
    op.drop_table("career_training_works")
    op.drop_column("careers", "training_level")
