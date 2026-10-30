"""The generated fixture a career round played (M13 Phase 3 item 12, the tie half)

Revision ID: 0046
Revises: 0045
Create Date: 2026-10-31

The calendar half made a career's season the fixture list the world drew; this half records *which*
world row each round played, so the same fixture identity can be read from the career's ledger and from
the public match page. Both columns are nullable because a round can be played on the career's own
rotation after the generated calendar runs out, and because rows written before this migration have no
tie to name. The reference is held by value rather than as a foreign key on purpose: a career outlives
the generated world it was opened in, and `world_match_slug` is what a link and a re-read use.

No backfill is possible — the fixture a pre-migration round played was never stored — so the column is
left null rather than guessed at, and `career_view` says a round has no world row instead of inventing
one.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("career_fixtures", sa.Column("world_match_id", sa.String(length=40), nullable=True))
    op.add_column("career_fixtures", sa.Column("world_match_slug", sa.String(length=200), nullable=True))
    op.create_index("ix_career_fixture_world_match", "career_fixtures", ["world_match_id"])


def downgrade() -> None:
    op.drop_index("ix_career_fixture_world_match", table_name="career_fixtures")
    op.drop_column("career_fixtures", "world_match_slug")
    op.drop_column("career_fixtures", "world_match_id")
