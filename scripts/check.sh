#!/usr/bin/env bash
# Every gate the project recognises, in one command (spec §88 Definition of Done).
# Run before committing. Exits non-zero on the first failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "── API: lint ─────────────────────────────────────────"
(cd apps/api && python -m ruff check app tests seed.py migrations)

echo "── API: types ────────────────────────────────────────"
(cd apps/api && python -m mypy app)

echo "── API: tests ────────────────────────────────────────"
(cd apps/api && python -m pytest)

echo "── API: migrations (drift check on SQLite + PostgreSQL) ─"
(cd apps/api && rm -f _check.db \
  && DATABASE_URL="sqlite:///./_check.db" python -m alembic upgrade head >/dev/null \
  && DATABASE_URL="sqlite:///./_check.db" python -m alembic check \
  && rm -f _check.db)
if [[ -n "${DATABASE_URL:-}" && "${DATABASE_URL:-}" != sqlite* ]]; then
  (cd apps/api && python -m alembic upgrade head && python -m alembic check)
else
  echo "skipped PostgreSQL leg (export DATABASE_URL to a PostgreSQL URL to run it)"
fi

echo "── Web: types ────────────────────────────────────────"
(cd apps/web && npm run typecheck)

echo "── Web: build ────────────────────────────────────────"
(cd apps/web && npm run build)

echo "── All gates passed ──────────────────────────────────"
