"""The ground costs money to run (M13 Phase 10 item 45)

Item 37 let a manager buy seats and item 44 let the manager price them. This migration adds the cost
side of the same ground: one row per home round, charging `round(capacity × 25%)` credits for the seats
the round opens. A challenge career pays none, like its gate; a neutral-venue final pays none.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_upkeep_charges",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("fixture_id", sa.String(length=40), nullable=True),
        sa.Column("tie_id", sa.String(length=40), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("seat_rate_pct", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("amount_units", sa.String(length=40), nullable=False),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fixture_id"], ["career_fixtures.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tie_id"], ["career_cup_ties.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upkeep_charge_career_round", "career_upkeep_charges", ["career_id", "round_index"])
    op.create_index(
        "uq_career_upkeep_round",
        "career_upkeep_charges",
        ["career_id", "round_index"],
        unique=True,
        postgresql_where=sa.text("tie_id IS NULL"),
        sqlite_where=sa.text("tie_id IS NULL"),
    )
    op.create_index(
        "uq_career_upkeep_tie",
        "career_upkeep_charges",
        ["tie_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_career_upkeep_tie", table_name="career_upkeep_charges")
    op.drop_index("uq_career_upkeep_round", table_name="career_upkeep_charges")
    op.drop_index("ix_upkeep_charge_career_round", table_name="career_upkeep_charges")
    op.drop_table("career_upkeep_charges")
