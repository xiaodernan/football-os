"""the appearance ledger (spec §20): a played round now leaves a trace the next round reads

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25 00:20:00.000000

§20 asks a career to carry a squad from match to match. Until now it did not: `career_fixtures` recorded
the score of a round and `career_squad_moves` recorded who had been bought, but nothing recorded who
actually *played*. So the eleven built for round 9 was composed from exactly the same inputs as the one
built for round 1 — the same stored `form`, the same fatigue term in the engine — and a career that had
played eight full matches was as fresh as one that had played none. Training was further away still:
`real_training_sessions` holds the world's 100 sessions with a `load_units` figure on each, and no code
read them for anything but a player's page.

This table is the missing fact. One row per player per round for the eleven the engine selected on the
career's side, with the minutes the fixture was played at. `carry_over` turns those rows, plus each
player's own training load on file, into a condition figure that the side's form index is adjusted by —
which is where it reaches the engine, through a term that already reads form and already says so.

Minutes are stored rather than re-read out of `sim_matches.report` because the report is the engine's
output and its owner can delete it: the load a round put on a squad belongs to the career, not to a
match report that happens to still be on file.

What this does not claim, and the row shape keeps honest: a selected player is credited the whole match
because the engine models no substitutions; nothing here rests a player, drops him or trains him up —
the numbers come from rows the career already has, and the selection rule itself is unchanged.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_appearances",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.String(length=40), nullable=False),
        sa.Column("player_slug", sa.String(length=160), nullable=False),
        sa.Column("player_name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("band", sa.String(length=10), nullable=False),
        sa.Column("side", sa.String(length=5), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("minutes_units", sa.String(length=40), nullable=False),
        sa.Column("opponent_name", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"], name=op.f("fk_career_appearances_career_id_careers"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["real_players.id"], name=op.f("fk_career_appearances_player_id_real_players"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_career_appearances")),
        sa.UniqueConstraint("career_id", "round_index", "player_id", name="uq_career_appearance_round_player"),
    )
    op.create_index("ix_appearance_career_round", "career_appearances", ["career_id", "round_index"], unique=False)
    op.create_index("ix_appearance_player", "career_appearances", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_appearance_player", table_name="career_appearances")
    op.drop_index("ix_appearance_career_round", table_name="career_appearances")
    op.drop_table("career_appearances")
