"""The board's season grant as a ledger row (M13 Phase 7 item 24)

A career's budget could only ever go down: fees left it, wages left it, and only a sale put anything
back. So a second season started with less than the first and a long career could only shrink. This
table is the money that *arrives*: one row per closed season of an open career, written in the same
transaction as the boundary decision it pays for, with the running `budget_after` the other two ledger
tables already carry.

A new table rather than columns on `career_seasons`, because that row is a decision and deliberately
stores no figure — the season's record is summed from `career_fixtures` on every read, and a reader who
wants the money looks at the money's own rows. One grant per season is held by the unique key rather
than by the call site: a boundary that somehow fired twice would otherwise pay twice.

No backfill: a season closed before this migration was paid nothing, and inventing a grant after the
fact would put a figure on the ledger that no boundary produced.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_budget_awards",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("season_index", sa.Integer(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("amount_units", sa.String(length=40), nullable=False),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("promotion", sa.Integer(), nullable=False),
        sa.Column("budget_after", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_budget_awards_career_id_careers"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_budget_awards")),
        sa.UniqueConstraint("career_id", "season_index", name="uq_career_award_season"),
    )
    op.create_index("ix_budget_award_career_round", "career_budget_awards", ["career_id", "round_index"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_budget_award_career_round", table_name="career_budget_awards")
    op.drop_table("career_budget_awards")
