#!/usr/bin/env bash
# Backs up the SQLite database using the SQLite .backup command (safe with WAL mode).
# Usage: bash scripts/backup_db.sh [backup_dir]
# Default backup_dir: ./backups/
set -euo pipefail

DB_PATH="${DATABASE_PATH:-instance/nammapayana.db}"
BACKUP_DIR="${1:-backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/nammapayana_$TIMESTAMP.db"

if [ ! -f "$DB_PATH" ]; then
  echo "Database not found at $DB_PATH — nothing to back up."
  exit 0
fi

sqlite3 "$DB_PATH" ".backup $BACKUP_FILE"
echo "Backup written to $BACKUP_FILE"
ls -lh "$BACKUP_FILE"
