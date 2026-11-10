"""Per-kind notification mutes on the user (spec 27's second slice)

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-11 12:00:00

One JSON column: `{"follower": true, "comment": true, "reaction": true}` — the kinds the
account WANTS written to its tray. A muted kind is never written: `notify` checks before
inserting, so a muted tray is empty by choice rather than by a filter the reader applies
after the fact. The default writes every kind, which is what the tier did before this
column existed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060_xp_leaderboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notification_mutes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_mutes")
