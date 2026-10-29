"""Two share tables: a scout report's link, and a child's plan behind a link (M13 Phase 5 item 18)

Revision ID: 0042
Revises: 0041
Create Date: 2026-10-29

`scout_report_shares` landed with the scout share unit but never got a revision, so a database built by
`alembic upgrade head` from scratch answered `alembic check` with a new table — the drift leg every local run and
CI execute. This revision pays that debt and creates the academy tier's own share row in the same motion, because
the two are the same shape and one replay should leave the schema matching `Base.metadata`.

`academy_plan_shares` stores a pointer rather than a page: the plan, the tenant it belongs to, the token and when
the door shut. Every figure the public page prints is recomputed from `plan_assessments` at read time. Both
foreign keys cascade, because §40's erasure is a promise about the child: deleting a plan takes its public links
with it, and deleting an account takes its own.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scout_report_shares",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("share_token", sa.String(length=64), nullable=False),
        sa.Column("player", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=True),
        sa.Column("career", sa.String(length=80), nullable=True),
        sa.Column("compare_to", sa.String(length=80), nullable=True),
        sa.Column("round_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_scout_report_shares_users"), ondelete="CASCADE"),
        sa.UniqueConstraint("share_token", name="uq_scout_report_share_token"),
    )
    op.create_index("ix_scout_report_share_owner_live", "scout_report_shares", ["user_id", "revoked_at"])

    op.create_table(
        "academy_plan_shares",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("share_token", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("plan_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_academy_plan_shares_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_academy_plan_shares_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["development_plans.id"], name=op.f("fk_academy_plan_shares_plans"), ondelete="CASCADE"),
        sa.UniqueConstraint("share_token", name="uq_academy_plan_share_token"),
    )
    op.create_index("ix_academy_plan_share_owner_live", "academy_plan_shares", ["user_id", "revoked_at"])
    op.create_index("ix_academy_plan_share_plan", "academy_plan_shares", ["plan_id"])

    # `0041` created `notifications` without the `updated_at` column `TimestampMixin` owns, which `alembic check`
    # reports as a new column on every fresh database. Backfill from the row's own `created_at`, then close it —
    # the three steps SQLite cannot take in one statement.
    op.add_column("notifications", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE notifications SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("notifications") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("updated_at")
    op.drop_index("ix_academy_plan_share_plan", table_name="academy_plan_shares")
    op.drop_index("ix_academy_plan_share_owner_live", table_name="academy_plan_shares")
    op.drop_table("academy_plan_shares")
    op.drop_index("ix_scout_report_share_owner_live", table_name="scout_report_shares")
    op.drop_table("scout_report_shares")
