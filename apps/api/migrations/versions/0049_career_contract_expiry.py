"""Career contract expiry: the last round a permanent deal covers (M13 Phase 7 item 25)

The market stored a deal's length in years and projected an expiry from it on every read, but nothing
ever enforced that date: a signed player stayed forever and the wage bill never shrank. This column
stores the last round the deal covers, fixed from the season length at the moment it was signed, so a
later promotion cannot stretch or shorten a contract already agreed. Zero means the row predates this
migration (or is a loan, whose last round is ``loan_until_round``); readers fall back to the stored terms
for those rows rather than backfilling a date the signing season cannot support.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("career_squad_moves", sa.Column("expiry_round", sa.Integer(), nullable=False, server_default="0"))
    # Drop the server default after the backfill: the model declares a Python-side default, and a
    # server default the model does not know about is exactly what ``alembic check`` reports as drift.
    with op.batch_alter_table("career_squad_moves") as batch:
        batch.alter_column("expiry_round", existing_type=sa.Integer(), server_default=None, existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("career_squad_moves") as batch:
        batch.drop_column("expiry_round")
