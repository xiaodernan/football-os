# Runbook — region failover

**When:** the primary region (database and/or API) is unavailable for longer than the RTO in
[`BACKUP_RECOVERY.md`](../BACKUP_RECOVERY.md).

**Reality check first:** this repository's `infra/docker-compose.yml` starts a **single** PostgreSQL container and
no replica. `scripts/backup_db.sh` only checks replication when `REPLICA_HOST` is exported. If no replica exists in
the DR region, there is nothing to promote and the path is a restore, not a failover.

## A. If a replica exists in the DR region

1. Confirm the replica is caught up before promoting:
   ```bash
   REPLICA_HOST=<dr-host> ./scripts/backup_db.sh incremental
   # prints "Replication lag: <n>s against a <ceiling>s ceiling"; a lag over the ceiling exits non-zero
   ```
2. Promote the replica (the tool that created it — `pgBackRest`, `WAL-G` or the managed service — owns this step).
3. Point the API's `DATABASE_URL` at the promoted instance and restart it.
4. Verify `/healthz`, then the smoke subset in [`full_restore.md`](full_restore.md) step 3.
5. Move DNS / the load balancer, with a short TTL, and announce the change.

## B. If no replica exists (the state of this repository)

1. Provision PostgreSQL in the DR region (same major version; the compose file's image is the reference).
2. Restore the newest off-host dump:
   ```bash
   # on a host that can reach the DR database, with PG* pointing at it
   ./scripts/restore_db.sh /path/to/football_os_<timestamp>.dump football_os_scratch_restore
   ```
   `restore_db.sh` still refuses a non-scratch name; the production cut-over is the reviewed step that points the
   API at the verified restore.
3. Verify as in [`full_restore.md`](full_restore.md) step 3.
4. Point `DATABASE_URL` at the restored instance, restart the API, check `/healthz`.
5. Move DNS and announce.

## What this runbook does not claim

- It does not create a replica. A failover runbook is only as real as the replica behind it.
- It does not promise the 30–60 minute figure in `BACKUP_RECOVERY.md`; that figure assumes a warm replica, which
  this repository does not start.
- It does not cover object storage. Video originals are a separate bucket and a separate provider decision.
