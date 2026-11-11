# Runbooks

One page per operational subsystem. Each cites the door or script it documents, and each carries a "what this
runbook does not claim" section — the limit is part of the procedure, not a footnote.

## Backup & disaster recovery

- [`full_restore.md`](runbooks/full_restore.md) — logical dump and restore into a scratch database.
- [`pitr_recovery.md`](runbooks/pitr_recovery.md) — PITR, and the honest check that this container has no WAL archive.
- [`partial_restore.md`](runbooks/partial_restore.md) — restore a slice into scratch, copy the missing rows back.
- [`region_failover.md`](runbooks/region_failover.md) — promote a replica if one exists, otherwise restore.
- [`secret_rotation.md`](runbooks/secret_rotation.md) — `APP_SECRET`, provider keys and database credentials.

The policy these follow is [`BACKUP_RECOVERY.md`](BACKUP_RECOVERY.md); the scripts are the source of truth
(`scripts/backup_db.sh`, `scripts/restore_db.sh`, `scripts/dr_lib.sh`). Where a runbook and a script disagree,
the script is right and the runbook is the bug.

## Erasure

- [`erasure.md`](runbooks/erasure.md) — account deletion (`/api/v1/auth/account`) and a child's data in one
  tenant (`/api/v1/club/academy/{ident}/players/{player}/data`), with the receipt-before-confirm rule.

## Rate limits

- [`rate_limits.md`](runbooks/rate_limits.md) — the distributed token bucket in
  `apps/api/app/core/ratelimit.py` (Lua-on-Redis TIME when REDIS_URL is set and reachable, a process-local
  pre-filter always), the policy table, the operator door `/api/v1/metrics/rate-limit`, the degraded `process`
  scope published on every answer, and M15's takeover of the old fixed-window limiter.

## The async-job queue

- [`jobs.md`](runbooks/jobs.md) — what queues onto `/jobs`, the claim algorithm (`UPDATE … WHERE id = :id
  AND status = 'QUEUED'`, rowcount is the verdict — portable across SQLite and Postgres), the ADR-006 state
  vocabulary, the `scripts/drain_jobs.py` worker, and the empty-board contract (every queued job ends
  `FAILED` with `no handler registered` — never held, never silently dropped).

## The Spring Cloud service plane

- [`service_plane.md`](runbooks/service_plane.md) — build and boot order for registry / config /
  core / edge, the seven doors, W3C trace propagation across Java and Python, the four failures
  this plane has actually had, and how to verify it offline.

## Tracing

- [`tracing.md`](runbooks/tracing.md) — the OTLP backend and the database span store (`request_spans`,
  seven-day retention), the two admin doors (`/api/v1/traces/{id}` and `/api/v1/traces/summary`), and the
  live-store caveat that a page render writes spans of its own.

## Cost alerts

- [`cost_alerts.md`](runbooks/cost_alerts.md) — the monthly ceiling's out-of-band channel: the sweep
  (`POST /api/v1/metrics/alerts/check`), the signed webhook (`OPS_ALERT_WEBHOOK_URL`), the `ops_alerts` ledger and
  its retry ceiling, and the delivery decision behind all three.
