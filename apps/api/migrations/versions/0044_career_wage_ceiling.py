"""The career's wage ceiling (M13 Phase 2 item 6)

Revision ID: 0044
Revises: 0043
Create Date: 2026-10-30

One column, `careers.wage_ceiling`: the most one round's wage bill may commit, in the career's own units. It is
a hard cap the balance cannot stand in for -- a career can be cash-rich and still unable to take on another
wage -- and `0` means the career has none. The ceiling is stated when a career is opened, like its budget, so
rows that predate this column are backfilled with `0` rather than a number nobody chose: a cap invented by a
migration would bind a career its manager never asked to be bound.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("careers", sa.Column("wage_ceiling", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("careers", "wage_ceiling")
