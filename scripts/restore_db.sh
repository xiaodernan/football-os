#!/usr/bin/env bash
# Restore script for FOOTBALL OS PostgreSQL database
# Usage: ./restore_db.sh <backup_file.dump> [target_database]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_FILE="${1:-}"
TARGET_DB="${2:-football_os_restore}"

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <backup_file.dump> [target_database]"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-football}"

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] $*"
}

check_pg() {
    if ! command -v pg_restore >/dev/null 2>&1; then
        log "ERROR: pg_restore not found in PATH"
        exit 1
    fi
    if ! command -v psql >/dev/null 2>&1; then
        log "ERROR: psql not found in PATH"
        exit 1
    fi
}

main() {
    log "Starting restore of $BACKUP_FILE to $TARGET_DB"
    check_pg

    # Verify backup file
    log "Verifying backup file..."
    if ! pg_restore --list "$BACKUP_FILE" >/dev/null 2>&1; then
        log "ERROR: Invalid backup file format"
        exit 1
    fi
    log "Backup file verified"

    # Create target database (or use existing)
    log "Creating target database: $TARGET_DB"
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c \
        "DROP DATABASE IF EXISTS $TARGET_DB; CREATE DATABASE $TARGET_DB;"

    # Restore
    log "Restoring backup to $TARGET_DB..."
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
        "$BACKUP_FILE"

    if [[ $? -eq 0 ]]; then
        log "Restore completed successfully"

        # Run migrations to ensure schema is current
        log "Running alembic migrations..."
        cd "$(dirname "$0")/.."
        DATABASE_URL="postgresql+psycopg2://$PGUSER@$PGHOST:$PGPORT/$TARGET_DB" \
            python -m alembic upgrade head

        log "Restore completed successfully. Database: $TARGET_DB"
    else
        log "ERROR: Restore failed"
        exit 1
    fi
}

main "$@"