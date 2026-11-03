"""The objectives a season met pay a bonus (M13 Phase 9 item 36)

Item 24's award table paid one grant per closed season and held that promise in a season-wide unique key.
Item 36 pays each met objective a row of its own, so the key widens to (career, season, kind, stage): the
grant stays unique in its season (its kind is fixed and its stage is empty), and each objective kind can
pay once. `stage` names what was paid for — the objective's kind — so the row says what was met without
reading the basis string.

No backfill: an objective met before this migration was paid nothing, and inventing a bonus after the fact
would put a figure on the ledger that no boundary produced.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("career_budget_awards", sa.Column("stage", sa.String(length=80), nullable=False, server_default=""))
    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot drop a constraint in place, so the whole table is rebuilt once: the server default
        # goes, the old season-wide unique goes, and the per-stage unique arrives together.
        with op.batch_alter_table("career_budget_awards", recreate="always") as batch:
            batch.alter_column("stage", existing_type=sa.String(length=80), server_default=None, existing_nullable=False)
            batch.drop_constraint("uq_career_award_season", type_="unique")
            batch.create_unique_constraint("uq_career_award_stage", ["career_id", "season_index", "kind", "stage"])
    else:
        with op.batch_alter_table("career_budget_awards") as batch:
            batch.alter_column("stage", existing_type=sa.String(length=80), server_default=None, existing_nullable=False)
        op.drop_constraint("uq_career_award_season", "career_budget_awards", type_="unique")
        op.create_unique_constraint("uq_career_award_stage", "career_budget_awards", ["career_id", "season_index", "kind", "stage"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("career_budget_awards", recreate="always") as batch:
            batch.drop_constraint("uq_career_award_stage", type_="unique")
            batch.create_unique_constraint("uq_career_award_season", ["career_id", "season_index"])
            batch.drop_column("stage")
    else:
        op.drop_constraint("uq_career_award_stage", "career_budget_awards", type_="unique")
        op.create_unique_constraint("uq_career_award_season", "career_budget_awards", ["career_id", "season_index"])
        op.drop_column("career_budget_awards", "stage")
