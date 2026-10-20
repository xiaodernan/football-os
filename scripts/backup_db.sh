#!/usr/bin/env bash
# Backup script for FOOTBALL OS PostgreSQL database
# Usage: ./backup_db.sh [full|incremental]
#
# `incremental` asks the server whether it can do incremental backups at all and refuses if it cannot. It used to
# print "Backup completed successfully" and exit 0 whatever the server said, producing no artifact — a scheduled
# job whose exit code meant "the script ran", so a month of silently missing WAL archives would look green.
# The refusal is the point: a backup that does not exist has to be loud.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=/dev/null
source "$ROOT/scripts/dr_lib.sh"

BACKUP_TYPE="${1:-full}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/var/backups/football_os}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
# Host, port, user and database come from `infra/docker-compose.yml` through `dr_pg_defaults`; an exported PG*
# still wins. The typed `5432` default these lines replace pointed at a port this project's container does not
# publish (it publishes 54321), which made every connection in this script a question about the wrong server.
dr_pg_defaults

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] $*"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log "ERROR: $1 not found in PATH (this project's PostgreSQL container ships it: docker exec football_os_db $1)"
        exit 1
    fi
}

check_pg() {
    require_cmd pg_isready
    if ! pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1; then
        log "ERROR: Cannot connect to PostgreSQL at $PGHOST:$PGPORT"
        log "       those coordinates are read from infra/docker-compose.yml; export PGHOST/PGPORT/PGUSER to override"
        exit 1
    fi
}

full_backup() {
    require_cmd pg_dump
    require_cmd pg_restore
    local file="${BACKUP_DIR}/football_os_${TIMESTAMP}.dump"
    log "Starting full backup to $file"

    pg_dump \
        --host="$PGHOST" \
        --port="$PGPORT" \
        --username="$PGUSER" \
        --dbname="$PGDATABASE" \
        --format=custom \
        --compress=3 \
        --no-owner \
        --no-privileges \
        --file="$file"

    local size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file")
    log "Full backup completed: $file ($(numfmt --to=iec "$size"))"

    # Verify backup
    if pg_restore --list "$file" >/dev/null 2>&1; then
        log "Backup verification: PASSED"
    else
        log "ERROR: Backup verification FAILED"
        exit 1
    fi

    # Upload to S3 if configured
    if [[ -n "$S3_BUCKET" ]]; then
        log "Uploading to s3://$S3_BUCKET/$(basename "$file")"
        aws s3 cp "$file" "s3://$S3_BUCKET/$(basename "$file")" --storage-class STANDARD_IA
    fi

    # Cleanup old local backups (keep last 7). The count is read from the same listing that is deleted: this line
    # used to announce removals it had not counted, and a schedule that keeps every file says "removed" all the same.
    local stale_list stale_count f
    stale_list="$(mktemp)"
    find "$BACKUP_DIR" -name "football_os_*.dump" -type f -mtime +7 -print >"$stale_list"
    stale_count="$(grep -c . "$stale_list" || true)"
    while IFS= read -r f; do
        rm -f "$f"
    done <"$stale_list"
    rm -f "$stale_list"
    log "Cleanup: removed $stale_count backup(s) older than 7 days"
}

# Ask the server whether it archives write-ahead log at all, and refuse if it does not.
#
# The branch this replaces ran `pg_waldump -n 1 ... || true`, printed nothing decisive when the binary was missing
# (it is missing on this host, and pg_waldump reads the data directory, so a client host cannot run it against a
# container anyway), and fell through to main's "Backup completed successfully" with exit 0 and no artifact written.
# A scheduled job reading that exit code would have reported green for as long as WAL archiving stayed off — which
# is its state in this repository's own container today.
incremental_backup() {
    require_cmd psql
    local mode
    mode="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tA -c "SHOW archive_mode" 2>/dev/null || true)"
    if [[ "$mode" != "on" ]]; then
        log "REFUSED: an incremental backup is a write-ahead-log archive, and $PGHOST:$PGPORT answers archive_mode='${mode:-nothing}'."
        log "         arm it (archive_mode=on plus an archive_command, or pgBackRest/WAL-G) and re-run, or take a"
        log "         logical dump now: ./scripts/backup_db.sh full"
        exit 2
    fi

    local archived
    archived="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tA -F"|" -c \
        "SELECT COALESCE(last_archived_wal, '-'), COALESCE(last_archived_time::text, '-'), failed_count FROM pg_stat_archiver" 2>/dev/null || true)"
    if [[ -z "$archived" ]]; then
        log "REFUSED: archive_mode is on but pg_stat_archiver did not answer, so nothing here can say a WAL segment was archived."
        exit 2
    fi
    local wal wal_time failures
    IFS="|" read -r wal wal_time failures <<<"$archived"
    if [[ "$wal" == "-" ]]; then
        log "REFUSED: archive_mode is on but no segment has ever been archived (pg_stat_archiver.last_archived_wal is null)."
        exit 2
    fi
    log "Last archived WAL: $wal at $wal_time; $failures failed archive attempt(s)"

    # Check replication lag if a replica is named. "unknown" is a refusal, not a pass: the lag below is the figure
    # docs/BACKUP_RECOVERY.md's alerting table promises to verify daily, and a query that did not answer verified nothing.
    if [[ -n "${REPLICA_HOST:-}" ]]; then
        local lag ceiling="${REPLICA_LAG_CEILING_SECONDS:-300}"
        lag="$(psql -h "$REPLICA_HOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -tA -c \
            "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))" 2>/dev/null || true)"
        if [[ ! "$lag" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            log "REFUSED: REPLICA_HOST=$REPLICA_HOST did not answer the replay-lag query (got '${lag:-nothing}')."
            exit 2
        fi
        log "Replication lag: ${lag}s against a ${ceiling}s ceiling"
        if awk -v lag="$lag" -v ceiling="$ceiling" 'BEGIN { exit !(lag > ceiling) }'; then
            log "ERROR: replication lag ${lag}s exceeds the ${ceiling}s ceiling"
            exit 2
        fi
    fi
}

main() {
    log "Starting $BACKUP_TYPE backup for $PGDATABASE on $PGHOST:$PGPORT"
    check_pg

    case "$BACKUP_TYPE" in
        full)
            full_backup
            ;;
        incremental|wal)
            incremental_backup
            ;;
        *)
            log "ERROR: Unknown backup type: $BACKUP_TYPE (use: full|incremental|wal)"
            exit 1
            ;;
    esac

    log "Backup completed successfully"
}

main "$@"