"""A creator's scouting list: addresses into the generated world, and the author's notes (M10, §36's sixth kind)

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-21 20:20:00

§36's sixth kind of content is a Scouting List: an author's selection of footballers. `creator_scouting_lists`
holds the author's words and a visibility; `creator_scouting_entries` holds one row per selection - the
**address** of a row in `real_players`, the content address that player carried at publication, and the
author's own note. No player attribute is stored: name, position, overall and club are read from the world's
row on every read.

`player_slug` is a plain pointer rather than a foreign key: `services/world/sync.py` retires generated rows,
and a list must survive a refresh. A retired player leaves a bare address in the list rather than erasing the
author's other selections.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_scouting_lists",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("author_id", "slug", name="uq_creator_scouting_list_slug"),
    )
    op.create_index("ix_creator_scouting_list_author_date", "creator_scouting_lists", ["author_id", "published_on"])
    op.create_table(
        "creator_scouting_entries",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("list_id", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["list_id"], ["creator_scouting_lists.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("list_id", "position", name="uq_creator_scouting_entry_position"),
        sa.UniqueConstraint("list_id", "player_slug", name="uq_creator_scouting_entry_player"),
    )
    op.create_index("ix_creator_scouting_entry_player", "creator_scouting_entries", ["player_slug"])


def downgrade() -> None:
    op.drop_index("ix_creator_scouting_entry_player", table_name="creator_scouting_entries")
    op.drop_table("creator_scouting_entries")
    op.drop_index("ix_creator_scouting_list_author_date", table_name="creator_scouting_lists")
    op.drop_table("creator_scouting_lists")
