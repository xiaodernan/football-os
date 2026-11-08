"""Widen a cup tie's basis (M13 Phase 9 item 35)

`career_cup_ties.basis` held the sentence a tie's slot came from: for a completed bracket, one clause
("the Semi-final the world drew for the half this club's quarter-final feeds"). A season the world has
drawn only to its quarter-finals needs a longer one — the slot names the adjacent tie and the engine's
reading of it - and the appended tie sentence pushed the row past 255 characters on Postgres. This
migration widens the column rather than truncating the explanation.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("career_cup_ties") as batch:
        batch.alter_column("basis", existing_type=sa.String(length=255), type_=sa.String(length=512), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("career_cup_ties") as batch:
        batch.alter_column("basis", existing_type=sa.String(length=512), type_=sa.String(length=255), existing_nullable=False)
