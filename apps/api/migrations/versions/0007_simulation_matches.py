"""simulation matches: fictional fixtures played from the synthetic world's rows (spec §19, §20)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-23 09:00:00.000000

One new table. A `sim_matches` row is the engine's whole report plus the four inputs that produced it
(two clubs, two tactical systems, one seed), because "reproducible" has to mean more than "we kept a
JSON blob": with `seed`, `minutes` and the two system slugs, `simulate_match` can be run again and its
digest compared against the stored one. `data_origin` defaults to `simulation` and `is_demo_data` to
true on every row, so no read path has to remember to say so, and the two team columns null out
instead of cascading — regenerating the world must not delete the fictional matches already played in
it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sim_matches",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.String(length=40), nullable=False),
        sa.Column("model_version", sa.String(length=60), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("block_minutes", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.String(length=40), nullable=True),
        sa.Column("away_team_id", sa.String(length=40), nullable=True),
        sa.Column("home_system", sa.String(length=160), nullable=False),
        sa.Column("away_system", sa.String(length=160), nullable=False),
        sa.Column("home_goals", sa.Integer(), nullable=False),
        sa.Column("away_goals", sa.Integer(), nullable=False),
        sa.Column("winner_side", sa.String(length=8), nullable=False),
        sa.Column("digest", sa.String(length=16), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_sim_matches_owner_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"], name=op.f("fk_sim_matches_home_team_id_teams"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"], name=op.f("fk_sim_matches_away_team_id_teams"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sim_matches")),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_sim_matches_digest", "sim_matches", ["digest"], unique=False)
    op.create_index("ix_sim_owner_created", "sim_matches", ["owner_id", "created_at"], unique=False)
    op.create_index("ix_sim_fixture", "sim_matches", ["home_team_id", "away_team_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sim_fixture", table_name="sim_matches")
    op.drop_index("ix_sim_owner_created", table_name="sim_matches")
    op.drop_index("ix_sim_matches_digest", table_name="sim_matches")
    op.drop_table("sim_matches")
