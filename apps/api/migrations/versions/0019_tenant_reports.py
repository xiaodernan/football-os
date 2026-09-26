"""tenant reports (spec §41's last noun): `club_reports`, a saved question and no stored answers

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-26 08:10:00.000000

§41 closes its tenant model with `Reports`. The obvious table — a row with a title, a body, maybe a JSON blob of
figures — was not built, because a stored body is a document that keeps asserting things the tenant stopped
holding: rows get corrected, plans get erased, a consent gets withdrawn, and the report would go on printing the
number from the day it was written while the doors beside it printed the new one.

So this table stores **the question**: which kind of reading, which team, which window. Every figure is re-summed
on read from the rows *this caller* may see, with the formula and the row counts printed next to it. Two
consequences the columns are shaped for:

* there is no payload column, so there is nothing to stale out. `created_at` says when the question was asked, and
  nothing pretends to be when the answer was true — the answer is true at read time or it refuses.
* the same reader question means different numbers for different readers, and that is not a bug to freeze: a
  director's squad-load report and the same report read by one guardian are the same row summed over scopes the
  read applies. Storing figures would have meant storing one of those two and lying about the other.

`team_id` cascades with the team and `asked_by_user_id` sets null with the account: a report about a dissolved
team means nothing, while the record that some coach asked the question is not the departing person's file to
take with them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_reports",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("asked_by_user_id", sa.String(length=40), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("team_id", sa.String(length=40), nullable=True),
        sa.Column("window_from", sa.String(length=10), nullable=False),
        sa.Column("window_to", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_reports_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asked_by_user_id"], ["users.id"], name=op.f("fk_club_reports_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["club_teams.id"], name=op.f("fk_club_reports_club_teams"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_reports")),
        sa.UniqueConstraint("organization_id", "kind", "team_id", "window_from", "window_to", name=op.f("uq_club_report_window")),
    )
    op.create_index("ix_club_report_org_kind", "club_reports", ["organization_id", "kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_club_report_org_kind", table_name="club_reports")
    op.drop_table("club_reports")
