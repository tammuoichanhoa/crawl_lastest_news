#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/config/backup.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required}"

# Normalize common SQLAlchemy-style URLs so pg_restore can use them.
DB_URL="$DATABASE_URL"
DB_URL="${DB_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"
DB_URL="${DB_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

dump_dir="$BACKUP_ROOT/dumps"
dump_file="${1:-$dump_dir/latest.dump}"

if [[ -L "$dump_file" ]]; then
  dump_file="$dump_dir/$(readlink "$dump_file")"
fi
test -f "$dump_file"

echo "About to restore dump: $dump_file"
echo "Target database: $DB_URL"
echo "This will run pg_restore --clean --if-exists"
read -r -p "Type YES to continue: " confirm
[[ "$confirm" == "YES" ]]

pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --dbname "$DB_URL" \
  "$dump_file"
echo "Restore completed."
