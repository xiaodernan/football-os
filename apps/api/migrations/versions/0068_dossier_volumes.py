"""The Deep Dossier writes back: `dossier_volumes` (Item 311).

A generated chapter used to vanish with the tab that asked for it. This table is the shelf:
one row per chapter a reader chose to keep, addressed by a readable slug, deduplicated on the
content signature so the same commission is never paid for twice.

Revision ID: 0068
Revises: 0067
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dossier_volumes",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("slug", sa.String(length=96), nullable=False),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("focus", sa.String(length=160), nullable=False),
        sa.Column("depth", sa.String(length=16), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locale", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("chapter", sa.Text(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dossier_volumes_slug", "dossier_volumes", ["slug"], unique=True)
    op.create_index("ix_dossier_volumes_signature", "dossier_volumes", ["signature"], unique=True)
    op.create_index("ix_dossier_volumes_created_at", "dossier_volumes", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_dossier_volumes_created_at", table_name="dossier_volumes")
    op.drop_index("ix_dossier_volumes_signature", table_name="dossier_volumes")
    op.drop_index("ix_dossier_volumes_slug", table_name="dossier_volumes")
    op.drop_table("dossier_volumes")
