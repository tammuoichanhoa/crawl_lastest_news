# Backup PostgreSQL (`news_db`)

Mục tiêu: tạo backup định kỳ cho DB `news_db` và lưu sang **ổ đĩa khác đã mount** trên server (ví dụ: `/data/backups/news_db`), có verify và có hướng dẫn restore.

## Yêu cầu

Cần có các tool:
- `pg_dump`, `pg_restore`, `psql` (PostgreSQL client tools)
- `flock`, `sha256sum`, `find` (thường có sẵn trên Linux)

## Cấu hình

### 1) Chọn nơi lưu backup (ổ đĩa đã mount)

Xác định mountpoint:
```bash
df -h
mount | head -n 50
```

Chọn `BACKUP_ROOT` (ví dụ): `/data/backups/news_db`

Tạo thư mục (chạy trên server):
```bash
sudo mkdir -p /data/backups/news_db
sudo chown -R "$USER":"$USER" /data/backups/news_db
chmod 700 /data/backups/news_db
```

### 2) Tạo file env cho backup

Repo có template: `config/backup.env.example`

Tạo file thật (không commit, đã được ignore):
```bash
cp config/backup.env.example config/backup.env
chmod 600 config/backup.env
```

Chỉnh `config/backup.env` theo môi trường của bạn:
- `DATABASE_URL=postgresql://crawl:crawl@localhost:5432/news_db`
- `BACKUP_ROOT=/path/to/mounted-disk/news_db`

Ghi chú:
- Backup scripts cần **libpq URL** dạng `postgresql://...`
- Nếu bạn đang dùng SQLAlchemy URL dạng `postgresql+psycopg2://...` thì scripts có normalize sang `postgresql://...` nên vẫn chạy được.
- Nếu gặp lỗi kiểu `permission denied for schema docker_stage` khi dump, có 2 hướng:
  - Cấp quyền cho user backup để đọc được schema đó, hoặc
  - Loại trừ schema khỏi dump bằng `EXCLUDE_SCHEMAS=docker_stage` trong `config/backup.env`.

### 3) Khuyến nghị: dùng `~/.pgpass` (tránh lộ mật khẩu trong cron)

Với user chạy cron:
```bash
echo "localhost:5432:news_db:crawl:crawl" >> ~/.pgpass
chmod 600 ~/.pgpass
```

Sau đó đặt `DATABASE_URL=postgresql://crawl@localhost:5432/news_db` (không có password) trong `config/backup.env`.

Test:
```bash
psql "postgresql://crawl@localhost:5432/news_db" -c "select 1;"
```

## Chạy backup thủ công

```bash
ENV_FILE=config/backup.env scripts/backup/postgres_backup.sh
```

Output sẽ nằm dưới:
- Dumps: `$BACKUP_ROOT/dumps/news_db_YYYYmmddTHHMMSSZ.dump`
- Checksums: cùng thư mục, `*.sha256`
- Log: `$BACKUP_LOG_DIR/backup_*.log`
- Symlink: `$BACKUP_ROOT/dumps/latest.dump`

## Verify backup

```bash
ENV_FILE=config/backup.env scripts/backup/postgres_verify.sh
```

Verify làm 2 việc:
- `sha256sum -c` checksum
- `pg_restore -l` để đảm bảo dump đọc được

## Restore backup

Khuyến nghị restore vào DB test trước.

Ví dụ tạo DB test:
```bash
createdb -h localhost -p 5432 -U crawl news_db_restore_test
```

Restore (sẽ hỏi xác nhận `YES`):
```bash
DATABASE_URL=postgresql://crawl@localhost:5432/news_db_restore_test \
ENV_FILE=config/backup.env \
scripts/backup/postgres_restore.sh /path/to/news_db_*.dump
```

## Lịch chạy định kỳ (cron)

Template: `cron/backup_postgres.cron`

Cài crontab:
```bash
crontab cron/backup_postgres.cron
crontab -l
```

Ghi chú:
- Cron chạy theo **timezone của hệ thống**.
- File cron hiện đang redirect log theo đường dẫn ví dụ `/data/backups/news_db/...` — hãy sửa cho khớp `BACKUP_ROOT`/`BACKUP_LOG_DIR` của bạn.

## Retention (xóa backup cũ)

`scripts/backup/postgres_backup.sh` sẽ xóa backup cũ sau khi backup thành công, theo biến:
- `RETENTION_DAYS` (mặc định `14`): giữ backup hàng ngày
- `RETENTION_WEEKS` (mặc định `8`): giữ backup ngày Chủ nhật (weekly anchor)
- `RETENTION_MONTHS` (mặc định `12`): giữ backup ngày 01 mỗi tháng (monthly anchor)

## Ops checklist

- Theo dõi dung lượng ổ đĩa backup: `df -h`
- Thỉnh thoảng test restore vào DB test
- Kiểm tra log trong `$BACKUP_LOG_DIR`
