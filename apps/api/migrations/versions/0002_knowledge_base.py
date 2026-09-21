"""knowledge base: documents, chunks with portable embeddings, query audit (spec §28-§29)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21 20:12:00.000000

`knowledge_chunks.embedding` is `vector(256)` on PostgreSQL (with the `vector` extension
and an HNSW cosine index) and a JSON array on the SQLite fallback — the same
`EmbeddingVector` type the models declare, so autogenerate stays quiet on both dialects.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.vector_type import EMBEDDING_DIM, EmbeddingVector

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("create extension if not exists vector")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("source_label", sa.String(length=400), nullable=False),
        sa.Column("editorial_confidence", sa.String(length=10), nullable=False),
        sa.Column("last_reviewed", sa.String(length=10), nullable=False),
        sa.Column("source_path", sa.String(length=400), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=60), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("data_origin", sa.String(length=20), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_knowledge_documents_category"), "knowledge_documents", ["category"], unique=False)

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("document_id", sa.String(length=40), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("haystack", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("applies_to", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", EmbeddingVector(EMBEDDING_DIM), nullable=False),
        sa.Column("embedding_model", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunk_document_ordinal"),
    )
    op.create_index(op.f("ix_knowledge_chunks_document_id"), "knowledge_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_knowledge_chunks_text_hash"), "knowledge_chunks", ["text_hash"], unique=False)
    op.create_index("ix_chunk_category_ordinal", "knowledge_chunks", ["category", "ordinal"], unique=False)

    op.create_table(
        "knowledge_queries",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("hit_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("hit_scores", sa.JSON(), nullable=False),
        sa.Column("answered", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("retrieval_backend", sa.String(length=20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_queries_user_id"), "knowledge_queries", ["user_id"], unique=False)

    if is_postgres:
        # HNSW on cosine: the index the pgvector `<=>` ORDER BY in retrieval.py uses.
        op.execute(
            "create index if not exists ix_chunk_embedding_hnsw on knowledge_chunks "
            "using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("drop index if exists ix_chunk_embedding_hnsw")
    op.drop_index(op.f("ix_knowledge_queries_user_id"), table_name="knowledge_queries")
    op.drop_table("knowledge_queries")
    op.drop_index("ix_chunk_category_ordinal", table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_text_hash"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_documents_category"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
