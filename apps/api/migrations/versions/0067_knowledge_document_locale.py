"""The knowledge corpus learns its second language (Item 141).

`knowledge_documents` gains a `locale` column so one retrieval window can never mix a
Chinese reader's question with an English passage and pass it off as grounded in their
language. Existing rows are `en` — the corpus was authored in English up to this migration.

Revision ID: 0067
Revises: 0066
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("locale", sa.String(length=8), nullable=False, server_default="en"))
    op.create_index("ix_knowledge_documents_locale", "knowledge_documents", ["locale"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_locale", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "locale")
