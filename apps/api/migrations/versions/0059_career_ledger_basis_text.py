"""Unbounded arithmetic prose: the `basis` columns (M13 follow-up; CI SQLite-leg blind spot)

Every career-ledger table stores the arithmetic in words so a figure can be checked against the
season without the code. The first PostgreSQL leg of the consolidated run read a 300+-character
sentence and refused it (`StringDataRightTruncation` on `career_gate_receipts.basis`), which
SQLite accepts silently — so the length ceiling is only visible on the engine production uses.
Widen every generated-prose `basis` column to TEXT and keep the shipped models in step; the
cup-tie column moves the same way, because its comment claimed 512 would bound the whole
sentence — appended bracket notes are not a bounded grammar.

SQLite cannot ALTER COLUMN TYPE without a rewrite, so every column moves through batch mode;
on PostgreSQL batch mode degenerates to the same coerces the native path would apply.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_TABLES = (
    "career_budget_awards",
    "career_gate_receipts",
    "career_stadium_works",
    "career_upkeep_charges",
    "career_season_tickets",
    "career_training_works",
    "career_cup_ties",
)

_TYPE = {"career_cup_ties": 512}


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "basis",
                existing_type=sa.String(length=_TYPE.get(table, 255)),
                type_=sa.Text(),
            )


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                "basis",
                existing_type=sa.Text(),
                type_=sa.String(length=_TYPE.get(table, 255)),
            )
