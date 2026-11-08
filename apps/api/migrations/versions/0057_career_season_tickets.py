"""Season tickets (M13 Phase 10 item 46)

One row per season's season-ticket sale: seats sold before the first round at a discount, the money
arriving up front, and those seats filled every home league round without being charged again. The
gate receipt gains `season_ticket_seats`, copied when the gate is paid so a later sale cannot rewrite
a crowd already in the bank.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_season_tickets",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("season_index", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("home_rounds", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("amount_units", sa.String(length=40), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "season_index", name="uq_career_season_ticket"),
    )
    op.create_index("ix_season_ticket_career", "career_season_tickets", ["career_id"])
    op.add_column(
        "career_gate_receipts",
        sa.Column("season_ticket_seats", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("career_gate_receipts", "season_ticket_seats")
    op.drop_index("ix_season_ticket_career", table_name="career_season_tickets")
    op.drop_table("career_season_tickets")
