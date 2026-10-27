# Runbook — point-in-time recovery (PITR)

**When:** data corruption or an accidental `DELETE`/`UPDATE` needs the database as it stood at a timestamp.
**Reality check first:** PITR needs write-ahead-log archiving. This repository's own container has it **off**, and
`scripts/backup_db.sh incremental` says so instead of pretending:

```bash
./scripts/backup_db.sh incremental
# REFUSED: an incremental backup is a write-ahead-log archive, and <host>:<port> answers archive_mode='off'.
#          arm it (archive_mode=on plus an archive_command, or pgBackRest/WAL-G) and re-run, or take a
#          logical dump now: ./scripts/backup_db.sh full
```

If it refuses, **PITR is not available on this deployment**. Use
[`full_restore.md`](full_restore.md) and accept the loss between the last dump and the incident. Do not describe
the gap as a PITR.

## If archiving is armed

`backup_db.sh incremental` also reads `pg_stat_archiver` (last archived WAL, last archived time, failed count) and,
when `REPLICA_HOST` is set, the replay lag against `REPLICA_LAG_CEILING_SECONDS` (default 300). A query that does
not answer is a refusal, not a pass.

1. Stop application traffic (maintenance mode).
2. Choose the target timestamp — strictly before the incident, and after the last base backup.
3. Restore the latest base backup before the target into a **scratch** database (the scratch-name policy in
   [`full_restore.md`](full_restore.md) applies).
4. Apply WAL up to the target timestamp with the tool that produced the archive (`pgBackRest`/`WAL-G`); this
   repository ships no PITR driver of its own, so use the one that armed `archive_command`.
5. Verify: `alembic check`, the restored table count, and the smoke subset in
   [`full_restore.md`](full_restore.md) step 3.
6. Cut over as in [`full_restore.md`](full_restore.md) step 4.

## What this runbook does not claim

- It does not arm archiving. That is a deliberate deployment change, not a step in a recovery.
- It does not choose a recovery tool. `BACKUP_RECOVERY.md` names `pgBackRest`/`WAL-G` as the strategy; whichever
  one is installed is the one whose commands apply.
- The 5-minute RPO in `BACKUP_RECOVERY.md` is a **target**, not a measurement. On this container the measured
  state is "no WAL archive", and the honest RPO is "since the last logical dump".
