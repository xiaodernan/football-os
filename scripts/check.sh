#!/usr/bin/env bash
# Every gate the project recognises, in one command (spec §88 Definition of Done).
# Run before committing. Exits non-zero on the first failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "── API: lint ─────────────────────────────────────────"
# No path arguments on purpose. Ruff then walks the whole project, which is the target CI enforces — and the
# three targets this project has used (`app tests`, `app tests seed.py migrations`, and CI's list) disagree.
# A planted unused import in `evals/` is invisible to the first two and caught by this one, which is exactly
# how a committed tree passed its own documented gate three separate times. One command, no list to drift.
(cd apps/api && python -m ruff check)

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

echo "── Web: refusal-shape gate ───────────────────────────"
# Not a browser walk: this one loads apps/web/lib/api.ts through the repo's own TypeScript and feeds it the
# answer bodies pinned in apps/web/fixtures/refusals.json, every one of which apps/api/tests/test_error_answer_shape.py
# holds against the backend's bytes. It needs no server and no port, so it belongs with the other gates and not in
# a scheduled walk — and neither tsc (tsconfig excludes `scripts`) nor next lint (its dirs do not include `scripts`)
# reads a .mjs, so a runner has to name it or nothing does.
(cd apps/web && node scripts/qa-error-shape.mjs)

echo "── Web: script-inventory gate ────────────────────────"
# Who checks the checkers. Every invocable file in apps/web/scripts is either named by a runner this gate reads
# (check.sh, ci.yml, the package manifest) or exempt for a reason re-proved from its own bytes on every run — so
# "the browser walks are verified" cannot quietly become a claim carried by files nothing invokes. It reads files
# only: no server, no browser, no port, which is why it runs here rather than joining the live-tier walks.
(cd apps/web && node scripts/qa-gate-inventory.mjs)

echo "── Web: types ────────────────────────────────────────"
(cd apps/web && npm run typecheck)

echo "── Web: build ────────────────────────────────────────"
(cd apps/web && npm run build)

echo "── All gates passed ──────────────────────────────────"
