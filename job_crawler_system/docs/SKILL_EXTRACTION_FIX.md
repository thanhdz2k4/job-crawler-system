# Skill Extraction Fix (Legacy - skill extraction currently disabled)

## Vấn đề

Trước đây, hệ thống có vấn đề:
- Jobs có description/requirements nhưng không có skills được lưu vào database
- Nguyên nhân: Race condition giữa skill extraction và database insertion
- Khi API call thất bại, job vẫn được lưu với skills = []

## Giải pháp đã triển khai

### 1. Cải thiện skill extraction (`src/utils/skills.py`)

- Thêm hàm `extract_skills()` với retry mechanism cải tiến
- Thêm exponential backoff với jitter để tránh rate limiting
- Tăng timeout cho các lần retry sau
- Thêm hàm `extract_skills_sync()` để đảm bảo blocking behavior

### 2. Cập nhật parser (`src/crawlers/topcv/parser.py`)

- Sửa hàm `extract_skills()` để sử dụng synchronous blocking
- Kiểm tra độ dài text trước khi gọi API
- Return `None` nếu skill extraction thất bại để ngăn job được lưu

### 3. Cập nhật spider (`src/crawlers/topcv/spider.py`)

- Thêm validation để kiểm tra `skills_extracted` flag
- Skip job nếu skill extraction thất bại
- Log chi tiết về số skills được extract

### 4. Cập nhật pipeline (`src/crawlers/common/pipelines.py`)

- Thêm validation trong `ValidationPipeline`
- Drop job nếu có đủ content nhưng không có skills
- Đảm bảo chỉ jobs có skills mới được lưu vào database

### 5. Script xử lý jobs cũ (`scripts/process_missing_skills.py`)

- **Đã vô hiệu hóa**: script và bước xử lý skills đã được gỡ bỏ.
- Hỗ trợ `--limit` để giới hạn số jobs xử lý

### 6. Cập nhật Airflow DAG (`dags/job_crawler_dag.py`)

- Thêm task `process_missing_skills` chạy sau khi crawl
- Có thể cấu hình qua `dag_run.conf`
- Chạy script để xử lý jobs thiếu skills

## Cách sử dụng

### 1. Chạy crawler bình thường

```bash
scrapy crawl topcv_spider -a max_pages=10
```

Bây giờ crawler sẽ:
- Chỉ lưu jobs có đủ content VÀ skills được extract thành công
- Skip jobs không có skills (với đủ content)
- Log chi tiết về quá trình skill extraction

### 2. Xử lý jobs cũ thiếu skills

```bash
# Kiểm tra trước (dry run)
python scripts/process_missing_skills.py --limit 100 --dry-run

# Xử lý thực tế
python scripts/process_missing_skills.py --limit 100
```

### 3. Trigger qua Airflow

```bash
# Chạy DAG với config
airflow dags trigger job_crawler_dag \
    --conf '{"max_pages": 10, "skills_limit": 200, "dry_run": false}'
```

## Cấu hình

### Environment variables

Trong file `.env`:

```bash
# OpenAI API settings
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=http://your-api-endpoint/v1
OPENAI_MODEL=mistral/pixtral-12b-2409
```

### Airflow Variables

- `CRAWLER_HOME`: Đường dẫn đến project
- `MONGO_URI`: MongoDB connection string
- `MONGO_DATABASE`: Database name

## Monitoring

### Logs

Kiểm tra logs để theo dõi:
- Skill extraction success/failure rate
- Number of jobs skipped due to missing skills
- API rate limiting và retry attempts

### Database queries

```javascript
// Kiểm tra jobs không có skills
db.job_postings_raw.countDocuments({
  "skills": {"$size": 0},
  "$or": [
    {"description": {"$regex": ".{50,}", "$options": "i"}},
    {"requirements": {"$regex": ".{50,}", "$options": "i"}}
  ]
})

// Kiểm tra jobs có skills
db.job_postings_raw.countDocuments({
  "skills": {"$gt": []}
})
```

## Troubleshooting

### 1. Skill extraction thất bại

- Kiểm tra API key và endpoint trong `.env`
- Kiểm tra network connection đến API server
- Xem logs để xác định lỗi cụ thể

### 2. Rate limiting

- Tăng `_min_request_interval` trong `skills.py`
- Giảm concurrent requests trong `settings.py`
- Sử dụng API endpoint với rate limit cao hơn

### 3. Jobs bị skip quá nhiều

- Kiểm tra xem API có đang hoạt động không
- Kiểm tra quality của job descriptions
- Tạm thời disable validation trong pipeline nếu cần

## Tương lai

1. **Async processing**: Sử dụng message queue (Redis/Celery) cho skill extraction
2. **Batch processing**: Process skills theo batch để giảm API calls
3. **Caching**: Cache results cho similar job descriptions
4. **ML improvement**: Train custom model cho skill extraction
