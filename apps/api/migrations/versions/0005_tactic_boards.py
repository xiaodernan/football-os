"""tactic boards: user-arranged elevens, shareable by token (spec §13, §21, §61)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22 10:00:00.000000

One new table, created rather than recreated — nothing here touches the authored catalogue. The
coordinates are user content (`data_origin='user'`), so they are never rendered as a project-authored
tactical system, and `share_token` is nullable+unique: an unshared board has no URL at all, and
revoking a share clears the token rather than deleting the board.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tactic_boards",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("origin_system", sa.String(length=160), nullable=True),
        sa.Column("phase_in", sa.JSON(), nullable=False),
        sa.Column("phase_out", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.String(length=12), nullable=False),
        sa.Column("share_token", sa.String(length=64), nullable=True),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_tactic_boards_owner_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tactic_boards")),
        sa.UniqueConstraint("slug", name=op.f("uq_tactic_boards_slug")),
        sa.UniqueConstraint("share_token", name=op.f("uq_tactic_boards_share_token")),
    )
    op.create_index("ix_board_owner", "tactic_boards", ["owner_id"], unique=False)
    op.create_index("ix_board_visibility", "tactic_boards", ["visibility"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_board_visibility", table_name="tactic_boards")
    op.drop_index("ix_board_owner", table_name="tactic_boards")
    op.drop_table("tactic_boards")
