#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/config/backup.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

: "${BACKUP_ROOT:?BACKUP_ROOT is required}"

dump_dir="$BACKUP_ROOT/dumps"
dump_file="${1:-$dump_dir/latest.dump}"

if [[ -L "$dump_file" ]]; then
  dump_file="$dump_dir/$(readlink "$dump_file")"
fi

echo "Verifying: $dump_file"
test -f "$dump_file"
test -f "${dump_file}.sha256"

(cd "$(dirname "$dump_file")" && sha256sum -c "$(basename "${dump_file}.sha256")")
pg_restore -l "$dump_file" >/dev/null
echo "OK"
