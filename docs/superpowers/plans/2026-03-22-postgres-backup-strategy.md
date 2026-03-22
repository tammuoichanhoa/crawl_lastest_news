# PostgreSQL Backup Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automated, verifiable PostgreSQL backups for `news_db` to a mounted “other disk” on this server, driven by `DATABASE_URL=postgresql://crawl:crawl@localhost:5432/news_db`.

**Architecture:** Use `pg_dump` (logical backups) to create timestamped dump files on a dedicated backup mount, plus a lightweight verification step (`pg_restore -l`) and retention/rotation. Keep secrets out of crontab by relying on `.pgpass` (recommended) or a root-owned env file.

**Tech Stack:** PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`), `bash`, `cron`, `flock`, `sha256sum`, `find`.

---

## Proposed File/Folder Structure

**Create:**
- `scripts/backup/postgres_backup.sh` (creates dumps + retention + checksums)
- `scripts/backup/postgres_verify.sh` (verifies dump integrity + basic readability)
- `scripts/backup/postgres_restore.sh` (restores from a chosen dump)
- `config/backup.env.example` (non-secret config template)
- `cron/backup_postgres.cron` (cron entry template)
- `docs/backup.md` (how to configure/run/restore)

**Modify:**
- `.gitignore` (ignore `config/backup.env`)
- `README.md` (link to `docs/backup.md`)

**Backup storage on mounted disk (outside repo):**
- `/data/backups/news_db/` (adjust to your real mount; see Task 1)

---

### Task 1: Confirm backup mount + retention policy

**Files:**
- Create: `docs/backup.md`

- [ ] **Step 1: Identify the mounted backup disk path**

Run:
```bash
df -h
mount | head -n 50
```

Decide and record in `docs/backup.md`:
- `BACKUP_ROOT` (example: `/data/backups/news_db`)
- Ensure it’s a mount point (recommended):
  - Example check: `mountpoint -q /data`

- [ ] **Step 2: Pick retention defaults**

Recommended starting point (edit as needed):
- Keep **daily** dumps for `14` days
- Keep **weekly** dumps for `8` weeks (by preserving one dump created on Sunday)
- Keep **monthly** dumps for `12` months (by preserving one dump created on day `01`)

Document these in `docs/backup.md` and encode them in `config/backup.env.example`.

- [ ] **Step 3: Create the backup directory (on the mounted disk)**

Run:
```bash
sudo mkdir -p /data/backups/news_db
sudo chown -R "$USER":"$USER" /data/backups/news_db
chmod 700 /data/backups/news_db
```

Expected: directory exists and is only accessible to the backup user.

---

### Task 2: Add backup configuration template (`config/backup.env.example`)

**Files:**
- Create: `config/backup.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Create `config/backup.env.example`**

Create `config/backup.env.example`:
```bash
# Required
# For best practice, remove the password from this URL and use ~/.pgpass instead.
DATABASE_URL=postgresql://crawl@localhost:5432/news_db

# Where backups are stored (should be on the mounted “other disk”)
BACKUP_ROOT=/data/backups/news_db

# Retention
RETENTION_DAYS=14
RETENTION_WEEKS=8
RETENTION_MONTHS=12

# Logging
BACKUP_LOG_DIR=/data/backups/news_db/logs
```

- [ ] **Step 2: Ignore the real env file**

Update `.gitignore` to include:
```gitignore
config/backup.env
```

- [ ] **Step 3: Create the real env file on the server (not committed)**

Run:
```bash
cp config/backup.env.example config/backup.env
chmod 600 config/backup.env
```

Then edit `config/backup.env` to match your actual `DATABASE_URL` and mount path.

---

### Task 3: Implement `scripts/backup/postgres_backup.sh`

**Files:**
- Create: `scripts/backup/postgres_backup.sh`
- Test: manual run commands below

- [ ] **Step 1: Create the script**

Create `scripts/backup/postgres_backup.sh`:
```bash
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

echo "[$(date -u --iso-8601=seconds)] Starting pg_dump -> $dump_file" | tee -a "$log_file"

# NOTE:
# - Prefer DATABASE_URL without password and use ~/.pgpass for cron.
# - If you must embed the password, use a root-owned env file with chmod 600.
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --compress=9 \
  --file "$dump_file" \
  "$DATABASE_URL" >>"$log_file" 2>&1

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
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x scripts/backup/postgres_backup.sh
```

- [ ] **Step 3: Manual test run**

Run:
```bash
ENV_FILE=config/backup.env scripts/backup/postgres_backup.sh
```

Expected:
- Creates a file like `/data/backups/news_db/dumps/news_db_YYYYmmddTHHMMSSZ.dump`
- Creates matching `.sha256`
- Updates symlink `/data/backups/news_db/dumps/latest.dump`
- Exit code `0`

---

### Task 4: Implement `scripts/backup/postgres_verify.sh`

**Files:**
- Create: `scripts/backup/postgres_verify.sh`

- [ ] **Step 1: Create the script**

Create `scripts/backup/postgres_verify.sh`:
```bash
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
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x scripts/backup/postgres_verify.sh
```

- [ ] **Step 3: Run it**

Run:
```bash
ENV_FILE=config/backup.env scripts/backup/postgres_verify.sh
```

Expected: prints `OK` and exits `0`.

---

### Task 5: Implement `scripts/backup/postgres_restore.sh`

**Files:**
- Create: `scripts/backup/postgres_restore.sh`

- [ ] **Step 1: Create the script**

Create `scripts/backup/postgres_restore.sh`:
```bash
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

dump_dir="$BACKUP_ROOT/dumps"
dump_file="${1:-$dump_dir/latest.dump}"

if [[ -L "$dump_file" ]]; then
  dump_file="$dump_dir/$(readlink "$dump_file")"
fi
test -f "$dump_file"

echo "About to restore dump: $dump_file"
echo "Target database: $DATABASE_URL"
echo "This will run pg_restore --clean --if-exists"
read -r -p "Type YES to continue: " confirm
[[ "$confirm" == "YES" ]]

pg_restore \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --dbname "$DATABASE_URL" \
  "$dump_file"
echo "Restore completed."
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x scripts/backup/postgres_restore.sh
```

- [ ] **Step 3: Document safe restore workflow**

In `docs/backup.md`, recommend restoring to a *new* database first:
```bash
createdb -h localhost -p 5432 -U crawl news_db_restore_test
DATABASE_URL=postgresql://crawl@localhost:5432/news_db_restore_test \
  ENV_FILE=config/backup.env scripts/backup/postgres_restore.sh /path/to/dump
```

---

### Task 6: Configure auth for cron (avoid plaintext passwords)

**Files:**
- Modify: `docs/backup.md`

- [ ] **Step 1: Prefer `.pgpass`**

Create `~/.pgpass` for the user running cron:
```bash
echo "localhost:5432:news_db:crawl:crawl" >> ~/.pgpass
chmod 600 ~/.pgpass
```

Then set `DATABASE_URL=postgresql://crawl@localhost:5432/news_db` (no password) in `config/backup.env`.

- [ ] **Step 2: Verify non-interactive connection**

Run:
```bash
psql "postgresql://crawl@localhost:5432/news_db" -c "select 1;"
```

Expected: returns `1` without prompting for password.

---

### Task 7: Schedule backups via cron

**Files:**
- Create: `cron/backup_postgres.cron`
- Modify: `docs/backup.md`

- [ ] **Step 1: Create cron template**

Create `cron/backup_postgres.cron`:
```cron
# Daily at 02:10 UTC - adjust timezone/time as needed
10 2 * * * cd /home/dev/BA_workspace/crawl_lastest_news && ENV_FILE=config/backup.env scripts/backup/postgres_backup.sh >> /data/backups/news_db/logs/cron_backup.log 2>&1

# Weekly verify (Sunday 03:10 UTC)
10 3 * * 0 cd /home/dev/BA_workspace/crawl_lastest_news && ENV_FILE=config/backup.env scripts/backup/postgres_verify.sh >> /data/backups/news_db/logs/cron_verify.log 2>&1
```

- [ ] **Step 2: Install cron**

Run:
```bash
crontab cron/backup_postgres.cron
crontab -l
```

Expected: shows the two entries.

---

### Task 8: Documentation and quick-start

**Files:**
- Modify: `README.md`
- Modify: `docs/backup.md`

- [ ] **Step 1: Add `docs/backup.md`**

Include:
- Required tools: `pg_dump`, `pg_restore`, `psql`, `flock`
- Config steps (`config/backup.env` + `.pgpass`)
- Backup runbook (manual run + where files land)
- Restore runbook (restore to test DB first)
- Ops checklist: monitor disk usage (`df -h`), check logs, occasionally perform full restore test

- [ ] **Step 2: Link from README**

Add a short “Backups” section to `README.md` pointing to `docs/backup.md`.

---

## Acceptance Checklist

- [ ] Running `ENV_FILE=config/backup.env scripts/backup/postgres_backup.sh` creates a new dump, checksum, and passes `pg_restore -l`.
- [ ] `scripts/backup/postgres_verify.sh` validates checksum and lists dump successfully.
- [ ] Cron entries run without interactive prompts (via `.pgpass`).
- [ ] Backups are written to the mounted disk path and retention removes old dumps as expected.
- [ ] Restore procedure documented and validated at least once to a test database.

---

## Optional Phase 2 (If You Need PITR)

If you need point-in-time recovery (PITR) instead of periodic dumps:
- Configure `archive_mode=on` and `archive_command` to ship WAL files to the mounted disk.
- Take regular `pg_basebackup` snapshots.

This requires PostgreSQL server config changes and is intentionally out of scope for Phase 1.
