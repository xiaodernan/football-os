"""The board gallery's consent column (M9's consent story, spec §13 follow-up)

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-14 19:40:00

A board could be private or hold an unguessable share token; what it could never do is
stand in a public place, which is why the audit's follow-up list carried "boards beyond
single ownership (M9's consent story)". `listed_publicly` is that story's column: the
owner's explicit, revocable yes to the one thing a gallery does — showing the board's
name, its measurements and the owner's display name to visitors with no account at all.
Default False, because a board is private working material until its owner says
otherwise, and the revocation is a predicate change, not a delete: the row survives,
the gallery read simply stops seeing it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tactic_boards",
        sa.Column("listed_publicly", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_board_listed_publicly", "tactic_boards", ["listed_publicly"])


def downgrade() -> None:
    op.drop_index("ix_board_listed_publicly", table_name="tactic_boards")
    op.drop_column("tactic_boards", "listed_publicly")
