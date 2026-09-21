# ARCHITECTURE — FOOTBALL OS

> The Operating System for Football — WATCH. UNDERSTAND. TRAIN. PLAY. MANAGE. BECOME.

## 1. System shape (MVP)

```
                    ┌──────────────────────────────┐
   browser / mobile │  apps/web  Next.js 15 (TS)   │  SSR + BFF + streaming + i18n
                    │  design tokens · PWA-ready   │
                    └───────────────┬──────────────┘
                                    │ HTTP/JSON (typed client in lib/api.ts)
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

## 3. Football World data model (core, M0–M3)

`User 1—N UserPlayer` · `UserPlayer 1—N AttributeSet/TrainingSession/MatchPerformance/XpEvent/Achievement`
`RealPlayer N—1 Team N—1 Competition` · `Match N—1 Team`, `Match 1—N MatchEvent`, `Match 1—N PlayerStat`
`NewsArticle N—1 source provider`, links to `RealPlayer`/`Team` entities
`TrainingSession` references a `Drill` (catalogue) + ` CoachingPoint` set + evidence links
`Job` and `AgentRun`/`AgentStep` (M2+) record provider, model, token counts, latency, cost, success/error.

RealPlayer vs UserPlayer are **separate tables**, never a flag on one table (spec §7).

## 4. Progression is explainable, never random

`TrainingSession completed → XpEvent(row, reason, formula) → skill points → attribute delta (bounded, per-cycle caps) → archetype match score → playstyle label`
Every stored attribute delta keeps its `reason` and `evidence_ids` so the UI can show *why* a number moved (spec §8). No AI call may mutate an attribute directly.

## 5. Auth, entitlements, security

- Credentials: email + password (scrypt, per-user salt), JWT access token in `Authorization` header + httpOnly refresh cookie; same-site strict cookies; per-IP and per-route rate limiting; Pydantic validation on every input; upload MIME/size allow-list (M5).
- RBAC roles: `fan, player, coach, manager, scout, academy, admin` + `organization_id` scoping reserved for B2B (spec §41).
- Entitlement matrix (`feature → plan → limit → usage`) exists from M0 as data, not as a payment integration (spec §42).
- Minors: youth records default to private, location/contact/face-visible media never public without explicit consent (spec §40, §61).

## 6. Frontend architecture

- App Router with route groups: `(public)` football world/news/SEO pages, `(app)` My Football/Coach/Training/Tactical Lab, `(auth)`.
- All data fetching through `lib/api.ts` (typed) — server components by default, client components only where interaction is required.
- i18n from the first screen: `messages/{en,zh,zh-TW}.json`, no literal strings inside components (spec §81).
- Design system: `styles/tokens.css` (colour/type/spacing/radius/shadow) + `components/ui/*`; dark, premium, editorial, data-rich (spec §48).
- Trust surfaces: every AI/simulation/demo output carries a visible badge — `DEMO DATA`, `AI-generated`, `Estimated`, `Simulation`, `Source`, `Confidence` (spec §62).

## 7. Data & AI sourcing

Legal-data-first (spec §5): synthetic generated world + user content + properly licensed/open news APIs behind `FootballDataProvider`/`NewsProvider`. A provider outage surfaces as `Provider unavailable` / `Data unavailable` — never invented values (spec §78).

## 8. Observability & cost

Structured JSON logs, request IDs, `/healthz` + `/readyz`. `model_calls` ledger stores provider, model, in/out/reasoning tokens, latency, estimated + actual cost, success/error (spec §46, §59, §76).

## 9. Testing strategy

pytest unit (progression, coach engine, auth) + FastAPI TestClient integration over the API; `npm run typecheck && npm run build` for the web app; Playwright E2E for the M1 loop at milestone close; agent/RAG evaluation harness lands in M2 (spec §63–64).
