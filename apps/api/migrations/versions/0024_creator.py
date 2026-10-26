"""0024 — §36's creator tier: a publication that cites the corpus and stores none of it (M10, spec §36).

Three tables. `creator_profiles` is an account's creator **state** — the row's existence is the answer, which is
why no `is_creator` column exists on `users` and why `ROLES` is unchanged: a fact with two homes has to be kept in
step with itself. `creator_guides` holds a title, a section, the author's own summary and a visibility, and
`guide_citations` holds the addresses: `document_id` plus the chunk's `ordinal`, with the `text_hash` that sat there
when the citation was written.

That key is not a style choice. `services/knowledge/ingest.py` reuses the document row across re-syncs (its `id` is
stable, looked up by `slug`) but mints a **fresh `kch_…` id for every chunk**, so a citation keyed on a chunk id
would dangle the first time an operator touched the corpus. (document, ordinal) keeps resolving, and the stored
hash is what lets a read say *the passage moved since I cited it* instead of quietly reading something else.

`ondelete` follows §35's argument, not §57's: a guide is its author's own publication, so every key out of a
profile or guide CASCADEs and the account's records go with the account (§40's erasure right). The one exception is
`document_id`, which is RESTRICT: a corpus document is operator data, and deleting it must not silently take a
hundred people's guides down with it — the deletion has to fail and say why instead.

Nothing dialect-specific: every constraint is named through `op.f()` so both engines in the test matrix accept the
DDL as written.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creator_profiles",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("headline", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("bio", sa.String(length=1500), nullable=False, server_default=""),
        sa.Column("since", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_creator_profiles_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creator_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_creator_profile_user")),
        sa.UniqueConstraint("slug", name=op.f("uq_creator_profile_slug")),
    )
    op.create_index("ix_creator_profiles_slug", "creator_profiles", ["slug"])

    op.create_table(
        "creator_guides",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("author_id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=600), nullable=False, server_default=""),
        sa.Column("section", sa.String(length=16), nullable=False, server_default="plan"),
        sa.Column("visibility", sa.String(length=12), nullable=False, server_default="public"),
        sa.Column("published_on", sa.String(length=10), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_creator_guides_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creator_guides")),
        sa.UniqueConstraint("author_id", "slug", name=op.f("uq_creator_guide_slug")),
    )
    op.create_index("ix_creator_guide_author_date", "creator_guides", ["author_id", "published_on"])
    op.create_index("ix_creator_guide_section", "creator_guides", ["section", "published_on"])

    op.create_table(
        "guide_citations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("guide_id", sa.String(length=40), nullable=False),
        sa.Column("document_id", sa.String(length=40), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cited_text_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=400), nullable=False, server_default=""),
        sa.Column("data_origin", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["guide_id"], ["creator_guides.id"], name=op.f("fk_guide_citations_guides"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], name=op.f("fk_guide_citations_documents"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guide_citations")),
        sa.UniqueConstraint("guide_id", "document_id", "ordinal", name=op.f("uq_creator_citation")),
    )
    op.create_index("ix_creator_citation_document", "guide_citations", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_creator_citation_document", table_name="guide_citations")
    op.drop_table("guide_citations")
    op.drop_index("ix_creator_guide_section", table_name="creator_guides")
    op.drop_index("ix_creator_guide_author_date", table_name="creator_guides")
    op.drop_table("creator_guides")
    op.drop_index("ix_creator_profiles_slug", table_name="creator_profiles")
    op.drop_table("creator_profiles")
