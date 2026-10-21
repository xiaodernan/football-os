# ARCHITECTURE — FOOTBALL OS

> The Operating System for Football — WATCH. UNDERSTAND. TRAIN. PLAY. MANAGE. BECOME.

## 1. System shape (MVP)

```
                    ┌──────────────────────────────┐
   browser / mobile │  apps/web  Next.js 15 (TS)   │  SSR + BFF + SEO metadata (§81 i18n: shell + catalogues)
                    │  design tokens · PWA-ready   │
                    └───────────────┬──────────────┘
                                    │ HTTP/JSON (typed: lib/api.ts client · lib/server.ts server)
                    ┌───────────────▼──────────────┐
                    │   apps/api  FastAPI (Py3.11) │  auth · domain · coach engine
                    │                              │  providers · agent runtime (M2+)
                    └───────┬──────────────┬───────┘
                            │              │
                 ┌──────────▼───┐   ┌──────▼───────────────┐
                 │ SQLAlchemy 2 │   │ Provider abstraction  │
                 │ + Alembic    │   │ LLM / Embedding /     │
                 │              │   │ Vision / Data / News /│
                 │ Postgres     │   │ Storage               │
                 │  + pgvector  │   └───────────────────────┘
                 │ (dev: SQLite)│
                 └──────────────┘
```

Deliberately absent in MVP (added only when a measured bottleneck demands it): Redis, Celery/RQ, Kafka, Elasticsearch, Java Spring Boot, Kubernetes, dedicated ML services. See ADR-001.

## 2. Layering inside `apps/api`

```
app/
  main.py            app factory, CORS, error schema, OpenAPI metadata, route mounting
  core/
    config.py        env-driven settings; DEMO MODE resolution
    security.py      scrypt password hashing, JWT issue/verify, RBAC dependency
    db.py            engine, Session factory, fallback resolution
    errors.py        RFC7807-ish error envelope + handlers
  models/            SQLAlchemy entities = Football World data model (§4 of spec)
  schemas/           Pydantic DTOs (request/response, versioned via /api/v1)
  api/v1/            routers: auth, users, players, trainings, coach, progress, world
  services/
    player_service   archetype derivation, overall/form computation
    progression      explainable XP → skill → attribute → archetype transitions
    coach_engine     deterministic, evidence-based training recommendation
    training_catalog seed catalogue with full spec §10 fields
    job_service      Job table state machine: QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED/RETRYING
    rag/*            (M2) ingestion → chunk → embed → hybrid retrieval → rerank → citation
  providers/
    base.py          LLMProvider, EmbeddingProvider, VisionProvider, FootballDataProvider, NewsProvider, StorageProvider
    mock_llm.py      DEMO MODE — self-labelled, never impersonates a real model
    openai_llm.py    activated by env keys only
    data_synthetic.py  synthetic football world provider (licensed-safe)
```

## 3. Football World data model (core, M0–M4)

`User 1—N UserPlayer` · `UserPlayer 1—N AttributeSet/TrainingSession/MatchPerformance/XpEvent/Achievement`
`RealPlayer N—1 Team N—1 Competition` · `Match N—1 Team`, `Match 1—N MatchEvent`, `Match 1—N PlayerStat`
`NewsArticle N—M RealPlayer/Team/Competition/Match` through `NewsArticleLink`
`TrainingSession` references a `Drill` (catalogue) + ` CoachingPoint` set + evidence links
`Job` and `AgentRun`/`AgentStep` (M2+) record provider, model, token counts, latency, cost, success/error.

RealPlayer vs UserPlayer are **separate tables**, never a flag on one table (spec §7).

M3 builds the world locally rather than reading a provider: `WORLD_SEED` → `plan_world()` (pure, in-memory)
→ `sync_world()` (upsert by natural key, schema validation before insert) → tables, with
`search_world()` reading them for one typed, ranked result set (spec §56). Two rules hold it honest:

- every row carries `data_origin='synthetic'` + `is_demo_data` + `WORLD_DISCLAIMER`, added by the sync layer
  rather than by the caller, so a page cannot be rendered without the label (spec §62, §88);
- an article may only quote a number that exists in `real_matches` / `real_player_match_stats`, and an
  unplayed fixture keeps NULL goals all the way to the API response ("Data unavailable"), so the news
  desk, the fixtures list and the league table cannot contradict each other.

A news provider is still the plan for real headlines (spec §45); until a key exists, `source_name` is
`synthetic-world` and the desk is a role, not a person.

M6 plays fictional matches: `run_simulation` decides one with `possession-block-v1`, `sim_matches` stores
its inputs and its digest (`POST /simulate/{ident}/replay` re-derives and compares, so a page prints
`Identical.` rather than asking to be believed), `careers` + `career_fixtures` give it a season to be
played in, and rows are `data_origin='simulation'` / `is_demo_data=true` with the §19 disclaimer on the
payload rather than in a page's strings.

Manager live challenges (spec §21) add **two columns, not two tables**: `careers.challenge_slug` and
`careers.challenge_window`. A run *is* a career — same rounds, same engine, same fixture store — which is
why its window can be enforced in exactly one place (`career.play_round`, the only path that plays a
round). The scenario's goal, reward and verdict are **never stored**: they are recomputed from the run's
own `career_fixtures` on every read, so a challenge cannot be edited into having been won. The six
scenarios are an authored catalogue in `app/services/simulation/challenges.py`, and each constraint
publishes `enforced: true|false` with the sentence naming what it does — §21's own examples ("no
transfers", "academy players only") are rules the build has no mechanism to apply, and saying so is
better than letting a scenario read as a constraint that was tested.

M4 adds `tactical_systems` — 50 project-authored coaching structures, one row per shape × temperament.
The same shape discipline applies, with two differences worth stating: these rows are
`data_origin='project-authored'`, `is_demo_data=False` (they are a design artefact of this repository,
not a simulation of the world), and only the identity/filter columns are typed — the measured artefact
(both phases' coordinates, the eight metrics with their formulas, the graded verdicts, the roles in the
field) is stored in `board` so the API serves what was computed. The API then **recomputes** metrics and
counterfactuals from those coordinates on every request rather than reading a stored conclusion, so a
page's numbers always match the dots on the same page (`docs/M4_VERIFICATION.md`).

## 4. Progression is explainable, never random

`TrainingSession completed → XpEvent(row, reason, formula) → skill points → attribute delta (bounded, per-cycle caps) → archetype match score → playstyle label`
Every stored attribute delta keeps its `reason` and `evidence_ids` so the UI can show *why* a number moved (spec §8). No AI call may mutate an attribute directly.

## 5. Auth, entitlements, security

- Credentials: email + password (scrypt, per-user salt), JWT access token in `Authorization` header + httpOnly refresh cookie; same-site strict cookies; per-IP and per-route rate limiting; Pydantic validation on every input; upload MIME/size allow-list (M5).
- RBAC roles: `fan, player, coach, manager, scout, academy, admin` + `organization_id` scoping reserved for B2B (spec §41).
- Entitlement matrix (`feature → plan → limit → usage`) exists from M0 as data, not as a payment integration (spec §42).
- Minors: youth records default to private, location/contact/face-visible media never public without explicit consent (spec §40, §61).

## 6. Frontend architecture

- App Router. The planned route groups (`(public)`, `(app)`, `(auth)`) are **not** used: protection is enforced twice instead —
  `middleware.ts` gates the `PROTECTED_PREFIXES` list, and each protected page calls `currentUser()`. Everything outside that
  list (`/world`, `/knowledge`, the five §80 entity routes, `/login`, `/register`, `/healthz`) renders for a signed-out visitor.
- All data fetching is typed: `lib/api.ts` is the client-safe half (`browserFetch` through the `/api/v1/*` cookie proxy),
  `lib/server.ts` the server-only half (`serverFetch` reading the httpOnly jar), `lib/types.ts` the single wire contract for
  both, `lib/world.ts` the world-page read helpers. Server components by default; client components only where interaction is required.
- Football World pages never construct a URL. The API hands out `path` for every row (`SEO_ROUTES`/`web_path()` in
  `app/services/world/plan.py`), so a §80 route exists in exactly one place across both tiers, and `sitemap.ts` builds its
  983 entries from the same fields the pages link with.
- i18n (spec §81): **built and finished** (2026-10-21) — `middleware.ts` resolves `fo_locale`/`Accept-Language`/the
  account column, `i18n/request.ts` loads the matching catalogue, the nav switcher writes the cookie, both Chinese
  catalogues carry every key the English file holds, and **every page body now reads its catalogue**: the copy gate
  (`apps/web/scripts/qa-i18n-literals.mjs`) reads **0 English literal sites** over every `app/**/*.tsx` **and every
  `components/**/*.tsx`**, on three floors — the three shapes the arc knew (JSX text, a label-ish attribute, a label-ish
  object property), the **fifth** shape it found on 2026-10-21 (a string literal that reaches the reader from
  somewhere else: a helper's sentence, a template, a lone word between two tags), and the keys a page names in its own
  data — and it holds every key against **the namespace it was asked of**, and every placeholder against the values
  supplied with it. Two more gates came out of the same arc: `qa-field-labels.mjs` (no two panels on one page may give a
  field the same accessible name) and `qa-proxy-gate.mjs` (a browser may only reach the API through the cookie proxy,
  because the access token is httpOnly). The key counts live in `apps/web/messages/README.md`, which the suite
  recomputes, and the arc's own record is `docs/I18N_ARC_VERIFICATION.md`.
- **The "0" above was green for the wrong reason, and a browser found it (2026-10-21).** The gate decided a string was
  "already translated" by asking whether it held *any* character outside ASCII — and a middle dot, an em dash and a
  curly apostrophe are all outside ASCII. Every English sentence carrying one of those marks was therefore read as
  Chinese and never counted. The rule now asks whether the string holds a **letter** from another script, and the gate
  immediately reported **47 English strings over 15 files** that the arc had left behind (the settings page's ten
  milestone labels, the pitch's axis labels and captions, the scout workbench's eyebrows, the erase row's sentence, the
  page-title template). All of them are in the catalogue now and both floors are 0 again — with a gate that can see them.
  A **formula** (an arithmetic expression whose words are variable names) is exempt structurally, because translating it
  would make the page wrong and copying it into the catalogue would give one rule two sources to drift apart. The
  lesson generalises: **a floor is a statement about the gate before it is a statement about the tree.**
- **And the gate itself had a blind spot, found by asking it a different question (2026-10-22).** The copy gate recognised a
  translator by the **name** of its variable — `/^t[a-z]{0,2}$/` — which is a naming convention rather than a fact. Three
  translators in this tree are named outside it (`tAuth` in the nav, `tCommon` on the demo badge, `settingsT` on the register
  form), and the **seven** literal key reads through them were therefore never checked for existence, never checked for the
  placeholders their messages need, and never checked for a word said twice. Every one of those keys is in the catalogue, so
  nothing was broken — but the gate was green for the wrong reason, which is the same failure as the rule above. The gate now
  identifies a translator by its **binding**, resolved in the scope that holds it: `const t = useTranslations("nav")` says what
  `t` reads, a function body is a scope (`components/ClubTools.tsx` binds `t` to `club` in one function and to `common` in the
  next), a translator **destructured** out of a promise is bound **positionally** (`const [t, td, tc] = await Promise.all([...])`,
  which `app/layout.tsx` and `app/page.tsx` both do), and a translator **handed to a component as a parameter** is resolved from
  its **call site** (`shelfEyebrow(shelf, tp)` hands the `creator` translator to a parameter called `t`, and reading the file's
  other `t` would have answered `common`). The gate now checks **3600** key calls against the namespaces they are asked of, up
  from 3593, and its red path was watched: a file reading two keys the catalogue does not hold through `tAuth` and `tCommon`
  made the **old** gate report 8/8 PASS and the new one report the two keys with their namespaces.
- **And the catalogue held 226 keys no page asks for (2026-10-22).** The copy gate asks whether every key the source asks
  for **is** in the catalogue; the other half of that question — whether every key the catalogue holds is **asked for** —
  had never been asked, so a catalogue could hold 3736 keys while the tree read 3510 and every gate in the suite would
  still have said the catalogue was complete. `apps/web/scripts/qa-unused-keys.mjs` is that check: it resolves every read in
  the web tier and reports the keys no read can reach. **226** of them, in three classes — two answers to one question
  (`nav.video` and `nav.videoShort` both name the nav's video entry; the nav prints the second, and the page's own title
  lives in `video.metaTitle`), a vocabulary for pages the spec names and the tree has not built (`auth.forgotPassword`,
  `validation.*`), and a table of seventy prepositions (`common.or`, `common.and`, `common.of` …) that was written so a
  sentence could be assembled from parts and never assembled. The gate's only hard job is to be **right about what it calls
  dead**: a read that cannot be resolved to a literal **exempts its whole namespace**, so a key that cannot be shown to be
  dead is never reported as dead. Every read in the tree resolved — named, destructured-positionally, dynamic, named-key,
  callback-parameter, and handed across files — so **no namespace was left unjudged**. **63** of the 226 held the
  **same English sentence as a key that is read** (`nav.video` and `nav.videoShort`, `nav.login` and `auth.signIn`,
  `common.pitchCaption3d` and `tactics.pitchCaption3d`, six `scout.kv*` rows and their shorter twins) — two answers to
  one question, one of them a stale copy no page reads. Those are gone from all three catalogues, and **67** more —
  a shared vocabulary for copy the interface never wrote (the verbs and prepositions `common.or`, `common.and`,
  `common.of`, `common.retry` …, written so a sentence could be assembled from parts, and never assembled, because
  every message here is a whole sentence) — went with them, and so did the last **96**: the club tier's rules
  (**36** of them holding nothing but a placeholder name, `club.matrixRule` is `"{rule}"`, so they were not
  translations at all), the sign-up and password-reset flows, the validation messages, and the nav entries for
  pages the nav does not offer. **26** of those 96 were never translated and were sitting in the Chinese
  catalogues as English. The floor is **0** and the catalogue holds **3510** keys (was 3736).
- SEO (spec §80): `lib/site.ts` turns `SITE_URL` into absolute canonical/OpenGraph URLs; `app/sitemap.ts` and `app/robots.ts` are
  generated from live API reads, so only routes that answer 200 for a signed-out visitor are advertised. Per-route metadata sets
  its own canonical — never the root layout, which every child would inherit.
- Design system: `styles/globals.css` (tokens + the shared class vocabulary listed at the top of the file) plus per-surface
  stylesheets (`world.css`, `coach.css`, `training.css`, …) and `components/ui/*`; dark, premium, editorial, data-rich (spec §48).
- Trust surfaces: every AI/simulation/demo output carries a visible badge — `DEMO DATA`, `AI-generated`, `Estimated`, `Simulation`, `Source`, `Confidence` (spec §62).

## 7. Data & AI sourcing

Legal-data-first (spec §5): synthetic generated world + user content + properly licensed/open news APIs behind `FootballDataProvider`/`NewsProvider`. A provider outage surfaces as `Provider unavailable` / `Data unavailable` — never invented values (spec §78).

## 8. Observability & cost

Structured JSON logs, request IDs, `/healthz` + `/readyz`. `model_calls` ledger stores provider, model, in/out/reasoning tokens, latency, estimated + actual cost, success/error (spec §46, §59, §76).

## 9. Testing strategy

pytest unit (progression, coach engine, auth) + FastAPI TestClient integration over the API; `npm run typecheck && npm run build` for the web app; Playwright E2E for the M1 loop at milestone close; agent/RAG evaluation harness lands in M2 (spec §63–64).
