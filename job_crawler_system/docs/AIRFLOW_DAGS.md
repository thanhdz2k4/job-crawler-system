# Airflow DAGs - Job Crawler

Tài liệu này giải thích 2 DAG mới trong `job_crawler_system/dags/`:  
- `job_crawler_dag.py`: Chạy crawler TopCV.  
- `maintenance_dag.py`: Dọn log định kỳ.

## 1) job_crawler_dag.py – chạy Scrapy spider

**Mục tiêu:** Trigger `scrapy crawl topcv_spider` theo lịch (mặc định 7h sáng hàng ngày).

**Biến Airflow cần thiết (Variables):**
- `CRAWLER_HOME`: Thư mục chứa project (mặc định `/opt/airflow/jobs/job_crawler_system`).
- `MONGO_URI`: URI MongoDB (mặc định `mongodb://mongo:27017`).
- `MONGO_DATABASE`: Tên DB (mặc định `job_crawler_db`).

**Tham số runtime (dag_run.conf):**
- `max_pages`: Số trang list cần crawl. Mặc định 10.  
  Ví dụ khi trigger thủ công: `{ "max_pages": 5 }`.

**Lịch chạy:** `0 7 * * *` (hàng ngày 7h). Có thể đổi trong DAG.

**Cách sử dụng:**
1. Đưa file DAG vào thư mục DAGs của Airflow (hoặc mount `job_crawler_system/dags` vào `/opt/airflow/dags`).
2. Đặt Airflow Variables như trên (UI: Admin → Variables, hoặc CLI `airflow variables set`).
3. Đảm bảo môi trường Airflow/Docker image có đủ deps: `scrapy`, `pymongo`, `brotli` (TopCV cần), và các deps crawler khác.
4. Bật DAG `job_crawler_dag` trên UI. Nếu muốn chạy ngay, Trigger DAG và truyền `{"max_pages": 5}` nếu cần.

**Bên trong DAG:**
- Dùng `BashOperator`:
  ```bash
  cd {{ CRAWLER_HOME }} && scrapy crawl topcv_spider -a max_pages={{ dag_run.conf.get('max_pages', 10) }}
  ```
- Biến môi trường đặt cho process: `MONGO_URI`, `MONGO_DATABASE`.
- `execution_timeout`: 2 giờ.

## 2) maintenance_dag.py – dọn log

**Mục tiêu:** Xoá log cũ của Airflow và log crawler.

**Biến Airflow cần thiết:**
- `CRAWLER_LOG_RETENTION_DAYS`: Số ngày giữ log (mặc định 7).
- `CRAWLER_HOME`: Dùng lại cho đường dẫn log crawler (mặc định `/opt/airflow/jobs/job_crawler_system`).

**Lịch chạy:** `@weekly` (hàng tuần). Có thể đổi trong DAG.

**Cách sử dụng:**
1. Đảm bảo DAG trong thư mục DAGs.
2. Đặt Variables: `CRAWLER_LOG_RETENTION_DAYS` (tuỳ chọn), `CRAWLER_HOME`.
3. Bật DAG `maintenance_dag`.

**Bên trong DAG:**
- Task `prune_airflow_logs`: `find /opt/airflow/logs -type f -mtime +<retention> -delete`.
- Task `prune_crawler_logs`: nếu tồn tại thư mục `{{ CRAWLER_HOME }}/logs` thì xoá file log quá hạn.
- Chạy nối tiếp: `prune_airflow_logs >> prune_crawler_logs`.

## Checklist triển khai
- [ ] Mount hoặc copy `dags/` vào Airflow.
- [ ] Set Variables: `CRAWLER_HOME`, `MONGO_URI`, `MONGO_DATABASE`, `CRAWLER_LOG_RETENTION_DAYS` (tuỳ chọn).
- [ ] Image/venv Airflow có đầy đủ dependencies crawler.
- [ ] MongoDB truy cập được từ container Airflow (kiểm tra network/DNS).

## Lưu ý
- Nếu muốn crawl nguồn khác hoặc thêm spider, chỉnh `bash_command` trong `job_crawler_dag.py`.
- Nếu muốn giảm thời gian/chi phí, hạ `max_pages` hoặc tăng `DOWNLOAD_DELAY` bằng cách sửa spider hoặc truyền thêm `-s DOWNLOAD_DELAY=3` vào lệnh trong DAG.
