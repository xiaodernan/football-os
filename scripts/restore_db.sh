#!/usr/bin/env bash
# Restore script for FOOTBALL OS PostgreSQL database
# Usage: ./restore_db.sh <backup_file.dump> [target_database]
#
# Read together with `scripts/backup_db.sh` and `scripts/dr_lib.sh`, and gated by
# `apps/api/tests/test_dr_scripts.py`. Four defects were measured here on 2026-10-20, none of which could show
# itself in a run because nothing on this host invokes the script (docs/M12_PRODUCTION_HARDENING_VERIFICATION.md
# records the 2026-10-11 drill as running the commands inside the container, not this file):
#
#   * the final `alembic upgrade head` ran from the repository root, where there is no `alembic.ini` — it failed
#     with "No config file 'alembic.ini' found" before reaching a server, so the migration replay the script
#     promised in its own log never happened;
#   * `if [[ $? -eq 0 ]]` sat under `set -euo pipefail`, which had already aborted the script on a non-zero
#     `pg_restore`, so the "Restore failed" branch was unreachable and the only thing the file could say about a
#     half-restored database was nothing at all;
#   * the default target was `football_os_restore` and the file ran `DROP DATABASE IF EXISTS` on whatever name
#     came in argument two, with no policy in between: `scripts/qa_db.py` already owns a scratch-name rule, and a
#     DR script is the one place a mistyped live database name has to be refused rather than dropped;
#   * the connection defaulted to port 5432 while the container this project owns publishes 54321.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="$ROOT/apps/api"
cd "$ROOT"

# shellcheck source=/dev/null
source "$ROOT/scripts/dr_lib.sh"
# Host, port, user and database come from `infra/docker-compose.yml`; an exported PG* still wins. The typed 5432
# these lines replace is the port nothing in this repository publishes, so a restore run without an environment
# pointed at a server that was not there.
dr_pg_defaults

BACKUP_FILE="${1:-}"
# A scratch name by default, and `--assert-scratch` below decides for every name: the policy lives in qa_db.py, the
# script that does the dropping, so this file cannot drift from it.
TARGET_DB="${2:-football_os_scratch_restore}"

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] $*"
}

usage() {
    echo "Usage: $0 <backup_file.dump> [target_database]" >&2
}

check_pg() {
    if ! command -v pg_restore >/dev/null 2>&1; then
        log "ERROR: pg_restore not found in PATH (this project's PostgreSQL container ships it: docker exec football_os_db pg_restore)"
        exit 1
    fi
    if ! command -v psql >/dev/null 2>&1; then
        log "ERROR: psql not found in PATH (this project's PostgreSQL container ships it: docker exec football_os_db psql)"
        exit 1
    fi
}

main() {
    if [[ -z "$BACKUP_FILE" ]]; then
        usage
        exit 1
    fi

    if [[ ! -f "$BACKUP_FILE" ]]; then
        log "ERROR: Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    log "Starting restore of $BACKUP_FILE to $TARGET_DB"

    # The name before the binaries and before the dump: a refused name must be the first thing this script says,
    # because everything after it is work done against the wrong database.
    if ! python "$ROOT/scripts/qa_db.py" --assert-scratch "$TARGET_DB"; then
        log "ERROR: refusing to restore into $TARGET_DB — scripts/qa_db.py owns the scratch-name policy and this name is not scratch"
        exit 1
    fi
    check_pg

    log "Verifying backup file"
    if ! pg_restore --list "$BACKUP_FILE" >/dev/null 2>&1; then
        log "ERROR: Invalid backup file format"
        exit 1
    fi
    log "Backup file verified"

    # Create the target through `scripts/qa_db.py` rather than a second copy of the DDL. It terminates backends,
    # drops `WITH (FORCE)`, creates the database and installs `vector`, which a fresh database needs before the
    # app's own schema can be built; a bare `CREATE DATABASE` here produced a target the restore then failed into.
    # Its stdout is the connection URL, so it goes to /dev/null: an operator's terminal and any log capture must
    # not end up holding a credential.
    log "Re-creating scratch target $TARGET_DB through scripts/qa_db.py"
    DATABASE_URL="postgresql+psycopg2://${PGUSER}@${PGHOST}:${PGPORT}/postgres" \
        python "$ROOT/scripts/qa_db.py" --name "$TARGET_DB" >/dev/null

    log "Restoring backup to $TARGET_DB on $PGHOST:$PGPORT"
    local rc=0
    pg_restore \
        --host="$PGHOST" \
        --port="$PGPORT" \
        --username="$PGUSER" \
        --dbname="$TARGET_DB" \
        --jobs=4 \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists \
        "$BACKUP_FILE" || rc=$?
    if ((rc != 0)); then
        # Reachable now: the status is captured, because `set -e` aborts the script before a trailing test can run.
        log "ERROR: pg_restore exited $rc — $TARGET_DB is a partial copy, so the migration replay and the success line are skipped"
        exit 1
    fi

    # `alembic.ini` is at apps/api/alembic.ini and the repository root has none, so the replay has to run from
    # there. From $ROOT this failed every time it was ever reached.
    log "Replaying migrations against $TARGET_DB (alembic runs from apps/api, where alembic.ini is)"
    (
        cd "$API"
        DATABASE_URL="postgresql+psycopg2://${PGUSER}@${PGHOST}:${PGPORT}/${TARGET_DB}" python -m alembic upgrade head
    )

    local tables
    # The count is the run's evidence, so an unread count is a failed run: a `:-0` here would let "holds 0 public
    # table(s)" read as a restored-but-empty database instead of as a query that did not answer.
    if ! tables="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$TARGET_DB" -tA -c \
        "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")" || [[ ! "$tables" =~ ^[0-9]+$ ]]; then
        log "ERROR: pg_restore and alembic returned but the restored table count could not be read, so this restore is unverified"
        exit 1
    fi
    log "Restore completed: $TARGET_DB on $PGHOST:$PGPORT holds $tables public table(s)"
}

main "$@"
