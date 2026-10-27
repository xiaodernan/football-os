# Runbook — full logical restore

**When:** the primary database is unavailable, or a restore must be rehearsed before it is needed.
**Scripts:** [`scripts/backup_db.sh`](../../scripts/backup_db.sh), [`scripts/restore_db.sh`](../../scripts/restore_db.sh),
[`scripts/dr_lib.sh`](../../scripts/dr_lib.sh). **Gated by:** `apps/api/tests/test_dr_scripts.py`.

## 0. Know where the scripts will connect

Both scripts source `dr_lib.sh`, which reads the single PostgreSQL mapping out of `infra/docker-compose.yml`
(host port, `POSTGRES_DB`, `POSTGRES_USER`). An exported `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER` wins. If the
compose file carries zero or two matching lines the script **refuses with the count it read** rather than
falling back to a default.

```bash
# what the scripts will use
grep -E 'POSTGRES_(DB|USER)|[0-9]+:5432' infra/docker-compose.yml
```

`pg_dump`, `pg_restore` and `psql` must be on `PATH`. This project's container ships them:
`docker exec football_os_db pg_dump --version`.

## 1. Take a backup

```bash
./scripts/backup_db.sh full
```

- Writes `$BACKUP_DIR/football_os_<UTC timestamp>.dump` (`BACKUP_DIR` defaults to `/var/backups/football_os`).
- Format: `pg_dump --format=custom --compress=3 --no-owner --no-privileges`.
- Verifies with `pg_restore --list`; a failed verification exits non-zero.
- Uploads to `s3://$BACKUP_S3_BUCKET/` only when that variable is set (the one off-host hop).
- Deletes local dumps older than 7 days, and prints how many it actually removed.

## 2. Restore into a scratch database

`restore_db.sh` **refuses any target that is not a scratch name** (`scripts/qa_db.py --assert-scratch`). That is
the point: a mistyped live database name is refused, not dropped.

```bash
./scripts/restore_db.sh /var/backups/football_os/football_os_<timestamp>.dump football_os_scratch_restore
```

It will, in order: verify the dump, re-create the target through `qa_db.py` (which installs `vector`), run
`pg_restore --jobs=4 --clean --if-exists`, replay `alembic upgrade head` from `apps/api` (where `alembic.ini` is),
and print the restored public-table count. A non-zero `pg_restore` exits with the message that the target is a
partial copy — the migration replay is skipped.

## 3. Verify

```bash
# the run prints this figure; read it rather than assume it
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d football_os_scratch_restore \
  -tA -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"

# schema and data agree with the code
cd apps/api
DATABASE_URL="postgresql+psycopg2://${PGUSER}@${PGHOST}:${PGPORT}/football_os_scratch_restore" \
  python -m alembic check
DATABASE_URL="postgresql+psycopg2://${PGUSER}@${PGHOST}:${PGPORT}/football_os_scratch_restore" \
  "C:/Program Files/Python311/python.exe" -m pytest tests/test_simulation_aggregates_rules.py -q
```

## 4. Cut over (only after step 3 is clean)

1. Put the API into maintenance mode / stop traffic.
2. Point `DATABASE_URL` at the restored database.
3. Restart the API and check `/healthz`.
4. Run the smoke subset above against the restored database.
5. Resume traffic.

## What this runbook does not claim

- It does not restore into a live database. The scratch-name policy is deliberate; cut-over is a separate,
  reviewed step.
- It does not restore video assets stored outside PostgreSQL (S3 originals are a separate bucket).
- It does not verify application-level invariants beyond `alembic check` and the smoke subset.
- The drill recorded in `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md` ran the commands inside the container;
  this runbook follows the scripts as they now stand.
