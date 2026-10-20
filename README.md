# FOOTBALL OS

> **The Operating System for Football** — WATCH. UNDERSTAND. TRAIN. PLAY. MANAGE. BECOME.

One platform connecting the real football world, personal football development, football simulation and football AI. Not a news site, not a score app, not an FM clone, not a chatbot wrapper.

**Status:** M0–M5 are implemented and **verified**; M6 Football Simulation is open — its engine, its `/simulate`
surface, the last §65 demo-world item (100 training sessions), Career Mode's backend *and* page, and manager live
challenges (§21) with **their page**, browser-verified 2026-09-24. The transfer market (§22) is the next slice inside it.

* **M0 Foundation · M1 vertical slice** — register → create player → derive attributes → training → completion → XP and attribute deltas with their reasons → history: one closed loop with real persistence, not a form that pretends (`docs/M0_M1_VERIFICATION.md`).
* **M2 Football Knowledge + RAG** — an 18-document / 138-chunk corpus → chunking → embeddings → hybrid retrieval + rerank → cited, refusal-capable answers. Five evaluation gates green on both engines, re-measured rather than loosened when the corpus grew (`docs/M2_VERIFICATION.md`).
* **M3 Football World** — deterministic synthetic world (10 competitions · 20 teams · 300 players · 130 matches · 3,172 stat lines · 500 news articles) behind 12 `/api/v1/world/*` routes with unified search, **and** its public web surface (`/world`, five browsable lists, `/world/search`, and the §80 pages `/player|team|match|competition|news/{slug}`) (`docs/M3_VERIFICATION.md`, `docs/M3_WEB_VERIFICATION.md`).
* **M4 Tactical Lab** — pitch geometry in metres, 14 roles with separate in/out-possession duties, 10 shapes × 5 temperaments = the 50 systems §65 asks for, eight metrics that each ship their own formula, six named counterfactuals, and an analysis that cites the corpus for all six of its topics on every one of the 50 systems — two of them were refused until the corpus gained the passages they needed (`docs/M4_VERIFICATION.md`). Served by `/tactics`, `/tactics/{slug}`, `/tactics/compare`, a draggable **My boards** area (`/tactics/boards`) and a public read-only share link (`/tactics/shared/{token}`), with the pitch drawn as SVG from the same metres the measurements come from (`docs/M4_WEB_VERIFICATION.md`).
* **M5 Video Analysis** — `ffprobe` container facts and `ffmpeg` frame sampling as fixed-argv subprocesses, magic-byte upload validation, `video_assets`/`video_detections`, 7 `/api/v1/video/*` routes and `Job`/`model_calls` rows written for real, behind a demo vision provider that measures the centre of non-pitch pixels and carries its thresholds and a `limitations` sentence saying it detects no players, ball or football events (`docs/M5_VERIFICATION.md`). `/video` and `/video/{id}` upload, report, detection timeline and frame strip, with owner-only playback that answers byte ranges through the cookie proxy — `206` slices, suffix ranges, `416` past the end (`docs/M5_WEB_VERIFICATION.md`). No clip of anyone's is crawlable: the report is `noindex` and robots keeps `/video` out.
* **M6 Football Simulation (first slice)** — `possession-block-v1@1.0.0` plays a 90-minute match as fifteen six-minute blocks from ten measured factors and nine named rates per side, each rate printing its own expression. The digest is `sha256` over the inputs, stored in `sim_matches` beside the report **and** the four inputs that produced it, so `POST /api/v1/simulate/{ident}/replay` can re-play from the row and the page prints `stored · replayed · Identical.` instead of asking to be trusted; another account gets 404 on every door, and `/simulate` sits behind the session wall. The same increment closed spec §65's last outstanding item — world 3.2 generates 100 training sessions for its generated players, each one citing a catalogue drill and deriving load as duration × RPE, browsable at `/world/training` and counted as `MEETS` by `/world`'s own table (`docs/M6_VERIFICATION.md`, `docs/M6_WEB_VERIFICATION.md`). What it is *not*: an observation of a real match — `data_origin='simulation'` and the simulation disclaimer ride on every row and page. Career Mode's backend (§20) landed with it — `careers` + `career_fixtures`, a rotation anyone can reproduce, rounds decided by the same engine, a record and objectives summed from stored rows, 6 routes and 28 tests on both engines — and `/career` plus `/career/{slug}` now put it on screen: the season page's record, objective verdicts, fixture list and table of clubs met are all read back from the API's sums, and the walk asserts that each round's printed points is the arithmetic of the row it came from (`docs/M6_CAREER_WEB_VERIFICATION.md`).
* **M6 Manager Live Challenges (§21, backend + page)** — six authored scenarios, each **time limited** by a window the engine enforces (`career.play_round` answers `409 window_closed` with the final verdict beside it), **goal based** on objectives the caller cannot lower, and **reward based** on a verdict recomputed from the run's own rows — every objective reached with rounds still to play earns nothing, because the window has not closed. A run *is* a career, so one match model and one fixture store still decide every round. The weakest club a scenario hands you is measured, not asserted: all five clubs in the named competition are built with the engine's own squad reader and the lowest is taken, with the whole ranking published. Every constraint ships `enforced: true|false` and the sentence saying what it does — "no transfers" is enforced since §22 landed, the market refusing every deal for a career carrying it, while "academy players only" is published, not applied, because the eleven has no age filter (`docs/M6_VERIFICATION.md` §11). `/challenges` and `/challenges/runs/{slug}` are the same thing on screen, and the walk holds each of the three adjectives to a check rather than a sentence: the start form has four fields and none of them is a knob (`negotiable fields 0`), the club a `weakest` scenario hands back is the arithmetic minimum of the ranking the same response printed (`Braeford Athletic at 0.4891 of 5 measured · gap to runner-up: 0.0018`), the verdict equals the fixture table added up in the browser (`Pts column sums to 4 and Points reads 4`), and the round past the window is refused by the route with `409 window_closed` and the final verdict beside it — 17 checks (`docs/M6_CHALLENGES_WEB_VERIFICATION.md`). The transfer market (§22) followed, turning `no_transfers` into an enforced constraint and the budget into one the wage bill actually spends.

Every one of those was verified the same way, on a fresh **production build**: **377 API tests** green on SQLite **and** on PostgreSQL+pgvector, **226/226 browser assertions** with 70 screenshots at 1440px and 375px, 1037 sitemap URLs each answering 200, `ruff` + `mypy` clean, and a console gate that fails the walk unless every browser error was one the walk provoked on purpose. SEO surface: `docs/SEO_VERIFICATION.md`; gate table: `ROADMAP.md`; environment audit: `docs/PROJECT_AUDIT.md`.

Open as follow-ups rather than gate gaps: a 3D pitch, boards beyond single ownership (M9's consent story), a frame overlay for the measured centroids, event semantics for video (a claim this build cannot support without a real detector), and §81's three locales.

## Architecture at a glance

```
apps/web   Next.js 15 + TypeScript   UI · BFF · auth UX · public knowledge, Football World and Tactical Lab pages (drag boards, SVG pitch) · private video analysis (/video) · SEO metadata (canonical/OG/JSON-LD) · sitemap + robots · dark design system
apps/api   FastAPI + SQLAlchemy 2     auth · football world model · training catalogue · coach engine
                                          progression(XP→skill→attribute, explainable) · providers · jobs
                                          knowledge base: data/knowledge → chunks → embeddings → hybrid retrieval → citations
                                          football world: seeded generator → idempotent sync → unified search → /api/v1/world/*
                                          tactical lab: pitch geometry → 10 shapes × 5 temperaments → 50 measured systems
                                          video analysis: ffprobe facts → ffmpeg frame samples → pixel-statistic vision provider → detections + job/ledger rows
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

## The measured clip loop (M5)

1. Upload a clip to your own account — the container is decided by its magic bytes, not its filename → 2. Ask for the
   analysis: `ffprobe` reads the container, `ffmpeg` samples frames at an even interval → 3. The `demo-pixel-stats`
   provider measures the pitch-green fraction and where the centre of the non-pitch pixels moved, and calls that a
   movement event when it shifts past its stated threshold → 4. The report page shows the provider's name, its model,
   every threshold and a sentence saying it detects no players, no ball and no football events → 5. Play the clip back
   through the owner-only route, which answers byte ranges, and reload to see the same numbers again → 6. Delete it and
   the row, the detections and the bytes on disk are gone.

## Honesty guarantees

- Synthetic world data is badged `DEMO DATA`; unavailable metrics show `Data unavailable`.
- AI output without real provider keys runs in self-labelled `DEMO MODE`.
- Simulations are badged fictional. Progression is rule-based and explainable, never random.
- Every video detection names the provider that produced it, and that provider publishes what it cannot see. Nobody's
  clip is crawlable: reports are `noindex` and robots keeps `/video` out of the crawl.
- No copyrighted assets, no scraped paywalled data, no fabricated citations.
- The interface answers in English, Simplified Chinese and Traditional Chinese: `GET /capabilities` names the
  catalogues the app will actually serve, `middleware.ts` picks one per request, and every page body reads its
  copy from `apps/web/messages/*.json` — `apps/api/tests/test_locale_claims.py` holds the published list to the
  files, and `apps/web/scripts/qa-i18n-literals.mjs` holds the pages to the catalogues.

## Documentation

`ARCHITECTURE.md` · `ROADMAP.md` · `docs/PROJECT_AUDIT.md` · `docs/adr/ADR-001…006` · `SECURITY.md` · `DATA_POLICY.md` · `AI_POLICY.md` · `CONTRIBUTING.md`

## License / disclaimer

Football names, players, teams and events shown in the demo world are fictional and generated. AI analysis is an estimate and not professional medical, scouting or performance certification.
