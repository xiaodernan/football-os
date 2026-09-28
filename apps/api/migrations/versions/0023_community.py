"""0023 — §35's Community tier: what an account publishes, and the rows that reach it (M9, spec §35).

Five tables and one idea: **a post stores a pointer, never a copy**. `community_posts` holds a kind, the author's
own words and the address of the artifact being shared; the figures a reader sees about it — `likes`, `comments`,
`reposts` — are counted from the other four tables at read time, so a share cannot go stale the way a snapshot
would, and there is no column here that could hold one account's statistic about another.

The three pair-tables each carry a unique constraint rather than relying on a code path:
`uq_community_reaction`, `uq_community_repost` and `uq_community_follow` make "pressing twice is one row" a fact
about the schema, which is §40's consent row and §57's receipt row carried over to a community. A follow is the
only row here that decides *reach*: `visibility = followers` is answered by joining this table at read time, so an
unfollow withdraws reach at once and deletes nothing that was already read.

Every foreign key out of a post CASCADEs, including `author_id`: unlike §57's notice — which is a tenant's record
and survives its author's account as a SET NULL — a post is its author's own publication, and the right to have
an account's records go with the account (§40's erasure argument) is what makes deletion the answer here.

Nothing is dialect-specific: each constraint is named through `op.f()` so both engines in the test matrix accept
the DDL exactly as written.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_posts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="note"),
        sa.Column("body", sa.String(length=1500), nullable=False),
        sa.Column("pointer", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("shared_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_community_posts_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_posts")),
    )
    op.create_index("ix_community_post_author_date", "community_posts", ["author_id", "shared_on"])
    op.create_index("ix_community_post_visibility", "community_posts", ["visibility", "shared_on"])

    op.create_table(
        "community_comments",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("post_id", sa.String(length=40), nullable=False),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("body", sa.String(length=600), nullable=False),
        sa.Column("commented_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], name=op.f("fk_community_comments_posts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_community_comments_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_comments")),
    )
    op.create_index("ix_community_comment_post_date", "community_comments", ["post_id", "commented_on"])

    op.create_table(
        "community_reactions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("post_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("reaction", sa.String(length=16), nullable=False, server_default="like"),
        sa.Column("reacted_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], name=op.f("fk_community_reactions_posts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_community_reactions_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_reactions")),
        sa.UniqueConstraint("post_id", "user_id", "reaction", name=op.f("uq_community_reaction")),
    )
    op.create_index("ix_community_reaction_user", "community_reactions", ["user_id", "reacted_on"])

    op.create_table(
        "community_reposts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("post_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("reposted_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], name=op.f("fk_community_reposts_posts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_community_reposts_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_reposts")),
        sa.UniqueConstraint("post_id", "user_id", name=op.f("uq_community_repost")),
    )
    op.create_index("ix_community_repost_user", "community_reposts", ["user_id", "reposted_on"])

    op.create_table(
        "community_follows",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("follower_id", sa.String(length=40), nullable=False),
        sa.Column("followee_id", sa.String(length=40), nullable=False),
        sa.Column("followed_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], name=op.f("fk_community_follows_follower"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"], name=op.f("fk_community_follows_followee"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_follows")),
        sa.UniqueConstraint("follower_id", "followee_id", name=op.f("uq_community_follow")),
    )
    op.create_index("ix_community_follow_followee", "community_follows", ["followee_id"])


def downgrade() -> None:
    op.drop_index("ix_community_follow_followee", table_name="community_follows")
    op.drop_table("community_follows")
    op.drop_index("ix_community_repost_user", table_name="community_reposts")
    op.drop_table("community_reposts")
    op.drop_index("ix_community_reaction_user", table_name="community_reactions")
    op.drop_table("community_reactions")
    op.drop_index("ix_community_comment_post_date", table_name="community_comments")
    op.drop_table("community_comments")
    op.drop_index("ix_community_post_visibility", table_name="community_posts")
    op.drop_index("ix_community_post_author_date", table_name="community_posts")
    op.drop_table("community_posts")
