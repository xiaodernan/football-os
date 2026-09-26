"""tenant sessions (spec §41's remaining noun): one table, `club_sessions`

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-26 07:10:00.000000

§41 lists what a multi-tenant club holds as `Organization, Members, Teams, Roles, Permissions, Players,
Sessions, Reports`. Seven of those landed before this migration; **Sessions** is the eighth, and it is the one
a coach actually produces in a week — a team, a date, a duration, a load, a list of who was there. §40's plans
can already say where a child is going; nothing in the tenant could say what the group did on Tuesday.

**Load is not a column.** The obvious design put `load_units` on the row, and it is wrong in the same way a
stored `progress` was wrong in `0017`: it is arithmetic over `duration_min` and `rpe`, both of which a coach can
correct the next morning, and a stored product would then be a number that quietly disagrees with the row it
came from. So the session stores the two inputs and the service prints the derived figure with its formula,
which is also what lets a reader check it.

**Attendance names the sheet it was taken from.** `attendees` is a list of `real_players` ids — not a join
table, because a session's roster is a statement about one date rather than a set of rows anyone edits
afterwards, and not a copy of player data, because the sheet in `club_team_members` is already the tenant's
claim about who belongs to a team. The service refuses an attendee who is not on **this team's** sheet, and
refuses a child on that sheet whose guardian has not answered for them, so the §40 gate is in front of the §41
row rather than beside it.

**`plan_id` and `curriculum_id` are SET NULL; `team_id` is CASCADE.** A team being dissolved takes its session
history with it, because the rows mean nothing without the grouping they describe. A plan being erased does not:
§40's erasure removes what a tenant *holds about a child*, and a record that sixteen kids trained on a date is
the tenant's own history, not a file on the child. The same reasoning keeps a retired curriculum's sessions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=True),
        sa.Column("curriculum_id", sa.String(length=40), nullable=True),
        sa.Column("coach_user_id", sa.String(length=40), nullable=True),
        sa.Column("scheduled_on", sa.String(length=10), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("rpe", sa.Integer(), nullable=False),
        sa.Column("focus", sa.JSON(), nullable=False),
        sa.Column("drill_slugs", sa.JSON(), nullable=False),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(length=280), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_sessions_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["club_teams.id"], name=op.f("fk_club_sessions_club_teams"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["development_plans.id"], name=op.f("fk_club_sessions_development_plans"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["curriculum_id"], ["academy_curricula.id"], name=op.f("fk_club_sessions_academy_curricula"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["coach_user_id"], ["users.id"], name=op.f("fk_club_sessions_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_sessions")),
        sa.UniqueConstraint("organization_id", "team_id", "scheduled_on", "slot", name=op.f("uq_club_session_slot")),
    )
    op.create_index("ix_club_session_org_date", "club_sessions", ["organization_id", "scheduled_on"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_club_session_org_date", table_name="club_sessions")
    op.drop_table("club_sessions")
