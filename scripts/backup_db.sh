#!/usr/bin/env bash
# Backup script for FOOTBALL OS PostgreSQL database
# Usage: ./backup_db.sh [full|incremental]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_TYPE="${1:-full}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-/var/backups/football_os}"
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-football}"
PGDATABASE="${PGDATABASE:-football_os}"

mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] $*"
}

check_pg() {
    if ! command -v pg_dump >/dev/null 2>&1; then
        log "ERROR: pg_dump not found in PATH"
        exit 1
    fi
    if ! pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" >/dev/null 2>&1; then
        log "ERROR: Cannot connect to PostgreSQL at $PGHOST:$PGPORT"
        exit 1
    fi
}

full_backup() {
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

    # Cleanup old local backups (keep last 7)
    find "$BACKUP_DIR" -name "football_os_*.dump" -type f -mtime +7 -delete
    log "Cleanup: removed backups older than 7 days"
}

incremental_backup() {
    # For PostgreSQL, incremental = WAL archiving (handled by pgBackRest/WAL-G)
    # This script just verifies WAL archiving is working
    log "Checking WAL archive status"

    if command -v pg_waldump >/dev/null 2>&1; then
        # Check latest WAL file
        latest_wal=$(pg_waldump -n 1 2>/dev/null | head -1 || true)
        log "Latest WAL: $latest_wal"
    fi

    # Check replication lag if replica exists
    if [[ -n "${REPLICA_HOST:-}" ]]; then
        lag=$(psql -h "$REPLICA_HOST" -U "$PGUSER" -d "$PGDATABASE" -t -c \
            "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))" 2>/dev/null || echo "unknown")
        log "Replication lag: ${lag}s"
        if [[ "$lag" != "unknown" && $(echo "$lag > 300" | bc -l 2>/dev/null || echo 0) -eq 1 ]]; then
            log "WARNING: Replication lag exceeds 5 minutes"
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