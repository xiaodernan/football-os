"""Alembic environment.

Resolves the database URL from the application settings so migrations follow the
same portability rule as runtime (ADR-002): PostgreSQL in staging/production,
SQLite for local development.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: E402,F401  (register all mappers on Base.metadata)
from app.core.config import settings  # noqa: E402
from app.core.db import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def _is_sqlite() -> bool:
    return settings.database_url.startswith("sqlite")


# The HNSW index over `knowledge_chunks.embedding` is created by migration 0002 with
# `USING hnsw (embedding vector_cosine_ops) WITH (m, ef_construction)`. That shape is
# pgvector-specific and cannot be declared on the portable EmbeddingVector column, so
# autogenerate would only ever propose dropping it. It stays migration-owned.
_AUTOGENERATE_EXCLUDED = {"ix_chunk_embedding_hnsw"}


def _include_object(object: Any, *_args: Any, **_kwargs: Any) -> bool:
    return getattr(object, "name", None) not in _AUTOGENERATE_EXCLUDED


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=_include_object,
        render_as_batch=_is_sqlite(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=_include_object,
            render_as_batch=_is_sqlite(),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
