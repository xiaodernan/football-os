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
# The two legs below are CI's PostgreSQL job, and one variable decides both: the suite above switches engines on
# FOOTBALL_OS_TEST_DATABASE_URL (`tests/conftest.py`), so the seed and the RAG benchmark take the same switch rather
# than a second one to drift from the first. CI runs the suite twice — once per engine — because SQLite accepts
# over-length strings and lax types; a local run is one engine per invocation, chosen by this variable.
if [[ -n "${FOOTBALL_OS_TEST_DATABASE_URL:-}" && "${FOOTBALL_OS_TEST_DATABASE_URL:-}" != sqlite* ]]; then
  echo "── API: seed on the PostgreSQL engine ───────────────"
  (cd apps/api && python -m seed --with-demo-user)
  echo "── API: RAG evaluation gates (pgvector leg) ─────────"
  # Spec §64's benchmark is the reviewer for any change to retrieval, chunking or the corpus. The suite gate
  # (`tests/test_knowledge_rag.py`) already holds the same thresholds on whichever engine the suite is on;
  # this leg is CI's report shape on the engine CI runs it on, so a quiet corpus change cannot merge.
  (cd apps/api && python -m evals.run_rag_eval)
else
  echo "skipped the seed and RAG-benchmark PostgreSQL legs (export FOOTBALL_OS_TEST_DATABASE_URL to a throwaway PostgreSQL URL; the suite's own gate tests/test_knowledge_rag.py ran above)"
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

echo "── Web: middleware gating gate ───────────────────────"
# Which routes a signed-out reader may reach is one function's decision, and a prefix list that reaches down into
# `/video/shared/<token>` made two share-link pages answer 307 to /login — a link handed to a person with no
# account. This gate loads `isProtected` out of middleware.ts itself (transpiled, called), and asks it of all 59
# page routes, so a change to the matching logic moves the verdict and not only the lists. Files only: no server,
# no browser, which is why it runs here rather than in the live-tier walks that would need a token-free plane.
(cd apps/web && node scripts/qa-middleware-gating.mjs)

echo "── Web: types ────────────────────────────────────────"
(cd apps/web && npm run typecheck)

echo "── Web: build ────────────────────────────────────────"
(cd apps/web && npm run build)

echo "── All gates passed ──────────────────────────────────"
