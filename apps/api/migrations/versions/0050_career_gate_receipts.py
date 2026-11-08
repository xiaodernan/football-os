"""Career gate receipts: the money a home round earns (M13 Phase 7 item 27)

The ledger had three tables: squad moves, wage charges and the board's season grant. A career's only
income was a sale or a boundary grant, so a wage bill was paid out of savings while the world already
knew how many people were at the ground. This table is the fourth: one row per home round, carrying the
attendance the world stored (or a deterministic share of capacity for a round on the career's own
rotation), the authored ticket price, the amount, the basis in words and the running ``budget_after``.

``uq_career_gate_round`` is the rule that a round is one fixture and can earn one gate. ``fixture_id``
is SET NULL rather than CASCADE: losing the fixture row must not delete money the balance counted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_gate_receipts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("fixture_id", sa.String(length=40), nullable=True),
        sa.Column("attendance", sa.Integer(), nullable=False),
        sa.Column("ticket_price", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "round_index", name="uq_career_gate_round"),
    )
    op.create_index("ix_gate_receipt_career_round", "career_gate_receipts", ["career_id", "round_index"])


def downgrade() -> None:
    op.drop_index("ix_gate_receipt_career_round", table_name="career_gate_receipts")
    op.drop_table("career_gate_receipts")
