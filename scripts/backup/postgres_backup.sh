#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/config/backup.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

: "${DATABASE_URL:?DATABASE_URL is required (e.g. postgresql://crawl@localhost:5432/news_db)}"
: "${BACKUP_ROOT:?BACKUP_ROOT is required (e.g. /data/backups/news_db)}"

RETENTION_DAYS="${RETENTION_DAYS:-14}"
RETENTION_WEEKS="${RETENTION_WEEKS:-8}"
RETENTION_MONTHS="${RETENTION_MONTHS:-12}"
BACKUP_LOG_DIR="${BACKUP_LOG_DIR:-$BACKUP_ROOT/logs}"
EXCLUDE_SCHEMAS="${EXCLUDE_SCHEMAS:-}"

# Normalize common SQLAlchemy-style URLs so pg_dump/pg_restore can use them.
DB_URL="$DATABASE_URL"
DB_URL="${DB_URL/postgresql+psycopg2:\/\//postgresql:\/\/}"
DB_URL="${DB_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

umask 077
mkdir -p "$BACKUP_ROOT" "$BACKUP_LOG_DIR"

LOCK_FILE="${LOCK_FILE:-/tmp/news_db_pg_backup.lock}"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another backup process is running; exiting." >&2
  exit 0
fi

ts="$(date -u +%Y%m%dT%H%M%SZ)"
dump_dir="$BACKUP_ROOT/dumps"
mkdir -p "$dump_dir"

dump_file="$dump_dir/news_db_${ts}.dump"
sha_file="${dump_file}.sha256"
log_file="$BACKUP_LOG_DIR/backup_${ts}.log"

cleanup_partial_dump() {
  if [[ -f "$dump_file" && ! -f "$sha_file" ]]; then
    rm -f "$dump_file" 2>/dev/null || true
  fi
}
trap cleanup_partial_dump EXIT

echo "[$(date -u --iso-8601=seconds)] Starting pg_dump -> $dump_file" | tee -a "$log_file"

# NOTE:
# - Prefer DATABASE_URL without password and use ~/.pgpass for cron.
# - If you must embed the password, use a root-owned env file with chmod 600.
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --compress=9 \
  ${EXCLUDE_SCHEMAS:+$(printf '%s' "$EXCLUDE_SCHEMAS" | tr ',' '\n' | sed -e 's/^/--exclude-schema=/' -e 's/$/ /' | tr -d '\n')}\
  --file "$dump_file" \
  "$DB_URL" >>"$log_file" 2>&1

sha256sum "$dump_file" > "$sha_file"

echo "[$(date -u --iso-8601=seconds)] Verifying pg_restore -l" | tee -a "$log_file"
pg_restore -l "$dump_file" >/dev/null 2>>"$log_file"

ln -sfn "$(basename "$dump_file")" "$dump_dir/latest.dump"

echo "[$(date -u --iso-8601=seconds)] Backup complete" | tee -a "$log_file"

# Retention: keep daily for RETENTION_DAYS; keep weekly and monthly anchors beyond that window.
# Simple approach:
# - Delete dumps older than RETENTION_DAYS unless they are weekly/monthly anchors.

now_epoch="$(date -u +%s)"
for f in "$dump_dir"/news_db_*.dump; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  # base: news_db_YYYYmmddTHHMMSSZ.dump
  stamp="${base#news_db_}"
  stamp="${stamp%.dump}"

  # Parse UTC timestamp
  yyyy="${stamp:0:4}"
  mm="${stamp:4:2}"
  dd="${stamp:6:2}"
  hh="${stamp:9:2}"
  mi="${stamp:11:2}"
  ss="${stamp:13:2}"
  file_epoch="$(date -u -d "${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}Z" +%s 2>/dev/null || echo 0)"
  [[ "$file_epoch" -gt 0 ]] || continue
  age_days=$(( (now_epoch - file_epoch) / 86400 ))

  dow="$(date -u -d "${yyyy}-${mm}-${dd}" +%u)" # 1..7 (Mon..Sun)

  keep="no"
  if [[ "$age_days" -le "$RETENTION_DAYS" ]]; then
    keep="yes"
  fi
  # Weekly anchor: keep Sunday dumps up to RETENTION_WEEKS
  if [[ "$keep" == "no" && "$dow" == "7" && "$age_days" -le $((RETENTION_WEEKS * 7)) ]]; then
    keep="yes"
  fi
  # Monthly anchor: keep day 01 dumps up to RETENTION_MONTHS (~31 days each)
  if [[ "$keep" == "no" && "$dd" == "01" && "$age_days" -le $((RETENTION_MONTHS * 31)) ]]; then
    keep="yes"
  fi

  if [[ "$keep" == "no" ]]; then
    rm -f "$f" "${f}.sha256" 2>>"$log_file" || true
  fi
done

trap - EXIT
