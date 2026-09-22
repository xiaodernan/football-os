# FOOTBALL OS

> **The Operating System for Football** — WATCH. UNDERSTAND. TRAIN. PLAY. MANAGE. BECOME.

One platform connecting the real football world, personal football development, football simulation and football AI. Not a news site, not a score app, not an FM clone, not a chatbot wrapper.

**Status:** M0 Foundation · M1 vertical slice (My Football → Player → Training → AI Coach → Progress → History) · M2 Football Knowledge + RAG (16-document corpus → chunking → embeddings → hybrid retrieval + rerank → cited, refusal-capable answers) · M3 Football World — deterministic synthetic world (10 competitions · 20 teams · 300 players · 130 matches · 3,172 stat lines · 500 news articles) behind 12 `/api/v1/world/*` routes with unified search, **and** its public web surface (`/world`, five browsable lists, `/world/search`, and the §80 pages `/player|team|match|competition|news/{slug}`) — all implemented and **verified**: 110/110 browser assertions at 1440px and 375px against a **production build**, 983 sitemap URLs each answering 200, five RAG evaluation gates green on both engines. The whole API suite is 218 tests, green on SQLite *and* PostgreSQL+pgvector. Evidence: `docs/M0_M1_VERIFICATION.md`, `docs/M2_VERIFICATION.md`, `docs/M3_VERIFICATION.md`, `docs/M3_WEB_VERIFICATION.md`; SEO surface: `docs/SEO_VERIFICATION.md`; gate table: `ROADMAP.md`; environment audit: `docs/PROJECT_AUDIT.md`. M4 Tactical Lab is **verified end to end**: pitch geometry in metres, 14 roles with separate in/out-possession duties, 10 shapes × 5 temperaments = the 50 systems §65 asks for, eight metrics that each ship their own formula, six named counterfactuals, and an analysis that cites the knowledge corpus for what it can and refuses the rest (`docs/M4_VERIFICATION.md`); served by `/tactics`, `/tactics/{slug}`, `/tactics/compare`, a draggable **My boards** area (`/tactics/boards`), and a public read-only share link (`/tactics/shared/{token}`) with the pitch drawn as SVG from the same metres the measurements come from — **151/151** browser assertions, 1034 sitemap URLs, 218 API tests on both engines (`docs/M4_WEB_VERIFICATION.md`). Still open in M4 as follow-ups rather than gate items: a 3D pitch, boards beyond single ownership (M9's consent story), and two knowledge-corpus passages (width in attack, defensive-line height) so the analysis can cite what it currently declines to claim.

## Architecture at a glance

```
apps/web   Next.js 15 + TypeScript   UI · BFF · auth UX · public Football World + knowledge pages · SEO metadata (canonical/OG/JSON-LD) · sitemap + robots · dark design system
apps/api   FastAPI + SQLAlchemy 2     auth · football world model · training catalogue · coach engine
                                          progression(XP→skill→attribute, explainable) · providers · jobs
                                          knowledge base: data/knowledge → chunks → embeddings → hybrid retrieval → citations
                                          football world: seeded generator → idempotent sync → unified search → /api/v1/world/*
                                          tactical lab: pitch geometry → 10 shapes × 5 temperaments → 50 measured systems
PostgreSQL + pgvector (docker compose)   dev fallback: SQLite via DATABASE_URL
```

No Redis, no Kafka, no microservices, no Java — added only against a measured bottleneck (ADR-001, ADR-006).

## Quick start

This project owns ports **8731** (API), **3210** (web) and **54321** (its own Postgres container) on this host —
`scripts/dev.sh` starts both tiers on them. Nothing else is bound or restarted by these commands.

```bash
# 1. API
python -m venv .venv && .venv/Scripts/activate        # or use a global Python 3.11
pip install -r apps/api/requirements.txt
cp apps/api/.env.example apps/api/.env                # set DATABASE_URL for pgvector, or leave it for SQLite
cd apps/api && alembic upgrade head && python -m seed  # catalogue + knowledge corpus, both idempotent
uvicorn app.main:app --reload --port 8731

# 2. Web (new terminal)
cd apps/web && npm install && npm run dev    # http://localhost:3210

# optional: real Postgres + pgvector
docker compose -f infra/docker-compose.yml up -d
```

Verification commands: `pytest` and `python -m evals.run_rag_eval` (API, both databases) ·
`npm run typecheck && npm run lint && npm run build` and `npm run qa:visual` (web).

## The first real loop (M1)

1. Register → 2. Create your player (position, age, level, foot, goal) → 3. Attributes + archetype derived with visible reasons → 4. Ask the Coach *"What should I train today?"* → 5. Train (objective, setup, coaching points, common mistakes, progression, test) → 6. Complete → 7. XP + attribute delta, each with its reason → 8. Progress and history update → 9. Coach's next message reflects your actual new state.

## The knowledge loop (M2)

1. Browse the library by category — every document shows who wrote it, when it was reviewed and how many chunks it is → 2. Filter by position, difficulty or tag, which really narrows the retrieval universe (the response says how many chunks were scanned) → 3. Search in `semantic`, `keyword` or `hybrid` mode and see each leg's score, the rerank features and why rank 1 won → 4. Ask a question and get an answer built only from numbered passages, each with a verbatim quote and a deep link → 5. Ask something the corpus cannot support and it refuses, naming the rare terms it looked for → 6. Every answer carries `demo_mode`, `confidence`, `reasons[]`, `sources[]` and a disclaimer, so nothing generated here is presented as fact.

## Honesty guarantees

- Synthetic world data is badged `DEMO DATA`; unavailable metrics show `Data unavailable`.
- AI output without real provider keys runs in self-labelled `DEMO MODE`.
- Simulations are badged fictional. Progression is rule-based and explainable, never random.
- No copyrighted assets, no scraped paywalled data, no fabricated citations.
- The UI speaks English only today. `GET /capabilities` answers `locales: ["en","zh","zh-TW"]` as the §81 target, not as a
  shipped feature — the translation layer itself is not built yet.

## Documentation

`ARCHITECTURE.md` · `ROADMAP.md` · `docs/PROJECT_AUDIT.md` · `docs/adr/ADR-001…006` · `SECURITY.md` · `DATA_POLICY.md` · `AI_POLICY.md` · `CONTRIBUTING.md`

## License / disclaimer

Football names, players, teams and events shown in the demo world are fictional and generated. AI analysis is an estimate and not professional medical, scouting or performance certification.
