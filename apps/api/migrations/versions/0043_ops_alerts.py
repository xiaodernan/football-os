"""The operator alert ledger (M13 Phase 6 item 21)

Revision ID: 0043
Revises: 0042
Create Date: 2026-10-30

One table, `ops_alerts`: every alert the platform raised about itself, the condition it names, and the channel's
own record of how far it got. The unique `dedupe_key` is the reason a month over its ceiling raises one row
however many sweeps run; the `delivered_at` / `delivery_attempts` pair is the retry state. No row stores a figure
the ledger can recompute: `detail` is the monthly block as the sweep computed it, kept because an alert is a
statement about the moment it fired and a month-to-date number is not reproducible after the month ends.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ops_alerts",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=40), nullable=True),
        sa.Column("delivery_channel", sa.String(length=20), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"], name=op.f("fk_ops_alerts_users"), ondelete="SET NULL"),
        sa.UniqueConstraint("dedupe_key", name="uq_ops_alert_dedupe"),
    )
    op.create_index("ix_ops_alert_state_created", "ops_alerts", ["state", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ops_alert_state_created", table_name="ops_alerts")
    op.drop_table("ops_alerts")
