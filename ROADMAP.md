# ROADMAP — FOOTBALL OS

Rule (spec §96): no milestone opens until the previous one is *running, tested and visually verified*. Current gate status is maintained in this file.

| Milestone | Scope | Gate | Status |
| --- | --- | --- | --- |
| **M0 Foundation** | monorepo, git, CI, docs+ADRs, design system, Next.js, FastAPI, Postgres/pgvector compose, auth foundation, provider abstraction, health checks | both apps build, tests green, login works | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M1 Player + AI Coach vertical slice** | Create user → create player → profile → training → completion → AI Coach → progress → history | closed loop usable in browser with real persistence | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M2 Football Knowledge + RAG** | ingestion, chunking, embeddings, pgvector hybrid retrieval, rerank, citations, Football AI | answers carry resolvable source citations | ✅ verified 2026-09-21 ([evidence](docs/M2_VERIFICATION.md)) |
| **M3 Football World** | RealPlayer/Team/Competition/Match/Stats/News + unified search + SEO routes | 20 teams / 300 players / 130 matches / 500 articles synthetic world, public pages for all five entities | ✅ verified 2026-09-22 ([backend](docs/M3_VERIFICATION.md) · [web surface](docs/M3_WEB_VERIFICATION.md)) — world 3.2 (2026-09-23) added the sixth §65 gate item, 100 training sessions, browsed at `/world/training` |
| **M4 Tactical Lab** | interactive board, formations, in/out possession, roles, animation, AI tactical analysis | 50 tactical systems + drag/draw/save/share + analysis with evidence | ✅ verified 2026-09-22 ([backend](docs/M4_VERIFICATION.md) · [web](docs/M4_WEB_VERIFICATION.md)) — analysis cites the corpus for 6 of 6 topics on all 50 systems (2 were refused until the corpus gained the missing passages); 3D pitch and board sharing beyond one owner are open follow-ups |
| **M5 Video Analysis** | upload → storage → transcode job → frame extraction → vision provider → events → report | demo vision provider behind real interface | ✅ verified 2026-09-22 ([pipeline](docs/M5_VERIFICATION.md) · [web](docs/M5_WEB_VERIFICATION.md)) — upload, report, detection timeline and owner-only byte-range playback proven in the browser |
| **M6 Football Simulation** | simulation engine, Career Mode, manager challenges, squad/training/finance | results labelled fictional; engine deterministic-testable | 🟡 in progress — engine, `/simulate`, the §65 training log and **Career Mode including its page** all browser-verified 2026-09-23 ([engine+career backend](docs/M6_VERIFICATION.md) §10 · [simulator+log](docs/M6_WEB_VERIFICATION.md) · [career web](docs/M6_CAREER_WEB_VERIFICATION.md)); **manager live challenges (§21) backend verified on both engines 2026-09-24** ([docs/M6_VERIFICATION.md](docs/M6_VERIFICATION.md) §11) — 6 scenarios, window enforced in `play_round`, verdicts recomputed; its page and the transfer market (§22) outstanding |
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
the items still open below it are follow-ups, not gate gaps. **M5 Video Analysis — closed the same day**, pipeline and
browser both. **M6 Football Simulation — first slice verified 2026-09-23**: the deterministic possession-block engine,
its `/simulate` surface, and the last outstanding §65 gate item (100 world training sessions, browsable at
`/world/training`). **Next inside M6:** Career Mode (§20) as the container a season is played in, then manager live
challenges (§21) and the transfer market (§22), with every result labelled fictional rather than observed.

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
   passage resolves — first measured as 4 cited and 2 refused for every system, because the library held no passage on
   using width to stretch a block or on how high a team sits. The refusals went on the page with the gate that produced
   them; rewording the queries to score `answerable` would have bought citations to off-topic passages, which is worse
   than none. The gap was then closed by **writing the two missing passages** (`width-in-attack`, `squad-height-and-territory`),
   not by moving a threshold: 6 cited and 0 refused across all 50 systems, with `run_rag_eval` still at recall 1.0 /
   citation integrity 1.0 / refusal accuracy 1.0 on 18 documents and 138 chunks
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
8. [x] corpus follow-up so the two refused topics can be cited: `data/knowledge/tactics/width-in-attack.md` and
   `squad-height-and-territory.md` authored to the corpus's own shape rules, `python -m evals.run_rag_eval` re-measured
   rather than loosened — recall@5 1.0, MRR 0.9167, citation integrity 1.0, refusal accuracy 1.0 on 18 documents /
   138 chunks, with two new golden questions both ranking first

**M5 Video Analysis — verified.** Evidence: [`docs/M5_VERIFICATION.md`](docs/M5_VERIFICATION.md) (pipeline) ·
[`docs/M5_WEB_VERIFICATION.md`](docs/M5_WEB_VERIFICATION.md) (browser).

Verified 2026-09-22 (29 video tests on both engines + a live HTTP pass + a browser walk):

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
6. [x] the web surface: `/video` holds the upload form and `/video/{id}` the report — detection timeline, the
   sampled frames shown as the PNGs `ffmpeg` wrote, and a `<video>` whose source is the owner-only file route.
   That route answers byte ranges, and the cookie proxy now carries `Range` out and `Content-Range` back, so the
   browser seeks instead of downloading: `206 bytes 0-99/58056`, suffix ranges, `416 bytes */58056`. No §80 route
   and no sitemap entry — the report is `noindex` and robots keeps `/video` out of the crawl. 12 checks in that
   block, **164/164** in the walk, 58 screenshots (`docs/M5_WEB_VERIFICATION.md`)

Still open in M5:

1. [ ] frame overlay: draw the measured centroids on the displayed frame, so a viewer can see which
   pixels the numbers describe
2. [ ] event semantics (a real vision model or hand-labelled data) — mapping pixel movement to passes,
   shots or presses would be a claim this build cannot support
3. [ ] linking a clip to a user's player or an M6 match, and short shareable clips

Verification harness to extend: `pytest` on both databases, `python -m evals.run_rag_eval`,
`scripts/export_openapi.py`, `apps/web/scripts/visual-qa.mjs`. `docs/api/openapi.json` remains the
contract the web tier codes against.

**M6 Football Simulation (first slice) — verified 2026-09-23.** Evidence:
[`docs/M6_VERIFICATION.md`](docs/M6_VERIFICATION.md) (engine + storage + reads) ·
[`docs/M6_WEB_VERIFICATION.md`](docs/M6_WEB_VERIFICATION.md) (browser).

**Manager live challenges (§21) — backend verified, both engines, 2026-09-24**
(`docs/M6_VERIFICATION.md` §11). Six authored scenarios, each time-limited by a window the engine
enforces, goal-based on objectives the caller cannot lower, and reward-based on a verdict recomputed
from the run's own rows. 31 tests, a live pass on a seeded database, and every constraint publishing
whether it binds — so "no transfers" and "academy players only" read as stated intent rather than as
rules something applied. **No page for it yet.**

Verified 2026-09-23 (317 API tests on both engines + a browser walk at 190/190):

1. [x] `possession-block-v1@1.0.0`: a 90-minute match as fifteen six-minute blocks, each side measured from ten
   factor rows through nine named rates, every rate shipping with the expression that produced it
2. [x] determinism a stranger can check: `sha256` digest over the inputs, stored beside the report in `sim_matches`
   (migration `0007`), and `POST /api/v1/simulate/{ident}/replay` re-playing from the stored seed + minutes + two
   systems so the page prints `stored · replayed · Identical.` rather than asking to be believed
3. [x] every result labelled fictional: `data_origin='simulation'`, `is_demo_data=true`, the simulation disclaimer on
   the row and on `/simulate`, and no claim that any of it was observed
4. [x] ownership: `/simulate` is behind the session wall, another account gets 404 on every door, and deleting a
   match removes it for its owner (the walk re-reads both rows and gets 404)
5. [x] the last §65 gate item: `real_training_sessions` (migration `0008`), 100 rows drawn in proportion to the
   minutes the generated players played, each quoting a catalogue drill and copying its duration and difficulty,
   `load_units = duration_min × rpe` computed on request — served by `GET /api/v1/world/training`, browsed at
   `/world/training`, and printed as `MEETS` by `/world`'s own counts table
6. [x] a session-rotation defect the walk found rather than a test: parallel proxied calls signed the user out of
   their own account. Fixed with `REFRESH_REUSE_GRACE_SECONDS` (ADR-003 amended), destroy-on-stale-reuse, logout that
   deletes the credential, a single-flight refresh in the cookie proxy, and four tests that age `revoked_at` instead
   of sleeping
7. [x] the console gate now attributes a failed request by its **own URL** (`message.location().url`), not by the
   page the reader was on — which is what let it name the walk's own doubled path
9. [x] **Career Mode's page** (same day, §20): `/career` and `/career/[slug]` — the form that states a manager, club, philosophy, tactical system, budget and objectives, and the season page whose record, objective verdicts, fixture list and table of clubs met are all read back from the API's sums. Behind the session wall like the simulator, disallowed in robots, absent from the sitemap, reachable from a panel action on `/simulate`. 17 checks in the walk, quoted in [`docs/M6_CAREER_WEB_VERIFICATION.md`](docs/M6_CAREER_WEB_VERIFICATION.md)
10. [x] **Career Mode's backend** (same day, §20): `careers` + `career_fixtures` (migration `0009`), a fixture
   list that is a *rotation* anyone can reproduce, rounds decided by `run_simulation` so there is still only one
   match model, a record and a mini-table summed from the career's own rows with their formulas printed,
   objectives that must be stated before a career can open, and 6 `/api/v1/careers/*` routes — 28 tests on both
   engines (`docs/M6_VERIFICATION.md` §10). **No page for it yet**, and the budget is stated intent nothing spends.

Still open in M6:

1. [ ] **a page for the challenges** — the catalogue at `/challenges`, a start form, and a run page that
   shows the verdict beside the fixtures it was summed from. Backend only today; `GET /challenges` is
   public because the scenarios are this project's own fiction, while the run routes sit behind the
   same session wall as careers, so a foreign run reads as 404
2. [ ] the transfer market (§22) — which is what would make a budget more than a stated number, and
   what would let `no_transfers` become an enforced constraint instead of a published one
3. [ ] squad and training carry-over between matches
4. [ ] a `sim_events` table so the timeline is stored rather than regenerated
5. [ ] rendering the `training_log` the player detail route already returns
6. [x] **a per-run test database** — `conftest.py` pointed every run at one fixed `football_os_pytest`
   and its session fixture began with `drop_all()`, so two overlapping runs made the other's tables
   vanish. Caught while re-running §21: one spurious `relation "training_drills" does not exist` in a
   test that never queries that table, green on rerun. Fixed by creating, provisioning (`vector`) and
   dropping a uuid-suffixed database per server-backed run — proved by **two full 376-test suites
   running concurrently, both green, nothing left behind** (`docs/M6_VERIFICATION.md` §13)

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
