"""A stadium a manager buys (M13 Phase 9 item 37)

Item 33 made the gate respond to the career through a tier factor and a form factor, but the ground was
still the world's shared `teams.capacity` row: every career at a club sold the same seats, and nothing a
manager did could add one. This migration stores the career's own expansion history. Each row is one
purchase — the seats, the unit price, the money, and the ground's capacity before and after — so the
current capacity is the club's stored figure plus the sum of `seats`, with no second copy to drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_stadium_works",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("amount_units", sa.String(length=40), nullable=False),
        sa.Column("capacity_before", sa.Integer(), nullable=False),
        sa.Column("capacity_after", sa.Integer(), nullable=False),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stadium_work_career", "career_stadium_works", ["career_id"])


def downgrade() -> None:
    op.drop_index("ix_stadium_work_career", table_name="career_stadium_works")
    op.drop_table("career_stadium_works")
