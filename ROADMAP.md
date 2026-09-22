# ROADMAP — FOOTBALL OS

Rule (spec §96): no milestone opens until the previous one is *running, tested and visually verified*. Current gate status is maintained in this file.

| Milestone | Scope | Gate | Status |
| --- | --- | --- | --- |
| **M0 Foundation** | monorepo, git, CI, docs+ADRs, design system, Next.js, FastAPI, Postgres/pgvector compose, auth foundation, provider abstraction, health checks | both apps build, tests green, login works | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M1 Player + AI Coach vertical slice** | Create user → create player → profile → training → completion → AI Coach → progress → history | closed loop usable in browser with real persistence | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M2 Football Knowledge + RAG** | ingestion, chunking, embeddings, pgvector hybrid retrieval, rerank, citations, Football AI | answers carry resolvable source citations | ✅ verified 2026-09-21 ([evidence](docs/M2_VERIFICATION.md)) |
| **M3 Football World** | RealPlayer/Team/Competition/Match/Stats/News + unified search + SEO routes | 20 teams / 300 players / 130 matches / 500 articles synthetic world, public pages for all five entities | ✅ verified 2026-09-22 ([backend](docs/M3_VERIFICATION.md) · [web surface](docs/M3_WEB_VERIFICATION.md)) |
| **M4 Tactical Lab** | interactive board, formations, in/out possession, roles, animation, AI tactical analysis | 50 tactical systems + drag/draw/save/share + analysis with evidence | ✅ verified 2026-09-22 ([backend](docs/M4_VERIFICATION.md) · [web](docs/M4_WEB_VERIFICATION.md)) — analysis cites the corpus for 4 of 6 topics and refuses 2; 3D pitch and board sharing beyond one owner are open follow-ups |
| **M5 Video Analysis** | upload → storage → transcode job → frame extraction → vision provider → events → report | demo vision provider behind real interface | 🔨 pipeline verified 2026-09-22 ([evidence](docs/M5_VERIFICATION.md)) · upload UI and report page pending |
| **M6 Football Simulation** | simulation engine, Career Mode, manager challenges, squad/training/finance | results labelled fictional; engine deterministic-testable | ⬜ |
| **M7 Scouting + Recruitment** | scout search, shortlists, comparison, AI scout reports, transfer market | structured reports with role/team fit + risk | ⬜ |
| **M8 Club OS / Academy** | organisations, teams, coaches, IDP, curriculum, permissions, multi-tenant | B2B tenant isolation proven | ⬜ |
| **M9 Community** | feed, posts, comments, likes, follows, shared boards/plans | creator→content→feedback loop | ⬜ |
| **M10 Creator Economy** | creator profiles, programs, guides, entitlement/pricing architecture | no payment vendor required to demo | ⬜ |
| **M11 Multi-Agent Football AI** | orchestrator + research/data/tactical/training/scout/video/simulation/coach agents, agent memory | spec §33 and §87 composite tasks succeed on benchmark | ⬜ |
| **M12 Production hardening** | security, performance, observability, cost, caching, rate limits, governance, backup/DR | load + pen test report clean; **account-level erasure implemented** (today only player data is deletable — `DATA_POLICY.md` §3) | ⬜ |

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

**M3 Football World — done.** Backend evidence in [`docs/M3_VERIFICATION.md`](docs/M3_VERIFICATION.md), web-surface
evidence in [`docs/M3_WEB_VERIFICATION.md`](docs/M3_WEB_VERIFICATION.md).

Backend (verified 2026-09-21):

1. [x] seven tables + `0003_football_world` migration, `alembic upgrade head` and `alembic check` clean on pgvector
2. [x] seeded deterministic generator (`WorldRng` → `plan_world(seed)` → identical `fingerprint()`), fictional name tables, no scraped or licensed material
3. [x] idempotent sync: upsert by natural key, schema-fit validation before insert, second pass reports `changed=0`, deletions cascade with 0 orphan links
4. [x] 500-article newsroom that only quotes numbers present in the stat tables, `claim_class` separating fact / analysis / speculation, desk bylines and `source_name='synthetic-world'`
5. [x] one unified search over all five entity types, explainable ranking, per-hit path + provenance
6. [x] 12 public `/api/v1/world/*` routes registered and live, `GET /capabilities` reporting `m3_football_world` from the data rather than the code
7. [x] 41 world tests, 89 total, green on SQLite **and** PostgreSQL+pgvector; ruff + mypy clean; `docs/api/openapi.json` regenerated (40 paths / 44 operations)

Web surface (verified 2026-09-22):

1. [x] `/team/{slug}`, `/player/{slug}`, `/match/{slug}`, `/competition/{slug}`, `/news/{slug}` mounted at the exact §80 paths the API hands out — pages link through `path` fields, never by rebuilding a URL
2. [x] a world index (counted contents + §65 gate state) and the unified search page, both public and JS-free
3. [x] `sitemap.ts` gained those entries in the same commit: 983 `<loc>` values, asserted to match the API's own per-table counts, each answering 200
4. [x] `DEMO DATA` badging driven by each row's own `data_origin`/`is_demo_data` + the API disclaimer, and an explicit "no score yet" state for scheduled fixtures
5. [x] `visual-qa.mjs` extended with 42 world assertions and screenshots at 1440px and 375px against a production build (110/110)
6. [x] structured data per entity: `Dataset`, `SportsOrganization`, `SportsTeam`, `Athlete`, `SportsEvent`, `NewsArticle`, plus `SearchAction`; `/world/search` is `noindex, follow`

**M4 Tactical Lab — closed 2026-09-22.** The gate (50 systems + drag/draw/save/share + analysis with evidence) is met;
the items still open below it are follow-ups, not gate gaps. **Next: M5 Video Analysis** — upload → processing → frame
extraction → vision provider → events → analysis → report, with a demo vision provider behind the real interface
(spec §14, §45, §62: every frame-derived claim labelled, no invented tracking).

Verified 2026-09-22 (the pure layer + storage + reads, 99 tests):

1. [x] `pitch.py` — one metre coordinate system (origin at the team's own goal, Law 1 dimensions), clamping, thirds/lanes/zones, nearest-neighbour and centroid maths; a non-finite coordinate is rejected at construction
2. [x] `roles.py` — 14 roles, each with separate in- and out-of-possession duties, instructions, a stated risk, and the tactical attributes it demands (the same six the player model stores, so fit can be computed)
3. [x] `shapes.py` — ten authored base shapes × five temperaments; every shape validated to eleven slots, one keeper, on the grass
4. [x] `analysis.py` — in-possession shift and out-of-possession rescale (the block's span is exactly the authored `block_depth`, its top exactly `press_line_y`), eight metrics that each carry their own formula, and six named counterfactuals that move only the slots they name
5. [x] `plan.py` — 50 systems whose strengths/risks are **decided from their own measurements against the catalogue quartiles**, each sentence quoting the number and the percentile; deterministic fingerprint; `tactical_problems()` empty
6. [x] stored: `tactical_systems` + `0004` migration, `alembic upgrade head`/`check` clean, idempotent sync by slug (second pass `created=0 updated=0 unchanged=50`), a poisoned plan rolls back and writes nothing
7. [x] served: 5 public `/api/v1/tactics/*` routes (status, list with formation/temperament/search filters, detail, counterfactual, compare); metrics are recomputed from the stored coordinates, and every response repeats its provenance and disclaimer; `m4_tactical_lab` is derived from the row count
8. [x] 188 tests green on SQLite **and** PostgreSQL+pgvector; ruff + mypy clean (53 files); `docs/api/openapi.json` regenerated (45 paths / 49 operations)

Web surface (verified 2026-09-22):

9. [x] `/tactics` index — counted store, the eight measures with their formulas, one real board, filters by shape and temperament, JS-free pagination and search
10. [x] `/tactics/{slug}` — the last §80 route shape the site did not serve: both phases drawn from the stored metres by `components/pitch.tsx` (server-rendered SVG, Law 1 markings, band colours, no client JS), the transform stated with its own numbers, the roles in the field, and the graded verdicts quoted character for character from the API
11. [x] `/tactics/{slug}?change=…` — a counterfactual is a URL: before-positions hollow, each moved player drawn as an arrow, the delta table beside it, and clamps reported rather than hidden
12. [x] `/tactics/compare?a=&b=&phase=` — plain GET form, `noindex, follow`, both boards measured side by side
13. [x] `sitemap.ts` gained the 50 system URLs in the same commit (1034 `<loc>` entries, each answering 200); `PROJECT AUTHORED` labelling is single-sourced in `OriginBadge` and asserted absent-of-`DEMO DATA` in the walk
14. [x] 136/136 browser assertions at 1440px and 375px against a production build, 54 PNGs, zero console errors — `docs/M4_WEB_VERIFICATION.md`

Still open in M4:

1. [x] AI tactical analysis with citations: `GET /tactics/{slug}/feedback` puts six coaching questions to the M2 corpus
   through the same hybrid retrieval and answerability gates as `/knowledge`, and renders only the statements whose
   passage resolves — 4 cited, 2 refused for every system, because the library holds no passage on using width to
   stretch a block or on how high a team sits. The refusals are on the page with the gate that produced them; rewording
   the queries to score `answerable` would have bought citations to off-topic passages, which is worse than none
2. [x] `GET /tactics/{slug}/fit` — the session's player against the shape's six tactical demands, with published
   thresholds (`short ≤ -12`, `exceeds ≥ +4`), 409 `no_player` when there is no profile
3. [x] user boards, stored and served: `tactic_boards` + migration `0005`, 8 routes under `/api/v1/boards`
   (create/edit/delete, share by 32-hex token, revoke, public read-only view, ceiling of 24 per account).
   Coordinates are validated before they are written, metrics are recomputed on every read, a second account
   gets 404 rather than 403, and the shared payload exposes no owner identity — 17 tests on both engines plus
   a live HTTP pass (`docs/M4_VERIFICATION.md` §8)
4. [x] the drag interface: pointer-move the eleven dots on the same metre-scaled board, snap to 0.5 m, save — the walk
   proves the dragged position reaches the database (a midfielder measured 55 → 64.5 m) — then share a token link,
   revoke it, delete the board
5. [x] animation: `PhasePlayer` interpolates the two stored phases with the transform sentence beside it, badged
   `SIMULATION` and carrying AI_POLICY §2's exact stamp, which the walk asserts is present
6. [ ] 3D pitch (spec §13 lists 2D/3D; 2D is what ships)
7. [ ] boards are single-owner by design: no co-editors, comments or public gallery — that needs M9's permission and
   consent story, not just a listing
8. [ ] corpus follow-up so the two refused topics can be cited: author `data/knowledge` passages on width in attack and
   on defensive-line height, then re-run `python -m evals.run_rag_eval` — the gates must be re-measured, never loosened

**M5 Video Analysis — in progress.** Evidence: [`docs/M5_VERIFICATION.md`](docs/M5_VERIFICATION.md).

Verified 2026-09-22 (26 tests + a live HTTP pass):

1. [x] media layer: `ffprobe` container facts, `ffmpeg` frame sampling to PPM at an even interval, a
   PNG display copy, all as subprocesses with fixed argument lists; missing tools raise
   `MediaToolMissing` and the API answers 503 rather than inventing frames
2. [x] demo vision provider `demo-pixel-stats` behind the `VisionProvider` protocol that had been pinned
   since M0: pitch-green fraction, brightest-cell and **centroid of the non-pitch pixels**, movement
   events with shift, speed and confidence — every threshold in the payload, plus a `limitations`
   sentence saying it detects no players, ball or football events
3. [x] upload contract: container decided by **magic bytes** (a `MZ` file named `.mp4` → 415), size ceiling
   in one place (`UploadTooLarge` → 413), sha256 + byte count stored, 20 clips per account, storage keys
   that cannot escape the root, `var/` gitignored
4. [x] `video_assets` / `video_detections` + migration `0006`; `LocalStorageProvider` implemented at last
   (it said "Lands with M5"); 7 routes; `Job` and `ModelCall` rows written for real, including a failed
   ledger row when the media tools are absent — and the jobs endpoint states there is no queue
5. [x] ownership: every video read needs a session, another account gets 404 on all five doors, and the
   report omits `storage_key`; deletion removes the row, the detections and the bytes on disk

Still open in M5:

1. [ ] the web surface: an upload form (`/video`), the per-clip report page with the sampled frames, the
   detection timeline and a `<video>` element fed by the owner-only file route — no §80 route and no
   sitemap entry for anyone's clips, because they are private
2. [ ] frame overlay: draw the measured centroids on the displayed frame, so a viewer can see which
   pixels the numbers describe
3. [ ] event semantics (a real vision model or hand-labelled data) — mapping pixel movement to passes,
   shots or presses would be a claim this build cannot support
4. [ ] linking a clip to a user's player or an M6 match, and short shareable clips

Verification harness to extend: `pytest` on both databases, `python -m evals.run_rag_eval`,
`scripts/export_openapi.py`, `apps/web/scripts/visual-qa.mjs`. `docs/api/openapi.json` remains the
contract the web tier codes against.

## Cross-cutting gates (spec §80 SEO, §81 i18n)

Milestones do not own these; every public route must satisfy them as it lands.

- [x] §80 metadata layer: `metadataBase` from `SITE_URL`, per-route canonical + OpenGraph (`pageMetadata()`), site-level
  and document-level JSON-LD — verified in `docs/SEO_VERIFICATION.md` against a **production build**, not a dev server
- [x] §80 `sitemap.xml` and `robots.txt` generated from live API reads; every advertised `<loc>` is asserted to answer
  200, and session-gated routes are excluded from the sitemap and disallowed in robots rather than published as redirect chains
- [x] `visual-qa.mjs` carries the SEO assertions, the `/settings` locale and milestone rows, and 42 Football World
  assertions (**110/110**, run `202609212343` against a production build, 46 PNGs, zero console errors). It tags browser
  console errors with the route they occurred on, probes every sitemap `<loc>` through a bounded pool, and records an
  unhandled abort as a failed check plus a screenshot instead of one log line — `docs/M3_WEB_VERIFICATION.md` §5
- [x] §80 SEO routes for the world entities (`/player|team|match|competition|news/{slug}`) — mounted at the paths
  `SEO_ROUTES`/`web_path()` in `app/services/world/plan.py` emits, with the same `pageMetadata()` helper, and
  `sitemap.ts` lists all 983 of them from the API's own `path` fields (`docs/M3_WEB_VERIFICATION.md` §3)
- [x] §81 honesty: the UI is English-only, and the docs no longer claim otherwise. `GET /capabilities` now reports
  `locales: ["en"]` with `locales_planned: ["en","zh","zh-TW"]` beside it, so the wire matches the shipped interface.
  Remaining step: land `messages/{en,zh,zh-TW}.json` and switch the field when translations actually exist.
