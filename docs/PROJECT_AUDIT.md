# PROJECT_AUDIT — FOOTBALL OS

Audit date: 2026-09-22 · Auditor: autonomous development agent · Repo state: greenfield (spec document only)

## 1. Repository scan

| Item | Finding |
| --- | --- |
| Path | `D:\足球项目` |
| Existing code | **None.** Only `新建 文本文档.txt` (the 3381-line FOOTBALL OS master specification) |
| Git | Not initialised before this audit → `git init` executed |
| Package manifests | None (no `package.json`, no `pyproject.toml`) |
| Migrations / CI / Docker | Absent |

**Conclusion:** the project starts at M0 with zero legacy constraints. Everything below is net-new.

## 2. Host environment (measured, not assumed)

| Capability | Version / value | Status |
| --- | --- | --- |
| OS | Windows 10.0.26200, x64 | OK |
| CPU | 16 logical cores | OK |
| RAM | ~16 GB (16,979,456,000 B) | OK |
| Node.js | v24.15.0 | OK |
| npm | 11.12.1 | OK |
| Python | 3.11.1 | OK |
| pip | 25.3 | OK |
| Git | 2.52.0.windows.1 | OK |
| Docker | 29.1.3 | OK — target for PostgreSQL + pgvector |
| Java | OpenJDK 25.0.1 (Temurin) | Present but **not used in MVP** per PRINCIPLE 1 |
| `psql` client | **Not installed** | Degraded → see §4 |
| GPU | Not detected | No local model inference; vision stays behind provider abstraction |

## 3. Specification coverage map

The master spec defines 30 product modules and milestones M0–M12. This audit pins what each milestone needs from the platform so nothing is "invented later".

Already-satisfied requirements: none (empty repo).

Blocking unknowns (all resolvable without user input, resolved in ADRs):

1. **Data source licensing** — no football data contract exists → ADR-004: synthetic demo world + provider abstraction, every surface labelled `DEMO DATA`.
2. **AI credentials** — no API keys configured → ADR-005: `MockLLMProvider` runs in explicit `DEMO MODE`; UI must never present mock output as real AI.
3. **PostgreSQL availability** — no local server → ADR-002: SQLAlchemy + Alembic with a SQLite dev fallback that preserves the Postgres/pgvector upgrade path.

## 4. Risk register

| Risk | Impact | Mitigation applied |
| --- | --- | --- |
| Docker/Postgres unavailable at run time | Backend cannot boot | `DATABASE_URL` falls back to SQLite; Postgres is the documented default via `infra/docker-compose.yml`; feature tests run against the fallback so CI is honest |
| `passlib`/`bcrypt` version conflicts | Auth broken at install | Password hashing uses Python stdlib `hashlib.scrypt` — zero third-party crypto deps |
| Fake-data temptation (PRINCIPLE 2) | Product becomes a mock UI | Every write path goes through the API to a real database; demo entities carry `is_demo_data` and a UI badge; unavailable metrics render `Data unavailable`, never a number |
| Scope explosion (30 modules) | Nothing ships | Milestone gate: M0 + M1 vertical slice must run end-to-end before any M2 work |
| npm registry unreachable | Frontend cannot build | Fallback documented in §6; build verified before claiming completion |

## 5. Decisions taken in this audit

- Monorepo: `apps/web` (Next.js), `apps/api` (FastAPI), `infra/` (compose), `docs/` (this audit, ADRs, policies).
- No Redis, no workers, no Kafka, no Java, no Kubernetes (PRINCIPLE 1). Async jobs are represented by a `Job` table polled by the API — upgrade path to a real queue is a single service swap (ADR-006).
- Design system is token-driven CSS (`styles/tokens.css` + component classes), not per-page CSS (spec §73).

## 6. Verification protocol used from here on

`install → lint/typecheck → unit+API tests → boot both servers → Playwright-free browser Visual QA with screenshots → fix → commit`. A milestone is not "done" until §6 has been executed and recorded in `docs/M<n>_VERIFICATION.md`.
