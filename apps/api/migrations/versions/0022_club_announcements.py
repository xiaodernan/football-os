"""0022 — §39's Communication row: one notice board and its receipts (M8, spec §39).

Two tables and no third on purpose. `club_announcements` stores the words, the audience *predicate* and the role
its author held when they posted it; `club_announcement_reads` stores one `(notice, account)` receipt. There is no
recipient column in either, and that absence is the tier's design rather than a shortcut:

* who can see a notice is recomputed from `organization_members` on every read, so a revoked member leaves the
  denominator at once instead of lingering in a stored count that insists they never read it;
* §40's data-minimisation rule forbids a row written about one named child, and a table with no column that could
  hold a child cannot break that rule by accident — the shape is the guard.

`uq_club_announcement_read` is what makes a receipt idempotent at the level of the schema rather than only in the
code path that writes one, the same argument §40 made for its consent row. Both foreign keys out of a notice
CASCADE: erasing a notice erases its receipts, and deleting a tenant takes its whole board with it — while
`author_id` is SET NULL, because a departed author's notice is the tenant's record, not their personal row.

Nothing here is dialect-specific: every constraint is named through `op.f()` because both engines in the test
matrix have to accept the DDL exactly as written.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_announcements",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("audience", sa.String(length=24), nullable=False, server_default="members"),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("author_id", sa.String(length=40), nullable=True),
        sa.Column("author_role", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_announcements_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_club_announcements_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_announcements")),
    )
    op.create_index("ix_club_announcement_org_date", "club_announcements", ["organization_id", "published_on"])
    op.create_index("ix_club_announcement_board", "club_announcements", ["organization_id", "audience", "pinned"])

    op.create_table(
        "club_announcement_reads",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.String(length=40), nullable=False),
        sa.Column("announcement_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("read_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_club_announcement_reads_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["announcement_id"], ["club_announcements.id"], name=op.f("fk_club_announcement_reads_announcements"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_club_announcement_reads_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_club_announcement_reads")),
        sa.UniqueConstraint("announcement_id", "user_id", name=op.f("uq_club_announcement_read")),
    )
    op.create_index("ix_club_announcement_read_user", "club_announcement_reads", ["user_id", "read_on"])


def downgrade() -> None:
    op.drop_index("ix_club_announcement_read_user", table_name="club_announcement_reads")
    op.drop_table("club_announcement_reads")
    op.drop_index("ix_club_announcement_board", table_name="club_announcements")
    op.drop_index("ix_club_announcement_org_date", table_name="club_announcements")
    op.drop_table("club_announcements")
