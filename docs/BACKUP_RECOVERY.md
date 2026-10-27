# Backup & Disaster Recovery (M12)

## Overview

This document defines backup procedures, recovery procedures, and RTO/RPO targets
for FOOTBALL OS production systems.

## Recovery Objectives

| System | RTO (Recovery Time Objective) | RPO (Recovery Point Objective) |
|--------|-------------------------------|--------------------------------|
| Primary API | 4 hours | 15 minutes |
| PostgreSQL Database | 2 hours | 5 minutes |
| pgvector Index | 6 hours | 1 hour |
| Knowledge Base (RAG) | 8 hours | 24 hours |
| File Storage (Video) | 24 hours | 24 hours |

## Backup Strategy

### PostgreSQL Database

**Continuous Archiving (WAL-G / pgBackRest)**
- Base backup: Daily at 02:00 UTC
- WAL archiving: Continuous (every 16MB or 5 minutes)
- Retention: 30 days base backups, 90 days WAL
- Storage: S3-compatible with versioning and cross-region replication

**Logical Backup (pg_dump)**
- Daily at 03:00 UTC (after base backup)
- Format: Custom format (`-Fc`) for parallel restore
- Includes: Schema + data, no ownership/privileges
- Compression: ZSTD level 3
- Retention: 90 days

### pgvector Index
- Rebuilt from PostgreSQL data on recovery
- No separate backup needed (derivable)

### Knowledge Base (RAG)
- Corpus documents: Included in PostgreSQL backup
- Embeddings: Regenerated from corpus on recovery (deterministic)
- RAG index: Regenerated from embeddings

### File Storage (Video Assets)
- Original files: S3 with versioning and cross-region replication
- Processed frames/detections: Regenerated from originals on recovery
- Retention: 90 days versioning

### Configuration & Secrets
- Environment variables: Stored in GitOps repo (encrypted with SOPS)
- Database credentials: Rotated quarterly, stored in secret manager
- API keys: Rotated quarterly, stored in secret manager

## Backup Verification

| Check | Frequency | Method |
|-------|-----------|--------|
| Base backup integrity | Weekly | `pg_verifybackup` |
| WAL continuity | Daily | `pg_waldump` / pgBackRest check |
| Logical dump restore | Monthly | Restore to staging, run test suite |
| Point-in-time recovery | Quarterly | Restore to target timestamp, verify data |
| Cross-region replication | Daily | Verify replication lag < 5 min |

## Recovery Procedures

### Scenario 1: Point-in-Time Recovery (PITR)

**When**: Data corruption, accidental deletion, bad deployment
**Steps**:
1. Stop application traffic (maintenance mode)
2. Identify target timestamp (before incident)
3. Restore latest base backup before target
4. Apply WAL up to target timestamp
4. Verify data integrity (`alembic check`, sample queries)
5. Update DNS / load balancer to recovered instance
6. Run smoke tests
7. Resume traffic

**Estimated Time**: 60-120 minutes

### Scenario 2: Full Database Restore

**When**: Primary database unavailable, PITR not possible
**Steps**:
1. Provision new PostgreSQL instance (same version)
2. Restore latest base backup
3. Apply all WAL up to latest
4. Run `alembic upgrade head`
5. Run `python -m seed --with-demo-user` (if needed)
6. Verify with test suite subset
6. Update connection strings / DNS

**Estimated Time**: 90-180 minutes

### Scenario 3: Full Region Failover

**When**: Entire region unavailable
**Steps**:
1. Promote read replica in DR region (or restore from cross-region backup)
2. Update DNS to DR region (TTL 60s)
3. Verify API health endpoints
4. Run smoke tests
4. Communicate status to users

**Estimated Time**: 30-60 minutes (DNS propagation)

### Scenario 4: Partial Data Loss (Single Table)

**When**: Accidental `DELETE`/`UPDATE` without `WHERE`
**Steps**:
1. Identify affected rows and timestamp
2. Create temporary table from PITR at t-1min
3. Copy missing rows back to production
3. Verify referential integrity

**Estimated Time**: 15-30 minutes

## Testing Schedule

| Test | Frequency | Owner |
|------|-----------|-------|
| Full PITR drill | Quarterly | Platform team |
| Logical restore to staging | Monthly | Platform team |
| Region failover simulation | Semi-annually | Platform team |
| Backup integrity scan | Weekly (automated) | CI/CD |
| Secrets rotation drill | Quarterly | Security team |

## Monitoring & Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| Backup job failed | Any backup job non-zero exit | Critical |
| WAL archive lag | `pg_wal_lsn_diff` > 100MB | Warning |
| Cross-region replication lag | > 5 minutes | Critical |
| Backup storage usage | > 80% capacity | Warning |
| Restore test failed | Any verification step fails | Critical |

## Runbooks

Step-by-step runbooks in [`docs/runbooks/`](runbooks/), each grounded in the scripts that actually run
(`scripts/backup_db.sh`, `scripts/restore_db.sh`, `scripts/dr_lib.sh`):

- [`full_restore.md`](runbooks/full_restore.md) — logical dump and restore into a scratch database.
- [`pitr_recovery.md`](runbooks/pitr_recovery.md) — PITR, and the honest check that this container has no WAL archive.
- [`partial_restore.md`](runbooks/partial_restore.md) — restore a slice into scratch, copy the missing rows back.
- [`region_failover.md`](runbooks/region_failover.md) — promote a replica if one exists, otherwise restore.
- [`secret_rotation.md`](runbooks/secret_rotation.md) — `APP_SECRET`, provider keys and database credentials.

The scripts are the source of truth: where a runbook and a script disagree, the script is right and the runbook is
the bug.

## Contacts

| Role | Primary | Secondary |
|------|---------|-----------|
| Incident Commander | Platform Lead | Engineering Manager |
| Database Admin | Senior DBA | Platform Engineer |
| Communications | Engineering Manager | CTO |

## Revision History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-10-09 | 1.0 | Initial version | Platform Team |