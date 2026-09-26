"""careers: the container a fictional season is played in (spec §20)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-23 22:05:00.000000

Two new tables. `careers` holds the stated intent — a manager name, a club borrowed from the
synthetic world, a philosophy, a tactical system, a budget and the objectives to judge the season by.
`career_fixtures` holds one row per round: which club was met, on which side, and the `sim_matches`
row that decided it. The score columns are copies of what that match said, kept so a career still
reads after its match report is deleted; every aggregate the career page shows is summed from these
rows on the request, and cross-checked against the linked match when it still exists.

The club and competition columns null out rather than cascade: regenerating the world must not erase
a person's season, exactly as with `sim_matches`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "careers",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("manager_name", sa.String(length=80), nullable=False),
        sa.Column("club_id", sa.String(length=40), nullable=True),
        sa.Column("club_name", sa.String(length=160), nullable=False),
        sa.Column("club_short", sa.String(length=40), nullable=False),
        sa.Column("competition_id", sa.String(length=40), nullable=True),
        sa.Column("competition_name", sa.String(length=160), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("philosophy", sa.String(length=20), nullable=False),
        sa.Column("system_slug", sa.String(length=160), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("budget_units", sa.String(length=40), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.Column("rounds_played", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_careers_owner_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["club_id"], ["teams.id"], name=op.f("fk_careers_club_id_teams"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], name=op.f("fk_careers_competition_id_competitions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_careers")),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_career_owner_created", "careers", ["owner_id", "created_at"], unique=False)

    op.create_table(
        "career_fixtures",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.String(length=40), nullable=True),
        sa.Column("match_slug", sa.String(length=80), nullable=False),
        sa.Column("digest", sa.String(length=16), nullable=False),
        sa.Column("model_version", sa.String(length=60), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=5), nullable=False),
        sa.Column("opponent_team_id", sa.String(length=40), nullable=True),
        sa.Column("opponent_name", sa.String(length=160), nullable=False),
        sa.Column("opponent_short", sa.String(length=40), nullable=False),
        sa.Column("venue_name", sa.String(length=120), nullable=False),
        sa.Column("club_goals", sa.Integer(), nullable=False),
        sa.Column("opponent_goals", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=4), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_fixtures_career_id_careers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["sim_matches.id"], name=op.f("fk_career_fixtures_match_id_sim_matches"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opponent_team_id"], ["teams.id"], name=op.f("fk_career_fixtures_opponent_team_id_teams"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_fixtures")),
        sa.UniqueConstraint("career_id", "round_index", name="uq_career_round"),
    )
    op.create_index("ix_career_fixture_match", "career_fixtures", ["match_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_career_fixture_match", table_name="career_fixtures")
    op.drop_table("career_fixtures")
    op.drop_index("ix_career_owner_created", table_name="careers")
    op.drop_table("careers")
