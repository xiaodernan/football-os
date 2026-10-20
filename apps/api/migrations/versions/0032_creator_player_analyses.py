"""A creator's player analysis: an address into the generated world (M10, spec §36's third kind)

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-21 19:00:00

§36's third kind of content is a Player Analysis: an author's reading of a footballer, published
beside the player rather than copied out of him. This table stores the author's words, a visibility
and the **address** of a row in `real_players` - never a rate, a total or a sentence about the
player. Every measurement a read shows is computed from the player's own stored columns on that read.

`player_hash` is the content address the player carried when the analysis was written. It is a
witness, not a figure: a read compares it with the world's and says whether the player has been
revised since (`moved`), while still measuring the player as he reads now.

`player_slug` is a plain pointer rather than a foreign key: `services/world/sync.py` retires rows
the world plan no longer authors, and a RESTRICT would make a routine world sync fail because
somebody once wrote about a player. A retired player answers as absence on read.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_player_analyses",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("author_id", "slug", name="uq_creator_analysis_slug"),
    )
    op.create_index("ix_creator_analysis_author_date", "creator_player_analyses", ["author_id", "published_on"])
    op.create_index("ix_creator_analysis_player", "creator_player_analyses", ["player_slug"])


def downgrade() -> None:
    op.drop_index("ix_creator_analysis_player", table_name="creator_player_analyses")
    op.drop_index("ix_creator_analysis_author_date", table_name="creator_player_analyses")
    op.drop_table("creator_player_analyses")
