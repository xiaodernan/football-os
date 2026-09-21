# ROADMAP — FOOTBALL OS

Rule (spec §96): no milestone opens until the previous one is *running, tested and visually verified*. Current gate status is maintained in this file.

| Milestone | Scope | Gate | Status |
| --- | --- | --- | --- |
| **M0 Foundation** | monorepo, git, CI, docs+ADRs, design system, Next.js, FastAPI, Postgres/pgvector compose, auth foundation, provider abstraction, health checks | both apps build, tests green, login works | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M1 Player + AI Coach vertical slice** | Create user → create player → profile → training → completion → AI Coach → progress → history | closed loop usable in browser with real persistence | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M2 Football Knowledge + RAG** | ingestion, chunking, embeddings, pgvector hybrid retrieval, rerank, citations, Football AI | answers carry resolvable source citations | ✅ verified 2026-09-21 ([evidence](docs/M2_VERIFICATION.md)) |
| **M3 Football World** | RealPlayer/Team/Competition/Match/Stats/News + unified search + SEO routes | 20 teams / 300 players / 100 matches / 500 articles synthetic world | 🔨 backend verified 2026-09-21 ([evidence](docs/M3_VERIFICATION.md)) · web surface pending |
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

**M3 Football World.** The backend half is verified — evidence in `docs/M3_VERIFICATION.md`:

1. [x] seven tables + `0003_football_world` migration, `alembic upgrade head` and `alembic check` clean on pgvector
2. [x] seeded deterministic generator (`WorldRng` → `plan_world(seed)` → identical `fingerprint()`), fictional name tables, no scraped or licensed material
3. [x] idempotent sync: upsert by natural key, schema-fit validation before insert, second pass reports `changed=0`, deletions cascade with 0 orphan links
4. [x] 500-article newsroom that only quotes numbers present in the stat tables, `claim_class` separating fact / analysis / speculation, desk bylines and `source_name='synthetic-world'`
5. [x] one unified search over all five entity types, explainable ranking, per-hit path + provenance
6. [x] 12 public `/api/v1/world/*` routes registered and live, `GET /capabilities` reporting `m3_football_world` from the data rather than the code
7. [x] 39 world tests, 87 total, green on SQLite **and** PostgreSQL+pgvector; ruff + mypy clean; `docs/api/openapi.json` regenerated (40 paths / 44 operations)

What the M3 gate still needs — the world's public web surface:

1. [ ] `/team/{slug}`, `/player/{slug}`, `/match/{slug}`, `/competition/{slug}`, `/news/{slug}` pages fed by those routes, each with `pageMetadata()` and the §80 path the API already hands out
2. [ ] a world index (competitions → teams → fixtures → news) and the unified search page
3. [ ] `sitemap.ts` entries for every one of those routes **in the same commit**, plus a QA assertion that each advertised `<loc>` answers 200
4. [ ] `DEMO DATA` badging that renders the row's own `data_origin` and disclaimer, and an explicit "no score yet" state for scheduled fixtures
5. [ ] `visual-qa.mjs` extended with world assertions and screenshots at 1440px and 375px against a production build

Verification harness to extend: `pytest` on both databases, `python -m evals.run_rag_eval`,
`scripts/export_openapi.py`, `apps/web/scripts/visual-qa.mjs`. `docs/api/openapi.json` remains the
contract the web tier codes against.

## Cross-cutting gates (spec §80 SEO, §81 i18n)

Milestones do not own these; every public route must satisfy them as it lands.

- [x] §80 metadata layer: `metadataBase` from `SITE_URL`, per-route canonical + OpenGraph (`pageMetadata()`), site-level
  and document-level JSON-LD — verified in `docs/SEO_VERIFICATION.md` against a **production build**, not a dev server
- [x] §80 `sitemap.xml` and `robots.txt` generated from live API reads; every advertised `<loc>` is asserted to answer
  200, and session-gated routes are excluded from the sitemap and disallowed in robots rather than published as redirect chains
- [x] `visual-qa.mjs` carries the SEO assertions (66/66, run stamp `202609212143`) and now tags browser console errors with the
  route they occurred on, so a hydration or fetch failure is localisable instead of a minified code
- [ ] §80 SEO routes for the world entities (`/player|team|match|competition|news/{slug}`) — the API already emits exactly these paths from
  one table (`SEO_ROUTES`/`web_path()` in `app/services/world/plan.py`); the pages must mount them with the same `pageMetadata()`
  helper, and `sitemap.ts` must gain those entries in the same commit, or the sitemap under-reports the site
- [x] §81 honesty: the UI is English-only, and the docs no longer claim otherwise. `GET /capabilities` now reports
  `locales: ["en"]` with `locales_planned: ["en","zh","zh-TW"]` beside it, so the wire matches the shipped interface.
  Remaining step: land `messages/{en,zh,zh-TW}.json` and switch the field when translations actually exist.
