"""Timestamps the models call timezone-aware were built naive on PostgreSQL

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-25

`0021`–`0025` declared every `created_at`/`updated_at` (and `cv_shares.revoked_at`) as `sa.DateTime()`
while `TimestampMixin` declares `DateTime(timezone=True)`. SQLite stores both as `DATETIME`, so no local
leg could see the disagreement. PostgreSQL builds `timestamp without time zone` from the migration and
compares it with the model's `timestamp with time zone`; `alembic check` refused the drift on the first
database CI ever built from scratch (run 40131268450, 2026-10-25).

The five migrations now declare the type the model does, which is what a fresh database replays. This
revision is for databases that already applied the older bytes: it moves the 26 columns `TimestampMixin`
owns and `cv_shares.revoked_at` to `timestamp with time zone`. The conversion is PostgreSQL's assignment
cast, which reads a stored value in the session's time zone — the same reading the write that stored it
took. SQLite is skipped: the engine has one timestamp type there, and `alembic check` is already clean.
"""

import sqlalchemy as sa
from alembic import op

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None

# The columns `TimestampMixin` owns, plus the one `cv_shares` adds on its own.
REPAIR: dict[str, tuple[str, ...]] = {
    "club_fixtures": ("created_at", "updated_at"),
    "club_match_appearances": ("created_at", "updated_at"),
    "club_announcements": ("created_at", "updated_at"),
    "club_announcement_reads": ("created_at", "updated_at"),
    "community_posts": ("created_at", "updated_at"),
    "community_comments": ("created_at", "updated_at"),
    "community_reactions": ("created_at", "updated_at"),
    "community_reposts": ("created_at", "updated_at"),
    "community_follows": ("created_at", "updated_at"),
    "creator_profiles": ("created_at", "updated_at"),
    "creator_guides": ("created_at", "updated_at"),
    "guide_citations": ("created_at", "updated_at"),
    "cv_shares": ("created_at", "updated_at", "revoked_at"),
}


def _engine_name() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    if _engine_name() != "postgresql":
        return
    for table, columns in REPAIR.items():
        for column in columns:
            op.alter_column(table, column, type_=sa.DateTime(timezone=True), existing_type=sa.DateTime())


def downgrade() -> None:
    if _engine_name() != "postgresql":
        return
    for table, columns in REPAIR.items():
        for column in columns:
            op.alter_column(table, column, type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True))
