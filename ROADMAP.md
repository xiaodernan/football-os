# ROADMAP — FOOTBALL OS

Rule (spec §96): no milestone opens until the previous one is *running, tested and visually verified*. Current gate status is maintained in this file.

| Milestone | Scope | Gate | Status |
| --- | --- | --- | --- |
| **M0 Foundation** | monorepo, git, CI, docs+ADRs, design system, Next.js, FastAPI, Postgres/pgvector compose, auth foundation, provider abstraction, health checks | both apps build, tests green, login works | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M1 Player + AI Coach vertical slice** | Create user → create player → profile → training → completion → AI Coach → progress → history | closed loop usable in browser with real persistence | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M2 Football Knowledge + RAG** | ingestion, chunking, embeddings, pgvector hybrid retrieval, rerank, citations, Football AI | answers carry resolvable source citations | ✅ verified 2026-09-21 ([evidence](docs/M2_VERIFICATION.md)) |
| **M3 Football World** | RealPlayer/Team/Competition/Match/Stats/News + unified search + SEO routes | 20 teams / 300 players / 100 matches / 500 articles synthetic world | 🔨 in progress |
| **M4 Tactical Lab** | interactive board, formations, in/out possession, roles, animation, AI tactical analysis | drag/draw/save/share + analysis with evidence | ⬜ |
| **M5 Video Analysis** | upload → storage → transcode job → frame extraction → vision provider → events → report | demo vision provider behind real interface | ⬜ |
| **M6 Football Simulation** | simulation engine, Career Mode, manager challenges, squad/training/finance | results labelled fictional; engine deterministic-testable | ⬜ |
| **M7 Scouting + Recruitment** | scout search, shortlists, comparison, AI scout reports, transfer market | structured reports with role/team fit + risk | ⬜ |
| **M8 Club OS / Academy** | organisations, teams, coaches, IDP, curriculum, permissions, multi-tenant | B2B tenant isolation proven | ⬜ |
| **M9 Community** | feed, posts, comments, likes, follows, shared boards/plans | creator→content→feedback loop | ⬜ |
| **M10 Creator Economy** | creator profiles, programs, guides, entitlement/pricing architecture | no payment vendor required to demo | ⬜ |
| **M11 Multi-Agent Football AI** | orchestrator + research/data/tactical/training/scout/video/simulation/coach agents, agent memory | spec §33 and §87 composite tasks succeed on benchmark | ⬜ |
| **M12 Production hardening** | security, performance, observability, cost, caching, rate limits, governance, backup/DR | load + pen test report clean | ⬜ |

## M0 exit criteria (verified)

- [x] `git init`, `.gitignore`, no secrets tracked
- [x] `PROJECT_AUDIT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `ADR/*`, `SECURITY.md`, `DATA_POLICY.md`, `AI_POLICY.md`, `CONTRIBUTING.md`
- [x] FastAPI boots, `/healthz`, `/api/v1/*` OpenAPI available, migrations run
- [x] Next.js builds, design system tokens present, dark premium shell renders
- [x] Auth foundation: register, login, JWT, RBAC guard
- [x] Provider abstraction with DEMO MODE fallback that self-labels
- [x] CI workflow (install → lint → test → build)
- [x] Docker Postgres + pgvector verified on this host: compose healthy, `alembic upgrade head` + `alembic check` (no drift), 21 tables, `vector` extension, and the full pytest suite green against it — see `docs/M0_M1_VERIFICATION.md` §1.3–1.5

## M1 exit criteria (the first real FOOTBALL OS loop)

1. register → 2. create UserPlayer (position, age, level, foot, goal) → 3. derive archetype + attributes (explainable) → 4. player card renders → 5. ask Coach "What should I train today?" → 6. session created from training catalogue with objective/setup/coaching points/mistakes/progression/test → 7. complete session with self-rated execution → 8. XP awarded with reason + attribute delta with reason → 9. progress page shows level/streak/skill curves → 10. history page lists every session with its evidence → 11. coach follow-up message reflects the new state → 12. API + engine tests green → 13. screenshots captured on desktop + mobile viewport.

All 13 are verified: `docs/M0_M1_VERIFICATION.md` §2 maps each one to a passing check in
`apps/web/scripts/visual-qa.mjs` (34/34 browser assertions, 19 PNGs captured to `docs/screenshots/`) plus the
23-test API/engine suite on SQLite and PostgreSQL.

## Now → next session

**M2 Football Knowledge + RAG** — verified end to end (backend + web surface). Exit criteria:

1. [x] corpus in `data/knowledge` with the frontmatter contract (`id/title/category/tags/applies_to/difficulty/source/confidence/last_reviewed`), provenance labelled `project-authored`
2. [x] ingestion: clean → section split → 220–1300 char chunks with the title prefixed → embeddings → rows; idempotent by content hash; deletions propagate; `--force-knowledge` re-embeds
3. [x] portable vectors (ADR-002): `vector(256)` + HNSW on PostgreSQL, JSON + in-process cosine on the SQLite fallback, and the response names its own backend
4. [x] hybrid retrieval: semantic + BM25 keyword + reciprocal rank fusion + deterministic feature rerank, all under one metadata-filter universe (category/position/difficulty/tag/document)
5. [x] citations: every hit carries a verbatim `quote`, `chunk_id`, `slug#ordinal` deep link; 64/64 quotes verified byte-for-byte against stored chunks
6. [x] answers: extractive digest in demo mode, LLM path only with a real key, confidence + `reasons[]` + `sources[]` + disclaimer, query audit row
7. [x] refusal: out-of-scope questions are refused with the rare terms it looked for; empty rare-term set now refuses instead of answering
8. [x] evaluation harness (`evals/golden_rag.json` + `run_rag_eval.py`) as a CI gate: recall@5 1.0 · MRR 0.922 · citation integrity 1.0 · refusal accuracy 1.0 · hybrid delta 0.0, green on both databases
9. [x] 48 tests on SQLite and PostgreSQL+pgvector; ruff + mypy clean; `alembic upgrade head` + `alembic check` clean; `docs/api/openapi.json` regenerated with all six `/api/v1/knowledge*` routes
10. [x] `/knowledge` web surface (library, search, ask with citations) verified in the browser at 1440px and 375px — 51/51 assertions, 25 PNGs, evidence in `docs/M2_VERIFICATION.md` §3 (the run caught and fixed a real citation-link defect)

After M2 closes: **M3 Football World** (RealPlayer/Team/Competition/Match/Stats/News + unified search + SEO
routes). The model classes are already reserved in `app/models/__init__.py`; `docs/api/openapi.json` remains the
contract the web tier codes against, and the verification harness to extend is `pytest` on both databases,
`python -m evals.run_rag_eval`, `scripts/export_openapi.py` and `apps/web/scripts/visual-qa.mjs`.
