# Configuration Module

Module cấu hình cho Job Crawler System, cung cấp quản lý tập trung cho toàn bộ hệ thống.

## 📁 Cấu trúc

```
config/
├── __init__.py          # Package initialization & Settings class
├── connections.py       # MongoDB connection factory
├── settings.yaml        # Main configuration file
└── README.md           # Documentation (file này)
```

## 🚀 Sử dụng nhanh

### 1. Load Configuration

```python
from config import load_settings, get_setting

# Load toàn bộ cấu hình
settings = load_settings()

# Lấy một giá trị cụ thể (sử dụng dot notation)
mongo_uri = get_setting('mongodb.uri')
max_pages = get_setting('sources.topcv.max_pages', default=50)
```

### 2. MongoDB Connection

```python
from config import get_mongo_client, get_database, get_collection

# Lấy MongoDB client
client = get_mongo_client()

# Lấy database
db = get_database()

# Lấy collection (sử dụng key từ config)
raw_collection = get_collection('raw_data')  # → job_postings_raw

# Hoặc sử dụng tên collection trực tiếp
custom_collection = get_collection('my_custom_collection')
```

### 3. Setup Logging

```python
from config import setup_logging

# Thiết lập logging dựa trên cấu hình
setup_logging()
```

### 4. Validate Configuration

```python
from config import validate_config

if validate_config():
    print("Configuration is valid")
else:
    print("Configuration has errors")
```

## ⚙️ Cấu hình chi tiết

### settings.yaml

File YAML chứa toàn bộ cấu hình hệ thống, bao gồm:

#### MongoDB Configuration
```yaml
mongodb:
  uri: "mongodb://localhost:27017"
  database: "job_crawler_db"
  collections:
    raw_data: "job_postings_raw"
    history: "job_postings_history"
    logs: "crawler_logs"
  max_pool_size: 100
  min_pool_size: 10
```

#### Scrapy Configuration
```yaml
scrapy:
  concurrent_requests: 16
  download_delay: 2
  retry_times: 3
  user_agents:
    - "Mozilla/5.0 ..."
```

#### Sources Configuration
```yaml
sources:
  topcv:
    enabled: true
    base_url: "https://www.topcv.vn"
    max_pages: 100
```

### Biến môi trường (.env)

Các giá trị trong `settings.yaml` có thể được override bằng biến môi trường:

```bash
# MongoDB
MONGO_URI=mongodb://user:pass@host:27017
MONGO_DATABASE=job_crawler_db

# Application
LOG_LEVEL=DEBUG
DOCKER_NETWORK=job_crawler_network

# Optional
PROXY_SERVERS=http://proxy1:8080,http://proxy2:8080
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

## 🔧 API Reference

### Settings Class

Singleton class quản lý cấu hình hệ thống.

```python
from config import Settings

settings = Settings()

# Lấy giá trị theo đường dẫn
value = settings.get('mongodb.uri', default='localhost')

# Lấy toàn bộ section
mongo_config = settings.get_section('mongodb')

# Lấy toàn bộ cấu hình
all_settings = settings.all()

# Reload configuration
settings.reload()
```

### MongoDB Connection Factory

```python
from config.connections import (
    get_mongo_client,
    get_database,
    get_collection,
    setup_indexes,
    close_connection
)

# Tạo connection
client = get_mongo_client()
db = get_database('custom_db')
collection = get_collection('raw_data')

# Setup indexes (chạy một lần khi khởi tạo)
setup_indexes()

# Đóng connection
close_connection()
```

### Convenience Functions

```python
from config import (
    load_settings,      # Load toàn bộ config
    get_setting,        # Lấy một giá trị cụ thể
    get_section,        # Lấy một section
    setup_logging,      # Thiết lập logging
    validate_config     # Validate config
)
```

## 📊 MongoDB Indexes

Module tự động tạo các indexes theo best practices:

1. **Unique Compound Index**: `(url, source)` - Đảm bảo không trùng lặp
2. **Text Index**: `(title, company)` - Hỗ trợ full-text search
3. **Hashed Index**: `content_hash` - Tối ưu so sánh hash
4. **Time Index**: `crawl_timestamp` - Query theo thời gian
5. **Active Index**: `metadata.is_active` - Filter dữ liệu active
6. **History Index**: `(original_id, version_timestamp)` - Lookup history
7. **TTL Index**: `timestamp` trên logs - Auto-delete sau 30 ngày

Để setup indexes:
```python
from config import setup_indexes

setup_indexes()
```

## 🧪 Testing

Mỗi file có thể được test độc lập:

```bash
# Test __init__.py
python -m config

# Test connections.py
python -m config.connections
```

## 🔐 Best Practices

### 1. Không commit secrets
- Không commit `.env` với thông tin thật
- Sử dụng `.env.example` cho template
- Sử dụng secret management tools (AWS Secrets, Azure Key Vault)

### 2. Override configuration theo môi trường
```python
# Development
MONGO_URI=mongodb://localhost:27017
LOG_LEVEL=DEBUG

# Production
MONGO_URI=mongodb://prod-server:27017
LOG_LEVEL=WARNING
```

### 3. Validate configuration khi khởi động
```python
if __name__ == "__main__":
    from config import validate_config, setup_logging
    
    if not validate_config():
        sys.exit(1)
    
    setup_logging()
    # Start application...
```

### 4. Sử dụng connection pooling
```python
# ✅ Good - Sử dụng global factory
from config import get_collection

collection = get_collection('raw_data')

# ❌ Bad - Tạo connection mới mỗi lần
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017')
```

## 📝 Ví dụ sử dụng trong Crawler

```python
# src/crawlers/topcv/spider.py
from config import get_setting, get_collection
import scrapy

class TopCVSpider(scrapy.Spider):
    name = 'topcv_spider'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load config
        self.max_pages = get_setting('sources.topcv.max_pages', 100)
        self.base_url = get_setting('sources.topcv.base_url')
        
        # Get MongoDB collection
        self.collection = get_collection('raw_data')
    
    def parse(self, response):
        # Crawling logic...
        pass
```

## 🐛 Troubleshooting

### Connection Failed
```
Error: Failed to connect to MongoDB
```
**Solution**: Kiểm tra MongoDB đã chạy và URI đúng
```bash
# Kiểm tra MongoDB service
sudo systemctl status mongodb

# Test connection
python -m config.connections
```

### Configuration Not Found
```
Warning: settings.yaml not found, using default configuration
```
**Solution**: Đảm bảo file `settings.yaml` tồn tại trong thư mục `config/`

### Import Error
```
ModuleNotFoundError: No module named 'pymongo'
```
**Solution**: Cài đặt dependencies
```bash
pip install pymongo pyyaml
```

## 📚 Tham khảo

- [MongoDB Python Driver Documentation](https://pymongo.readthedocs.io/)
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Singleton Pattern](https://refactoring.guru/design-patterns/singleton/python/example)

## 📄 License

Part of Job Crawler System - Smart Recruitment Project
