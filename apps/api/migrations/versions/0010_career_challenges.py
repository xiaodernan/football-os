"""careers: a run can be played under an authored scenario (spec §21)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-23 23:40:00.000000

Two columns, not two tables. A live challenge is a *career played under a scenario*, so a run reuses
`careers` and `career_fixtures` exactly as an open career does — there is still one fixture store and
one match model behind both.

`challenge_slug` names the scenario and `challenge_window` its round limit. Nothing else about the
scenario is stored: the goal, the reward and the verdict are recomputed from the run's own fixture
rows on every read, so a challenge cannot be edited into having been won. `challenge_window` of 0
means "no window" — the value every career opened before this revision carries, and the value an open
career keeps.

Server defaults are declared here so the columns can be added to a populated `careers` table without a
separate backfill pass.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("careers", sa.Column("challenge_slug", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("careers", sa.Column("challenge_window", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("careers", "challenge_window")
    op.drop_column("careers", "challenge_slug")
