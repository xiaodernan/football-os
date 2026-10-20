"""A creator's match analysis: an address into the generated fixture list (M10, spec §36's fourth kind)

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-21 19:40:00

§36's fourth kind of content is a Match Analysis: an author's reading of a played fixture, published
beside the match rather than copied out of it. This table stores the author's words, a visibility and
the **address** of a row in `real_matches` - never a score, a shot count or a sentence about the
match. Every measurement a read shows is computed from the match's own stored score and stats on that
read.

`match_hash` is the content address the match carried when the analysis was written. It is a
witness, not a figure: a read compares it with the world's and says whether the fixture has been
revised since (`moved`), while still measuring the match as it reads now.

`match_slug` is a plain pointer rather than a foreign key: `services/world/sync.py` retires
catalogue rows the plan no longer authors, and a RESTRICT would make a routine world sync fail
because somebody once wrote about a fixture. A retired match answers as absence on read.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_match_analyses",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("match_slug", sa.String(length=200), nullable=False),
        sa.Column("match_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("author_id", "slug", name="uq_creator_match_slug"),
    )
    op.create_index("ix_creator_match_author_date", "creator_match_analyses", ["author_id", "published_on"])
    op.create_index("ix_creator_match_anchor", "creator_match_analyses", ["match_slug"])


def downgrade() -> None:
    op.drop_index("ix_creator_match_anchor", table_name="creator_match_analyses")
    op.drop_index("ix_creator_match_author_date", table_name="creator_match_analyses")
    op.drop_table("creator_match_analyses")
