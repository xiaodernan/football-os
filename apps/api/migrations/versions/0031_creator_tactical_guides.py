"""A creator's tactical guide: an address into the tactical catalogue (M10, spec §36's second kind)

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-21 18:00:00

§36's second kind of content is a Tactical Guide: an author's reading of a shape, published beside
the shape rather than copied out of it. This table stores the author's words, a visibility and the
**address** of a row in `tactical_systems` - never a metric, a coordinate or a sentence about the
shape. Every measurement a read shows is computed from the system's own dots on that read.

`system_hash` is the content address the system carried when the guide was written. It is a
witness, not a figure: a read compares it with the catalogue's and says whether the system has
been revised since (`moved`), while still measuring the system as it reads now.

`system_slug` is a plain pointer rather than a foreign key: `services/tactics/sync.py` retires
catalogue rows the plan no longer authors, and a RESTRICT would make a routine catalogue sync fail
because somebody once wrote about a system. A retired system answers as absence on read.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_tactical_guides",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("system_slug", sa.String(length=160), nullable=False),
        sa.Column("system_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("author_id", "slug", name="uq_creator_tactical_slug"),
    )
    op.create_index("ix_creator_tactical_author_date", "creator_tactical_guides", ["author_id", "published_on"])
    op.create_index("ix_creator_tactical_system", "creator_tactical_guides", ["system_slug"])


def downgrade() -> None:
    op.drop_index("ix_creator_tactical_system", table_name="creator_tactical_guides")
    op.drop_index("ix_creator_tactical_author_date", table_name="creator_tactical_guides")
    op.drop_table("creator_tactical_guides")
