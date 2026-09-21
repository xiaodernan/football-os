# ADR-006 — Async jobs as a database state machine (no broker yet)

- Status: Accepted · Relates to: §47, §75, PRINCIPLE 1
- **Context**: Video analysis, training-plan generation, large RAG runs, simulations and agent research are long tasks. Kafka/Celery+Redis would be premature for a single-node MVP.
- **Problem**: Long work must not block request threads and must be observable/cancellable, without new infrastructure.
- **Options**: (a) `BackgroundTasks` only; (b) Postgres-backed `Job` table + in-process worker pool with claim-by-`UPDATE ... RETURNING`; (c) Celery/Redis now.
- **Decision**: (b). Job states `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED | RETRYING` with `attempt/max_attempts/lease_expires_at`, progress 0–100, structured error and result payload. The polling worker is one process today; the same repository interface can be driven by Redis/Celery later without touching call sites.
- **Consequences**: No cross-node scaling until the broker swap; job leases must be renewed to avoid duplicate execution after a crash; tests assert state transitions rather than sleeps.
