"""A creator's career challenge: an authored scenario entrants pin their own run to (M10, spec §36's fifth kind)

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-22 09:10:00

§36's fifth kind is a Career Challenge: an author's objective, target and window over a career's own
fixtures, published for other accounts to enter with a run of their own. `creator_career_challenges`
stores the author's words and the rule; `creator_career_attempts` stores one entrant's **address**
of a career and the round its window opened at. Neither table stores a point, a win or a goal: every
figure a verdict shows is summed from the entrant's own `career_fixtures` rows on the read.

`career_slug` is a plain pointer rather than a foreign key: a career is the entrant's own row and
`DELETE /career/{slug}` must not be blocked by an attempt somebody once made. `start_round` is an
event fact about the entry - how many played fixtures the career stood at - not a cached
measurement; the window is read from that round onward.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_career_challenges",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("objective_kind", sa.String(length=20), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("window_rounds", sa.Integer(), nullable=False),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("author_id", "slug", name="uq_creator_career_challenge_slug"),
    )
    op.create_index(
        "ix_creator_career_challenge_author_date", "creator_career_challenges", ["author_id", "published_on"]
    )
    op.create_table(
        "creator_career_attempts",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("challenge_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("career_slug", sa.String(length=80), nullable=False),
        sa.Column("start_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["creator_career_challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("challenge_id", "account_id", name="uq_creator_career_attempt"),
    )
    op.create_index("ix_creator_career_attempt_challenge", "creator_career_attempts", ["challenge_id"])
    op.create_index("ix_creator_career_attempt_career", "creator_career_attempts", ["career_slug"])


def downgrade() -> None:
    op.drop_index("ix_creator_career_attempt_career", table_name="creator_career_attempts")
    op.drop_index("ix_creator_career_attempt_challenge", table_name="creator_career_attempts")
    op.drop_table("creator_career_attempts")
    op.drop_index("ix_creator_career_challenge_author_date", table_name="creator_career_challenges")
    op.drop_table("creator_career_challenges")
