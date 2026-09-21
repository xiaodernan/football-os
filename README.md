# FOOTBALL OS

> **The Operating System for Football** — WATCH. UNDERSTAND. TRAIN. PLAY. MANAGE. BECOME.

One platform connecting the real football world, personal football development, football simulation and football AI. Not a news site, not a score app, not an FM clone, not a chatbot wrapper.

**Status:** M0 Foundation + M1 vertical slice (My Football → Player → Training → AI Coach → Progress → History) implemented and verified. See `ROADMAP.md` for gate status, `docs/PROJECT_AUDIT.md` for the environment audit.

## Architecture at a glance

```
apps/web   Next.js 15 + TypeScript   UI · BFF · auth UX · i18n(en/zh/zh-TW) · dark design system
apps/api   FastAPI + SQLAlchemy 2     auth · football world model · training catalogue · coach engine
                                          progression(XP→skill→attribute, explainable) · providers · jobs
PostgreSQL + pgvector (docker compose)   dev fallback: SQLite via DATABASE_URL
```

No Redis, no Kafka, no microservices, no Java — added only against a measured bottleneck (ADR-001, ADR-006).

## Quick start

```bash
# 1. API
python -m venv .venv && .venv/Scripts/activate
pip install -r apps/api/requirements.txt
cp apps/api/.env.example apps/api/.env
cd apps/api && alembic upgrade head && python -m seed
uvicorn app.main:app --reload --port 8000

# 2. Web (new terminal)
cd apps/web && npm install && npm run dev    # http://localhost:3000

# optional: real Postgres + pgvector
docker compose -f infra/docker-compose.yml up -d
```

Tests: `pytest` (API) · `npm run typecheck && npm run test && npm run build` (web).

## The first real loop (M1)

1. Register → 2. Create your player (position, age, level, foot, goal) → 3. Attributes + archetype derived with visible reasons → 4. Ask the Coach *"What should I train today?"* → 5. Train (objective, setup, coaching points, common mistakes, progression, test) → 6. Complete → 7. XP + attribute delta, each with its reason → 8. Progress and history update → 9. Coach's next message reflects your actual new state.

## Honesty guarantees

- Synthetic world data is badged `DEMO DATA`; unavailable metrics show `Data unavailable`.
- AI output without real provider keys runs in self-labelled `DEMO MODE`.
- Simulations are badged fictional. Progression is rule-based and explainable, never random.
- No copyrighted assets, no scraped paywalled data, no fabricated citations.

## Documentation

`ARCHITECTURE.md` · `ROADMAP.md` · `docs/PROJECT_AUDIT.md` · `docs/adr/ADR-001…006` · `SECURITY.md` · `DATA_POLICY.md` · `AI_POLICY.md` · `CONTRIBUTING.md`

## License / disclaimer

Football names, players, teams and events shown in the demo world are fictional and generated. AI analysis is an estimate and not professional medical, scouting or performance certification.
