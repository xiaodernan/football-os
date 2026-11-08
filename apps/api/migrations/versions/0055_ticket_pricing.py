"""A manager prices the gate (M13 Phase 10 item 44)

Item 33 priced every seat at the competition's own figure and item 37 let a manager buy more of them.
The price itself was still not a decision. This migration stores the manager's setting on the career
(`ticket_price_pct`, 100 = the competition's price) and copies the setting and the demand it produced
onto each gate receipt, so a crowd already paid is never rewritten by a later change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("careers", sa.Column("ticket_price_pct", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("career_gate_receipts", sa.Column("price_pct", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("career_gate_receipts", sa.Column("demand_pct", sa.Integer(), nullable=False, server_default="100"))


def downgrade() -> None:
    op.drop_column("career_gate_receipts", "demand_pct")
    op.drop_column("career_gate_receipts", "price_pct")
    op.drop_column("careers", "ticket_price_pct")
