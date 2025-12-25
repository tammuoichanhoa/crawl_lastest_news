# crawl_lastest_news

Crawler thu thập các bài báo mới nhất từ nhiều trang tin tức Việt Nam (ví dụ: VNExpress, Tuổi Trẻ, Thanh Niên, Zing, v.v.) và lưu vào PostgreSQL thông qua SQLAlchemy.

## Tính năng chính
- Hỗ trợ nhiều site khác nhau, cấu hình tập trung trong `config.py` (mỗi site là một `SiteConfig`).
- Crawl song song nhiều site bằng `ThreadPoolExecutor`.
- Lưu dữ liệu vào PostgreSQL qua SQLAlchemy ORM.
- Tự động tạo schema nếu chưa tồn tại.
- Cấu hình kết nối DB qua biến môi trường hoặc file `.env`.

## Yêu cầu
- Python 3.10+ (khuyến nghị cùng phiên bản với môi trường hiện tại).
- PostgreSQL đang chạy (local hoặc Docker).

Cài đặt thư viện:

```bash
cd crawl_lastest_news
pip install -r requirements.txt
```

## Cấu hình database

Thư viện đọc chuỗi kết nối từ:
- Tham số dòng lệnh `--database-url`, hoặc
- Biến môi trường `DATABASE_URL`, hoặc
- File `.env` trong thư mục `crawl_lastest_news` (ví dụ: `crawl_lastest_news/.env`).

Ví dụ giá trị `DATABASE_URL`:

```bash
DATABASE_URL=postgresql+psycopg2://crawl:crawl@localhost:15432/lastest_news
```

### Sử dụng Docker Compose

Trong thư mục `crawl_lastest_news` đã có `docker-compose.yml` để khởi động PostgreSQL:

```bash
cd crawl_lastest_news
docker-compose up -d
```

Mặc định:
- User: `crawl`
- Password: `crawl`
- Database: `lastest_news`
- Port host: `15432`

## Cách chạy

Chạy dưới dạng module (khuyến nghị):

```bash
cd /path/to/project-root
python -m crawl_lastest_news.main --sites vnexpress tuoitre
```

Hoặc chạy trực tiếp file:

```bash
python crawl_lastest_news/main.py --sites vnexpress tuoitre
```

Một số tham số quan trọng (xem thêm trong `main.py`):
- `--sites SITE_KEY ...`  
  Danh sách site muốn crawl, ví dụ: `--sites vnexpress tuoitre`.  
  Nếu không truyền, chương trình sẽ crawl tất cả site được khai báo trong `config.py`.
- `--database-url`  
  Chuỗi kết nối DB, ví dụ:  
  `postgresql+psycopg2://user:pass@host:port/dbname`.  
  Nếu không cung cấp, chương trình dùng `DATABASE_URL` từ môi trường / `.env`.
- `--max-articles-per-site`  
  Giới hạn tổng số bài cho mỗi site (mặc định: không giới hạn).
- `--log-level`  
  Mức log: `DEBUG`, `INFO`, `WARNING`, `ERROR` (mặc định: `INFO`).
- `--echo-sql`  
  Bật log câu lệnh SQLAlchemy (phục vụ debug).
- `--workers`  
  Số luồng chạy song song (mặc định = số site được chọn).

## Log và theo dõi

Thư mục `logs/` chứa log crawl cho từng site, ví dụ:
- `logs/vnexpress.log`
- `logs/tuoitre.log`
- `logs/znews.log`

Bạn có thể tail file tương ứng để theo dõi tiến trình crawl:

```bash
tail -f logs/vnexpress.log
```

## Mở rộng / thêm site mới

- Thêm hoặc chỉnh sửa `SiteConfig` trong `config.py` để khai báo site mới (base URL, rule category, selector bài viết, v.v.).
- Nếu cần logic đặc thù, xem thêm các helper trong thư mục `crawler/` (ví dụ: `crawler/site_config.py`, `crawler/sitemap.py`, `crawler/throttle.py`).

