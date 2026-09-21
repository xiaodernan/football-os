# ADR-002 — Portable ORM: SQLAlchemy 2 + Alembic, Postgres target, SQLite dev fallback

- Status: Accepted · Relates to: PRINCIPLE 1, §68 (when something fails), §43
- **Context**: Target database is PostgreSQL + pgvector. This host has Docker but no `psql` client, and CI/offline runs must still execute the full test suite.
- **Problem**: The product must be verifiable end-to-end without a guaranteed Postgres, while never shipping a fake persistence layer.
- **Options**: (a) require Postgres always; (b) SQLite-only; (c) SQLAlchemy with `DATABASE_URL` swap — SQLite for local/tests, Postgres+pgvector for `docker-compose`/prod.
- **Decision**: (c). Models use only portable types (`JSON`, `String`, numeric, FK); vector columns are introduced in M2 through a Postgres-only Alembic branch guarded by a dialect check, with a documented `InMemoryVectorIndex` fallback for SQLite that keeps the same interface.
- **Consequences**: Tests are honest (they exercise the real repository code, not mocks). Migration drift must be checked on both dialects in CI. pgvector features (ivfflat/hnsw, `<=>`) only run under Postgres; the capability is reported by `/healthz` so the UI can label degraded vector search instead of pretending.
