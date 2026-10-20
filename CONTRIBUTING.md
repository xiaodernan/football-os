# CONTRIBUTING — FOOTBALL OS

## The loop every change follows (spec §67)

`research → plan → architect → implement → run → test → visual QA → fix → document → commit`

Skipping `run`/`test`/`visual QA` is not a shortcut, it is a defect.

## Local setup

```bash
cp apps/api/.env.example apps/api/.env
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r apps/api/requirements-dev.txt
alembic -c apps/api/alembic.ini upgrade head && python -m apps.api.seed   # demo world
uvicorn apps.api.app.main:app --reload --port 8000      # terminal 1
cd apps/web && npm install && npm run dev                      # terminal 2
```

Full stack with Postgres + pgvector: `docker compose -f infra/docker-compose.yml up -d`.

## Quality gates (CI enforces these)

Run all of them at once with `bash scripts/check.sh`. That script and `.github/workflows/ci.yml` call the same
commands on purpose — three different `ruff` targets have been used in this project's history, and a green local
run against the narrow one was not evidence that CI would be green.

- `pytest` suite green (unit + API integration, no network needed).
- The project's one lint target: `bash scripts/lint.sh`. It is the only place a ruff target is written down, and
  CI runs that same file. It lints all of `apps/api`, plus every committed `.py` outside that tree — the extra
  population is derived from `git ls-files` on every run, so a newly committed Python file is in target without
  anyone editing a list, and the count it prints is the scope it read. Two measurements shaped it: run from the
  repository root with `--config apps/api/pyproject.toml`, the same rules call `app.*` third-party and report 71
  bogus import-ordering errors, so ruff runs with `apps/api` as its project root; and the `ruff check` command this
  bullet used to publish walked only `apps/api`, which is how four committed files in `scripts/` passed a gate whose
  comment claimed the whole project. A planted unused import in `scripts/qa_db.py` is invisible to that command and
  caught by this one — measured 2026-10-20, and `python -m mypy app` is unchanged.
- `npm run typecheck` and `npm run build` clean for the web app.
- No `TODO`/`FIXME` placeholders in merged code (spec §89) — open an issue or a roadmap row instead.
- Every new user-visible string lives in `apps/web/messages/*.json` for all three locales (spec §81). The
  catalogues exist and both Chinese ones carry the full key set (2026-10-06); a string added to `en.json`
  without its `zh`/`zh-TW` values falls back to English on those pages until translated — add all three in the
  same commit.
- Every new page uses design tokens + `components/ui/*` only (spec §73).

## Definition of Done per feature (spec §88)

UI · backend · database · API · validation · error handling · loading state · empty state · mobile · accessibility · tests · visual QA · documentation · git commit. All fourteen, or the feature is not done.

## Commit style

`feat(m1): explainable XP transitions on training completion` · `fix(coach): guard empty training history` · `docs(adrs): ADR-007 vector index`. Milestone tags: `m0-foundation`, `m1-vertical-slice`.

## Data & AI rules

Never commit secrets or `.env`. Never add copyrighted assets. Never fake data, stats, news, citations, video analysis or simulation. Provenance and DEMO DATA labelling are mandatory (`DATA_POLICY.md`, `AI_POLICY.md`).
