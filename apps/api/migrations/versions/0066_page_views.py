"""M7 item 98: page_views — the behavioural beacon table behind the admin console.

Rows are written either by the public ``POST /api/v1/telemetry/page-view`` door (one row per
browser navigation, seeded=false) or by the deterministic demo cohort seeder
(``app.services.behavior_seed``, seeded=true). ``seeded`` keeps the two apart so the admin
console can label every figure it prints.

Revision ID: 0066
Revises: 0065
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("session_ref", sa.String(length=48), nullable=False),
        sa.Column("path", sa.String(length=200), nullable=False),
        sa.Column("dwell_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bounced", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("seeded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_page_views_session_ref", "page_views", ["session_ref"])
    op.create_index("ix_page_views_path", "page_views", ["path"])
    op.create_index("ix_page_views_created_at", "page_views", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_page_views_created_at", table_name="page_views")
    op.drop_index("ix_page_views_path", table_name="page_views")
    op.drop_index("ix_page_views_session_ref", table_name="page_views")
    op.drop_table("page_views")
