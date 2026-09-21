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

- `pytest` suite green (unit + API integration, no network needed).
- `ruff check` + `mypy app` clean for the API.
- `npm run typecheck` and `npm run build` clean for the web app.
- No `TODO`/`FIXME` placeholders in merged code (spec §89) — open an issue or a roadmap row instead.
- Every new user-visible string lives in `apps/web/messages/*.json` for all three locales (spec §81).
- Every new page uses design tokens + `components/ui/*` only (spec §73).

## Definition of Done per feature (spec §88)

UI · backend · database · API · validation · error handling · loading state · empty state · mobile · accessibility · tests · visual QA · documentation · git commit. All fourteen, or the feature is not done.

## Commit style

`feat(m1): explainable XP transitions on training completion` · `fix(coach): guard empty training history` · `docs(adrs): ADR-007 vector index`. Milestone tags: `m0-foundation`, `m1-vertical-slice`.

## Data & AI rules

Never commit secrets or `.env`. Never add copyrighted assets. Never fake data, stats, news, citations, video analysis or simulation. Provenance and DEMO DATA labelling are mandatory (`DATA_POLICY.md`, `AI_POLICY.md`).
