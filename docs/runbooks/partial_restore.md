# Runbook — partial data loss (one table, or one set of rows)

**When:** a `DELETE`/`UPDATE` without `WHERE`, or a bad migration, damaged a known slice of data while the rest of
the database is healthy.

**Rule:** never restore over the live database to fix a slice. Restore a copy into a scratch database, take the
missing rows from it, and write them back under a transaction you can inspect.

## 1. Rehearse the slice in scratch

```bash
./scripts/restore_db.sh /var/backups/football_os/football_os_<timestamp>.dump football_os_scratch_restore
```

`restore_db.sh` refuses a non-scratch name (`scripts/qa_db.py --assert-scratch`), so the live database cannot be
the target by accident. If the backup you need is older than the newest dump, use the dump whose timestamp is
**before** the damage.

## 2. Find the rows that are missing

Compare counts and keys between the scratch copy and production — not whole rows, so the check stays cheap:

```bash
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d football_os_scratch_restore -tA -c \
  "SELECT count(*) FROM <table> WHERE <window>"
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tA -c \
  "SELECT count(*) FROM <table> WHERE <window>"
```

Then list the keys present in scratch and absent in production (`EXCEPT`), and confirm the list is the size you
expect before copying anything.

## 3. Copy the rows back

1. `BEGIN;`
2. Insert/update only the keys you listed, from the scratch database (a `dblink`/`postgres_fdw` copy or an
   `INSERT … SELECT` after a `pg_dump --table` of that slice).
3. Verify referential integrity and the counts from step 2 **inside** the transaction.
4. `COMMIT;` only if every check passes; otherwise `ROLLBACK;`.

## 4. Verify

- The count from step 2 now agrees.
- `alembic check` still reports no drift.
- The smoke subset in [`full_restore.md`](full_restore.md) step 3 passes.

## What this runbook does not claim

- It does not reconstruct rows that were never in any dump. The oldest row you can recover is the oldest dump
  that still contains it.
- It does not repair foreign keys automatically; the integrity check in step 3 is the gate.
- It does not cover a slice larger than a table or a key range — that is a full restore.
