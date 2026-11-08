"""Career cup ties and the prizes they pay (M13 Phase 8 item 32)

The generated world already draws a knockout cup for every season: eight entrants, four quarter-finals,
two semi-finals and a final, each with a stored opponent, side and venue. A career only ever played its
league calendar, so a cup was scenery. This migration stores the ties a career plays in that bracket and
lets the board's award table pay them.

``career_cup_ties`` is a fifth *career* table, not a fifth ledger: the money a tie pays still lands in
``career_budget_awards``, which is the table the balance arithmetic already sums. ``stage`` is added to
that table so an award can name the cup round it was won in, and ``uq_career_award_season`` is replaced by
``uq_career_award_stage`` over (career, season, kind, stage): a season still pays exactly one grant (its
stage is empty), and a cup run can pay one prize per round without a second grant becoming possible.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_cup_ties",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("season_index", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=12), nullable=False),
        sa.Column("cup_id", sa.String(length=40), nullable=True),
        sa.Column("cup_slug", sa.String(length=160), nullable=False),
        sa.Column("cup_name", sa.String(length=160), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("stage_index", sa.Integer(), nullable=False),
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
        sa.Column("decided_by", sa.String(length=24), nullable=False),
        sa.Column("penalty_note", sa.String(length=60), nullable=False),
        sa.Column("world_match_id", sa.String(length=40), nullable=True),
        sa.Column("basis", sa.String(length=255), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cup_id"], ["competitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["match_id"], ["sim_matches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opponent_team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "season_index", "cup_slug", "stage", name="uq_cup_tie_stage"),
    )
    op.create_index("ix_cup_tie_career_season", "career_cup_ties", ["career_id", "season_index"])

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
    op.drop_index("ix_cup_tie_career_season", table_name="career_cup_ties")
    op.drop_table("career_cup_ties")
