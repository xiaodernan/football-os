"""The training program's tables (M10, spec §36's first kind of content)

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-21 12:00:00

§36 lists six kinds of content a user can create and the first is a Training Program. The tier
published guides, and its own verification record said what a guide is not: "Nothing here is a
runnable program: no row carries a schedule, a dose or a progression."

These are those three things. A program is a title, a visibility and an ordered list of steps; a
step is a catalogue drill, the minutes it asks for, and the author's own words. The position
column is the progression, and it is unique per program so a program cannot hold two steps at the
same place in its own schedule.

`training_sessions.program_id` remembers which program planned a session. It is nullable because
most sessions are planned by the learner and not by a program, and the column records where a
session came from rather than claiming every session has one behind it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_programs",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("author_id", "slug", name="uq_creator_program_slug"),
    )
    op.create_index("ix_creator_program_author_date", "creator_programs", ["author_id", "published_on"])

    op.create_table(
        "creator_program_steps",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("program_id", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("drill_slug", sa.String(length=80), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["creator_programs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("program_id", "position", name="uq_creator_program_step_position"),
    )

    op.add_column("training_sessions", sa.Column("program_id", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("training_sessions", "program_id")
    op.drop_table("creator_program_steps")
    op.drop_index("ix_creator_program_author_date", table_name="creator_programs")
    op.drop_table("creator_programs")
