"""The notification tier (spec module 27, the first slice)

Revision ID: 0041
Revises: 0040
Create Date: 2026-10-26 23:30:00

One row per event an account should hear about, written at the moment the event
happens: a follower, a comment on the account's post, a reaction to it. The payload
carries the addresses the reader needs — never another account's email, and never a
figure the reader could not recompute from the row the payload names. `read_at` is the
whole read-state machinery: null is unread, a timestamp is read, and there is no
third state for a reader to manage.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("user_id", sa.String(40), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notification_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notification_user_unread", "notifications", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_user_unread", table_name="notifications")
    op.drop_index("ix_notification_user_created", table_name="notifications")
    op.drop_table("notifications")
