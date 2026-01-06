# Job Crawler System - TopCV Spider

Hệ thống thu thập dữ liệu việc làm từ TopCV.vn sử dụng Scrapy, MongoDB và Airflow.

## 📋 Tính năng đã triển khai

### ✅ Core Components
- **Items** (`items.py`): Định nghĩa JobItem với 30+ fields
- **Parser** (`parser.py`): Parse HTML, extract salary, dates
- **Spider** (`spider.py`): Crawl job listings với pagination & incremental crawling
- **Pipelines** (`pipelines.py`): Validation, cleaning, MongoDB upsert với versioning
- **Middlewares** (`middlewares.py`): User-Agent rotation, proxy support, retry logic

### 📊 Database Utilities
- Content hashing để detect changes
- Document versioning (lưu history)
- Upsert logic (insert/update intelligent)
- MongoDB helper với statistics

### ⚙️ Configuration
- Centralized config với `settings.yaml`
- MongoDB connection factory
- Environment variables support

## 🚀 Cài đặt

### 1. Cài đặt dependencies
```bash
pip install scrapy pymongo pyyaml beautifulsoup4
```

### 2. Cấu hình MongoDB
Đảm bảo MongoDB đang chạy:
```bash
# Windows
net start MongoDB

# Linux/Mac
sudo systemctl start mongodb
```

### 3. Cấu hình settings
Edit `config/settings.yaml`:
```yaml
mongodb:
  uri: "mongodb://localhost:27017"
  database: "job_crawler_db"

scrapy:
  download_delay: 2
  concurrent_requests: 8
```

## 📖 Sử dụng

### Chạy Spider đơn lẻ

```bash
# Chạy từ thư mục project root
cd job_crawler_system

# Chạy spider với default settings
scrapy crawl topcv_spider

# Chạy với custom max_pages
scrapy crawl topcv_spider -a max_pages=5

# Chạy full spider (không incremental)
scrapy crawl topcv_full_spider -a max_pages=100

# Chạy với custom settings
scrapy crawl topcv_spider -s DOWNLOAD_DELAY=3 -s LOG_LEVEL=DEBUG
```

### Test các modules riêng lẻ

```bash
# Test parser
python src/crawlers/topcv/parser.py

# Test database utils
python src/utils/database.py

# Test config
python -m config

# Test pipelines
python src/crawlers/common/pipelines.py

# Test middlewares
python src/crawlers/common/middlewares.py
```

### Xem dữ liệu trong MongoDB

```bash
# Mở mongo shell
mongosh

# Chọn database
use job_crawler_db

# Xem collections
show collections

# Xem dữ liệu
db.job_postings_raw.find().limit(5).pretty()

# Đếm số jobs
db.job_postings_raw.countDocuments()

# Tìm jobs từ TopCV
db.job_postings_raw.find({source: "topcv"}).limit(5)

# Xem jobs active
db.job_postings_raw.find({"metadata.is_active": true}).limit(5)

# Xem statistics
db.job_postings_raw.aggregate([
  {
    $group: {
      _id: "$source",
      count: { $sum: 1 },
      avg_version: { $avg: "$metadata.version" }
    }
  }
])
```

## 🏗️ Cấu trúc Project

```
job_crawler_system/
├── config/
│   ├── __init__.py          # Settings class & helpers
│   ├── connections.py       # MongoDB connection factory
│   ├── settings.yaml        # Configuration file
│   └── README.md
├── src/
│   ├── crawlers/
│   │   ├── common/
│   │   │   ├── middlewares.py   # Scrapy middlewares
│   │   │   └── pipelines.py     # Scrapy pipelines
│   │   └── topcv/
│   │       ├── __init__.py
│   │       ├── items.py         # JobItem definition
│   │       ├── parser.py        # HTML parsing logic
│   │       └── spider.py        # Scrapy spider
│   ├── utils/
│   │   └── database.py      # MongoDB utilities
│   └── settings.py          # Scrapy settings
├── scrapy.cfg               # Scrapy config
└── requirements.txt
```

## 🧪 Testing

### Test Parser Functions

```python
from src.crawlers.topcv.parser import extract_salary, parse_date

# Test salary extraction
salary = extract_salary("10 - 15 triệu")
print(salary)
# {'raw': '10 - 15 triệu', 'min': 10000000, 'max': 15000000, 'currency': 'VND'}

# Test date parsing
date = parse_date("Hôm nay")
print(date)  # Today's datetime

```

### Test Database Utils

```python
from src.utils.database import create_helper

# Create helper
helper = create_helper()

# Get statistics
stats = helper.get_statistics(source='topcv')
print(stats)

# Count active jobs
count = helper.get_active_jobs_count(source='topcv')
print(f"Active jobs: {count}")
```

## 📊 Pipeline Flow

```
Spider → ValidationPipeline → DuplicatesPipeline → CleaningPipeline → MongoPipeline
   ↓           ↓                    ↓                     ↓                 ↓
Extract    Check         Filter duplicates     Clean text      Upsert to MongoDB
  data    required       in current run        & normalize      with versioning
         fields
```

## 🔧 Troubleshooting

### MongoDB Connection Error
```
Error: Failed to connect to MongoDB
```
**Solution:**
1. Kiểm tra MongoDB đã start: `mongosh`
2. Kiểm tra URI trong `settings.yaml`
3. Test connection: `python -m config.connections`

### Import Errors
```
ModuleNotFoundError: No module named 'scrapy'
```
**Solution:**
```bash
pip install -r requirements.txt
```

### Cloudflare Blocked
```
🚫 Cloudflare challenge detected
```
**Solution:**
1. Tăng DOWNLOAD_DELAY trong settings
2. Enable proxy rotation
3. Consider using Playwright (advanced)

### No items scraped
```
INFO: Closing spider (finished)
INFO: Dumped Scrapy stats: 'item_scraped_count': 0
```
**Solution:**
1. Check CSS selectors trong parser.py
2. Inspect HTML của TopCV (có thể đã thay đổi)
3. Run với DEBUG level: `scrapy crawl topcv_spider -s LOG_LEVEL=DEBUG`

## 🎯 Các bước tiếp theo

### Đã hoàn thành ✅
1. ✅ Items & Parser
2. ✅ Spider với pagination
3. ✅ Pipelines (Validation, Cleaning, MongoDB)
4. ✅ Middlewares (User-Agent, Retry, Proxy)
5. ✅ Database utilities với versioning

### Chưa triển khai ⏳
1. ⏳ Airflow DAGs (orchestration)
2. ⏳ Docker containers
3. ⏳ Playwright integration (Cloudflare bypass)
4. ⏳ Unit tests
5. ⏳ API endpoints để query data

## 📚 Documentation

- [Scrapy Documentation](https://docs.scrapy.org/)
- [MongoDB Python Driver](https://pymongo.readthedocs.io/)
- [Project Architecture Doc](docs/Xây%20Dựng%20Hệ%20Thống%20Crawl%20Dữ%20Liệu%20Job.txt)

## 📝 Notes

### CSS Selectors cần điều chỉnh
CSS selectors trong `parser.py` là dự đoán dựa trên HTML patterns phổ biến. Cần:
1. Inspect HTML thực tế của TopCV
2. Update selectors cho chính xác
3. Test với real data

### Incremental Crawling
Spider hỗ trợ incremental crawling - dừng khi gặp jobs cũ hơn 24h. Có thể customize:
```python
scrapy crawl topcv_spider -a incremental=False  # Disable incremental
```

### User-Agent Rotation
Middleware tự động rotate User-Agent từ list trong config. Có thể thêm nhiều User-Agents hơn trong `settings.yaml`.

## 🤝 Contributing

Khi thêm features mới:
1. Follow code structure hiện tại
2. Add docstrings cho functions
3. Update README
4. Test thoroughly

## 📄 License

Part of Job Crawler System - Smart Recruitment Project
