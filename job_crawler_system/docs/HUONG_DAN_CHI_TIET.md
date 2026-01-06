# HƯỚNG DẪN CHI TIẾT - HỆ THỐNG CRAWL DỮ LIỆU VIỆC LÀM

## 📑 MỤC LỤC

1. [Tổng quan Hệ thống](#1-tổng-quan-hệ-thống)
2. [Cấu trúc Dự án](#2-cấu-trúc-dự-án)
3. [Config Module - Quản lý Cấu hình](#3-config-module---quản-lý-cấu-hình)
4. [Database Utilities - Xử lý Dữ liệu MongoDB](#4-database-utilities---xử-lý-dữ-liệu-mongodb)
5. [Items Module - Định nghĩa Cấu trúc Dữ liệu](#5-items-module---định-nghĩa-cấu-trúc-dữ-liệu)
6. [Parser Module - Trích xuất Dữ liệu HTML](#6-parser-module---trích-xuất-dữ-liệu-html)
7. [Spider Module - Thu thập Dữ liệu](#7-spider-module---thu-thập-dữ-liệu)
8. [Pipelines Module - Xử lý Item](#8-pipelines-module---xử-lý-item)
9. [Middlewares Module - Tăng cường Spider](#9-middlewares-module---tăng-cường-spider)
10. [Scrapy Settings - Cấu hình Scrapy](#10-scrapy-settings---cấu-hình-scrapy)
11. [Hướng dẫn Sử dụng](#11-hướng-dẫn-sử-dụng)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Mục đích
Hệ thống thu thập tự động dữ liệu việc làm từ TopCV.vn và các trang tuyển dụng khác, lưu trữ vào MongoDB với khả năng:
- **Incremental Crawling**: Chỉ thu thập dữ liệu mới
- **Document Versioning**: Theo dõi lịch sử thay đổi
- **Content Deduplication**: Loại bỏ trùng lặp
- **Automated Pipeline**: Xử lý và làm sạch dữ liệu tự động

### 1.2 Công nghệ Sử dụng
- **Scrapy 2.11+**: Framework web crawling
- **MongoDB 4.x+**: Database lưu trữ
- **PyMongo 4.6+**: MongoDB driver
- **BeautifulSoup4**: HTML parsing bổ sung
- **Python 3.8+**: Programming language

### 1.3 Kiến trúc Hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                     JOB CRAWLER SYSTEM                      │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌──────────┐       ┌──────────┐      ┌──────────┐
    │ Config   │       │ Scrapy   │      │ MongoDB  │
    │ Module   │       │ Engine   │      │ Database │
    └──────────┘       └──────────┘      └──────────┘
           │                  │                  │
           │                  ▼                  │
           │           ┌──────────┐              │
           │           │  Spider  │              │
           │           │ (TopCV)  │              │
           │           └──────────┘              │
           │                  │                  │
           │                  ▼                  │
           │           ┌──────────┐              │
           │           │ Parser   │              │
           │           │ Module   │              │
           │           └──────────┘              │
           │                  │                  │
           │                  ▼                  │
           │           ┌──────────┐              │
           │           │Pipelines │              │
           │           │ Module   │              │
           │           └──────────┘              │
           │                  │                  │
           └──────────────────┼──────────────────┘
                              ▼
                    ┌──────────────────┐
                    │ Database Utils   │
                    │ (Upsert/Version) │
                    └──────────────────┘
```

---

## 2. CẤU TRÚC DỰ ÁN

```
job_crawler_system/
│
├── config/                          # Module quản lý cấu hình
│   ├── __init__.py                 # Config loader functions
│   ├── connections.py              # MongoDB connection factory
│   ├── settings.yaml               # File cấu hình chính
│   └── README.md                   # Hướng dẫn config
│
├── src/                            # Source code chính
│   ├── crawlers/                   # Scrapy crawlers
│   │   ├── settings.py            # Scrapy settings
│   │   ├── common/                # Components dùng chung
│   │   │   ├── pipelines.py      # Item pipelines
│   │   │   └── middlewares.py    # Downloader middlewares
│   │   │
│   │   └── topcv/                 # TopCV spider
│   │       ├── spider.py          # Spider implementation
│   │       ├── parser.py          # HTML parser functions
│   │       └── items.py           # Item definitions
│   │
│   └── utils/                      # Utility modules
│       └── database.py             # MongoDB utilities
│
├── dags/                           # Airflow DAGs (tương lai)
│   ├── job_crawler_dag.py
│   └── maintenance_dag.py
│
├── docker/                         # Docker configurations
│   ├── airflow/Dockerfile
│   └── scraper/Dockerfile
│
├── logs/                           # Log files
│
├── scrapy.cfg                      # Scrapy project config
├── requirements.txt                # Python dependencies
├── docker-compose.yaml             # Docker compose (tương lai)
└── README.md                       # Hướng dẫn chung
```

---

## 3. CONFIG MODULE - QUẢN LÝ CẤU HÌNH

### 3.1 File: `config/__init__.py`

**Mục đích**: Cung cấp các hàm tiện ích để đọc cấu hình từ `settings.yaml`

#### 3.1.1 Các Functions

##### `load_config() -> dict`
Load toàn bộ file `settings.yaml` thành dictionary.

```python
from config import load_config

config = load_config()
print(config['mongodb']['uri'])  # mongodb://localhost:27017
```

##### `get_setting(key_path: str, default=None) -> Any`
Lấy giá trị cấu hình theo đường dẫn dot-notation.

```python
from config import get_setting

# Lấy MongoDB URI
mongo_uri = get_setting('mongodb.uri')

# Lấy với default value
delay = get_setting('scrapy.download_delay', default=2)

# Lấy nested values
user_agents = get_setting('scrapy.user_agents', default=[])
```

**Key paths thường dùng**:
- `mongodb.uri` - MongoDB connection string
- `mongodb.database` - Database name
- `mongodb.collections.raw_data` - Raw data collection name
- `scrapy.download_delay` - Delay giữa requests (giây)
- `scrapy.concurrent_requests` - Số requests đồng thời
- `sources.topcv.enabled` - Bật/tắt TopCV spider

##### `get_section(section_name: str) -> dict`
Lấy toàn bộ một section trong config.

```python
from config import get_section

# Lấy toàn bộ config MongoDB
mongodb_config = get_section('mongodb')
print(mongodb_config['uri'])
print(mongodb_config['database'])

# Lấy config Scrapy
scrapy_config = get_section('scrapy')
```

#### 3.1.2 Ví dụ Sử dụng Thực tế

```python
# File: src/crawlers/topcv/spider.py
from config import get_setting

class TopCVSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load config
        self.max_pages = get_setting('sources.topcv.max_pages', default=10)
        self.download_delay = get_setting('scrapy.download_delay', default=2)
        
        logger.info(f"Spider initialized with max_pages={self.max_pages}")
```

---

### 3.2 File: `config/connections.py`

**Mục đích**: Factory pattern để tạo và quản lý MongoDB connections với Singleton pattern.

#### 3.2.1 Class: `MongoDBConnectionFactory`

**Design Pattern**: Singleton - đảm bảo chỉ có một connection pool duy nhất.

##### Attributes
- `_instance`: Singleton instance
- `_client`: MongoDB client instance (connection pool)
- `_config`: Dictionary chứa config từ settings.yaml

##### Methods

**`get_client() -> MongoClient`**
Tạo hoặc trả về MongoDB client.

```python
from config.connections import get_mongo_client

client = get_mongo_client()
# Client sử dụng connection pool, thread-safe
```

**Features**:
- Tự động đọc config từ `settings.yaml`
- Ưu tiên biến môi trường `MONGO_URI` (cho Docker)
- Connection pool với max_pool_size=100
- Auto retry on failures
- Connection health check (ping test)

**`get_database(db_name: Optional[str] = None) -> Database`**
Lấy MongoDB database instance.

```python
from config.connections import get_database

# Sử dụng database từ config
db = get_database()

# Hoặc chỉ định database cụ thể
test_db = get_database('test_crawler_db')
```

**`get_collection(collection_name: str, db_name: Optional[str] = None) -> Collection`**
Lấy MongoDB collection instance.

```python
from config.connections import get_collection

# Sử dụng key từ config (raw_data -> job_postings_raw)
raw_coll = get_collection('raw_data')

# Sử dụng tên collection trực tiếp
custom_coll = get_collection('my_custom_collection')

# Chỉ định database khác
other_coll = get_collection('raw_data', db_name='other_db')
```

**Mapping trong config**:
```yaml
mongodb:
  collections:
    raw_data: "job_postings_raw"      # Key -> Actual name
    history: "job_postings_history"
    logs: "crawler_logs"
```

**`setup_indexes() -> None`**
Thiết lập indexes cho collections (chạy một lần khi setup).

```python
from config.connections import setup_indexes

# Tạo các indexes cần thiết
setup_indexes()
```

**Indexes được tạo**:
1. **Unique compound index** trên `(url, source)` - đảm bảo không trùng lặp job
2. **Text index** trên `title` và `company` - hỗ trợ full-text search
3. **Hash index** trên `content_hash` - tìm kiếm nhanh theo hash
4. **Index** trên `crawl_timestamp` - query theo thời gian
5. **TTL index** trên logs collection - tự động xóa logs cũ

**`close_connection() -> None`**
Đóng MongoDB connection (gọi khi shutdown).

```python
from config.connections import close_connection

# Cleanup khi tắt ứng dụng
close_connection()
```

#### 3.2.2 Ví dụ Sử dụng

```python
# --- Example 1: Basic Usage ---
from config.connections import get_collection

# Lấy collection để insert data
raw_collection = get_collection('raw_data')

# Insert job posting
job_doc = {
    'url': 'https://topcv.vn/job-12345',
    'title': 'Python Developer',
    'company': 'Tech Corp',
    'source': 'topcv'
}
raw_collection.insert_one(job_doc)

# --- Example 2: Query với Index ---
# Tìm job theo URL và source (sử dụng unique compound index)
job = raw_collection.find_one({
    'url': 'https://topcv.vn/job-12345',
    'source': 'topcv'
})

# Full-text search (sử dụng text index)
results = raw_collection.find({
    '$text': {'$search': 'python developer'}
})

# --- Example 3: Setup Indexes (chỉ chạy 1 lần) ---
from config.connections import setup_indexes

setup_indexes()
print("Indexes created successfully!")
```

---

### 3.3 File: `config/settings.yaml`

**Mục đích**: File cấu hình tập trung cho toàn bộ hệ thống.

#### 3.3.1 Cấu trúc và Giải thích

##### MongoDB Configuration
```yaml
mongodb:
  uri: "mongodb://localhost:27017"  # Connection string
  database: "job_crawler_db"        # Database name
  
  collections:                      # Collection name mapping
    raw_data: "job_postings_raw"   # Key: raw_data -> Name: job_postings_raw
    history: "job_postings_history"
    logs: "crawler_logs"
  
  # Connection Pool Settings
  max_pool_size: 100                # Số connections tối đa
  min_pool_size: 10                 # Số connections tối thiểu
  connection_timeout_ms: 5000       # Timeout khi connect (5s)
  server_selection_timeout_ms: 5000 # Timeout khi chọn server (5s)
```

**Lưu ý**:
- URI có thể override bằng biến môi trường `MONGO_URI`
- Database có thể override bằng `MONGO_DATABASE`
- Connection pool settings quan trọng cho production

##### Scrapy Configuration
```yaml
scrapy:
  # General Settings
  concurrent_requests: 16           # Tổng requests đồng thời
  concurrent_requests_per_domain: 8 # Requests/domain
  download_delay: 2                 # Delay giữa requests (giây)
  download_timeout: 30              # Timeout cho mỗi request
  
  # Retry Settings
  retry_enabled: true
  retry_times: 3                    # Số lần retry
  retry_http_codes:                 # HTTP codes cần retry
    - 500  # Internal Server Error
    - 502  # Bad Gateway
    - 503  # Service Unavailable
    - 504  # Gateway Timeout
    - 408  # Request Timeout
    - 429  # Too Many Requests
  
  # User Agent Rotation
  user_agents:                      # Danh sách User-Agent headers
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"
    # ... thêm nhiều user agents
  
  # AutoThrottle (Tự động điều chỉnh tốc độ)
  autothrottle_enabled: true
  autothrottle_start_delay: 1       # Delay ban đầu (giây)
  autothrottle_max_delay: 10        # Delay tối đa (giây)
  autothrottle_target_concurrency: 2.0  # Target concurrent requests/server
```

**Giải thích AutoThrottle**:
- AutoThrottle tự động điều chỉnh `download_delay` dựa trên server response
- Nếu server phản hồi chậm → tăng delay
- Nếu server phản hồi nhanh → giảm delay
- Giúp tránh overload server và bị ban

##### Proxy Configuration
```yaml
proxy:
  enabled: false                    # Bật/tắt proxy rotation
  type: "http"                      # http, https, socks5
  rotation_enabled: true            # Xoay vòng proxy
  servers: []                       # Danh sách proxy servers
    # - "http://proxy1.example.com:8080"
    # - "http://proxy2.example.com:8080"
```

**Khi nào cần proxy**:
- Crawl với volume lớn
- Tránh IP bị ban
- Bypass geo-restrictions
- Testing từ nhiều locations

##### Data Validation
```yaml
data_validation:
  # Minimum required fields
  required_fields:
    - url       # Bắt buộc
    - title     # Khuyến nghị
    - company   # Khuyến nghị
    - source    # Bắt buộc
  
  # Content Hash Algorithm
  hash_algorithm: "sha256"  # md5 hoặc sha256
  
  # Duplicate Detection
  check_duplicates: true
  duplicate_threshold_hours: 24  # Chỉ check trong 24h gần nhất
```

##### Sources Configuration
```yaml
sources:
  topcv:
    enabled: true
    name: "TopCV"
    base_url: "https://www.topcv.vn"
    start_urls:
      - "https://www.topcv.vn/tim-viec-lam-moi-nhat"
    
    # Custom settings cho TopCV
    custom_settings:
      download_delay: 3           # TopCV cần delay cao hơn
      concurrent_requests: 8
      max_pages: 100              # Giới hạn số trang
```

**Thêm source mới**:
```yaml
  vietnamworks:
    enabled: true
    name: "VietnamWorks"
    base_url: "https://www.vietnamworks.com"
    start_urls:
      - "https://www.vietnamworks.com/tim-viec-lam"
    custom_settings:
      download_delay: 2
      concurrent_requests: 10
```

##### Feature Flags
```yaml
features:
  incremental_crawling: true     # Chỉ crawl dữ liệu mới
  document_versioning: true      # Lưu lịch sử thay đổi
  content_deduplication: true    # Loại bỏ trùng lặp
  auto_field_extraction: true    # Tự động trích xuất (NLP)
```

#### 3.3.2 Override Configuration

**Cách 1: Environment Variables**
```bash
# Set environment variables
export MONGO_URI="mongodb://prod-server:27017"
export MONGO_DATABASE="production_db"
export LOG_LEVEL="DEBUG"

# Run spider
scrapy crawl topcv_spider
```

**Cách 2: Command Line Arguments**
```bash
# Override Scrapy settings
scrapy crawl topcv_spider \
    -s DOWNLOAD_DELAY=5 \
    -s CONCURRENT_REQUESTS=4 \
    -s LOG_LEVEL=DEBUG
```

**Cách 3: Custom Settings trong Spider**
```python
class TopCVSpider(scrapy.Spider):
    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS': 8,
    }
```

**Priority** (thấp đến cao):
1. Default values trong code
2. `settings.yaml`
3. Environment variables
4. Spider custom_settings
5. Command line arguments

---

## 4. DATABASE UTILITIES - XỬ LÝ DỮ LIỆU MONGODB

### 4.1 File: `src/utils/database.py`

**Mục đích**: Cung cấp các functions và helper class để tương tác với MongoDB, bao gồm content hashing, document versioning, và upsert logic.

#### 4.1.1 Function: `calculate_content_hash()`

**Signature**:
```python
def calculate_content_hash(
    content: Dict[str, Any],
    fields: Optional[list] = None,
    algorithm: str = 'sha256'
) -> str
```

**Mục đích**: Tính toán hash của content để phát hiện thay đổi.

**Parameters**:
- `content`: Dictionary chứa dữ liệu job posting
- `fields`: List các fields cần hash (None = hash toàn bộ)
- `algorithm`: Thuật toán hash ('md5' hoặc 'sha256')

**Returns**: String hash dạng hexadecimal

**Cách hoạt động**:
1. Lấy các fields cần hash từ content
2. Sắp xếp theo key (để đảm bảo consistent)
3. Chuyển thành string
4. Tính hash bằng MD5 hoặc SHA256

**Ví dụ**:
```python
from src.utils.database import calculate_content_hash

# Hash toàn bộ content
job_data = {
    'title': 'Python Developer',
    'company': 'ABC Corp',
    'salary_raw': '10-15 triệu',
    'description': 'Looking for Python dev...'
}

hash1 = calculate_content_hash(job_data)
print(hash1)  # 'e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0...'

# Hash chỉ một số fields quan trọng
hash2 = calculate_content_hash(
    job_data,
    fields=['title', 'company', 'salary_raw', 'description']
)

# Kiểm tra thay đổi
job_data_modified = job_data.copy()
job_data_modified['description'] = 'Updated description'

hash3 = calculate_content_hash(
    job_data_modified,
    fields=['title', 'company', 'salary_raw', 'description']
)

print(hash2 == hash3)  # False - content đã thay đổi
```

**Use cases**:
- Detect khi job posting được cập nhật (title, salary thay đổi)
- Tránh lưu trùng lặp (nếu hash giống nhau = content giống nhau)
- Trigger versioning khi content thay đổi

---

#### 4.1.2 Function: `is_content_changed()`

**Signature**:
```python
def is_content_changed(
    old_doc: Dict[str, Any],
    new_content: Dict[str, Any],
    hash_fields: Optional[list] = None
) -> bool
```

**Mục đích**: So sánh hash của document cũ và mới để xác định có thay đổi không.

**Ví dụ**:
```python
from src.utils.database import is_content_changed

# Document hiện tại trong DB
old_doc = {
    '_id': ObjectId('...'),
    'url': 'https://topcv.vn/job-123',
    'title': 'Python Developer',
    'content_hash': 'abc123...',
    'raw_data': {...}
}

# Content mới từ crawl
new_content = {
    'title': 'Senior Python Developer',  # Changed!
    'company': 'ABC Corp',
    'salary_raw': '15-20 triệu'  # Changed!
}

# Check if changed
if is_content_changed(old_doc, new_content):
    print("Content has changed - need to update!")
    # Trigger versioning và update
else:
    print("Content unchanged - only update last_seen_timestamp")
```

---

#### 4.1.3 Function: `archive_to_history()`

**Signature**:
```python
def archive_to_history(
    history_collection: Collection,
    original_doc: Dict[str, Any]
) -> Optional[ObjectId]
```

**Mục đích**: Lưu trữ version cũ của document vào history collection trước khi update.

**Quy trình**:
1. Copy toàn bộ document gốc
2. Lưu `original_id` (reference tới document gốc)
3. Xóa `_id` (MongoDB sẽ tạo _id mới cho history)
4. Thêm metadata: `version_timestamp`, `archived_at`
5. Insert vào history collection

**Ví dụ**:
```python
from config.connections import get_collection
from src.utils.database import archive_to_history

raw_coll = get_collection('raw_data')
history_coll = get_collection('history')

# Lấy document hiện tại
current_doc = raw_coll.find_one({'url': 'https://topcv.vn/job-123'})

# Lưu vào history trước khi update
history_id = archive_to_history(history_coll, current_doc)

print(f"Archived to history with ID: {history_id}")

# Giờ có thể update document gốc
raw_coll.update_one(
    {'_id': current_doc['_id']},
    {'$set': {'title': 'New Title', 'version': 2}}
)
```

**History document structure**:
```json
{
    "_id": "674a5b8c9d...",           // ID mới của history
    "original_id": "674a1234ab...",   // ID của document gốc
    "url": "https://topcv.vn/job-123",
    "title": "Python Developer",       // Old title
    "salary_raw": "10-15 triệu",      // Old salary
    "version": 1,                      // Old version
    "version_timestamp": "2025-11-20T10:30:00Z",
    "archived_at": "2025-11-24T14:20:00Z"
}
```

**Query history**:
```python
# Xem lịch sử thay đổi của một job
history_docs = history_coll.find({
    'original_id': ObjectId('674a1234ab...')
}).sort('archived_at', -1)

for doc in history_docs:
    print(f"Version {doc['version']} - {doc['archived_at']}")
    print(f"  Title: {doc['title']}")
    print(f"  Salary: {doc['salary_raw']}")
```

---

#### 4.1.4 Function: `upsert_job_posting()`

**Signature**:
```python
def upsert_job_posting(
    raw_collection: Collection,
    history_collection: Collection,
    job_item: Dict[str, Any],
    hash_fields: Optional[list] = None,
    enable_versioning: bool = True
) -> Tuple[bool, Optional[ObjectId], str]
```

**Mục đích**: Insert hoặc update job posting với document versioning - **Core function** của hệ thống.

**Returns**: Tuple `(is_new, document_id, status)`
- `is_new`: `True` nếu là document mới, `False` nếu đã tồn tại
- `document_id`: ObjectId của document
- `status`: `'inserted'`, `'updated'`, hoặc `'unchanged'`

**Quy trình hoạt động**:

```
┌─────────────────────────────────────────┐
│ START: upsert_job_posting               │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 1. Tính content_hash cho job_item mới  │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 2. Tìm document theo (url, source)     │
└─────────────────────────────────────────┘
                  │
         ┌────────┴────────┐
         ▼                 ▼
    [NOT FOUND]       [FOUND]
         │                 │
         ▼                 ▼
┌──────────────┐    ┌─────────────────┐
│ CASE 1: NEW  │    │ CASE 2: EXISTS  │
└──────────────┘    └─────────────────┘
         │                 │
         ▼                 ▼
   Insert new       Compare hashes
   document              │
         │          ┌────┴────┐
         │          ▼         ▼
         │      [CHANGED] [UNCHANGED]
         │          │         │
         │          ▼         ▼
         │     Archive old  Update only
         │     version     last_seen
         │     to history    │
         │          │         │
         │     Update doc    │
         │     version++     │
         │          │         │
         └──────────┴─────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ RETURN (is_new, doc_id, status)        │
└─────────────────────────────────────────┘
```

**Ví dụ chi tiết**:

**Case 1: Document mới (chưa tồn tại)**
```python
from config.connections import get_collection
from src.utils.database import upsert_job_posting

raw_coll = get_collection('raw_data')
history_coll = get_collection('history')

# Job item mới từ crawler
new_job = {
    'url': 'https://topcv.vn/job-999',
    'source': 'topcv',
    'title': 'Python Developer',
    'company': 'Tech Corp',
    'salary_raw': '10-15 triệu',
    'raw_data': {
        'title': 'Python Developer',
        'company': 'Tech Corp',
        'description': 'Looking for Python dev...'
    }
}

# Upsert
is_new, doc_id, status = upsert_job_posting(
    raw_coll, history_coll, new_job
)

print(is_new)   # True
print(status)   # 'inserted'
print(doc_id)   # ObjectId('674a...')

# Document trong DB:
{
    '_id': ObjectId('674a...'),
    'url': 'https://topcv.vn/job-999',
    'source': 'topcv',
    'title': 'Python Developer',
    'content_hash': 'abc123...',
    'crawl_timestamp': datetime(2025, 11, 24, 10, 0, 0),
    'last_seen_timestamp': datetime(2025, 11, 24, 10, 0, 0),
    'metadata': {
        'version': 1,
        'is_active': True,
        'created_at': datetime(2025, 11, 24, 10, 0, 0),
        'updated_at': datetime(2025, 11, 24, 10, 0, 0)
    },
    'raw_data': {...}
}
```

**Case 2a: Document đã tồn tại - Content thay đổi**
```python
# Crawl lại sau 1 ngày - job đã cập nhật
updated_job = {
    'url': 'https://topcv.vn/job-999',  # Same URL
    'source': 'topcv',
    'title': 'Senior Python Developer',  # Changed!
    'company': 'Tech Corp',
    'salary_raw': '15-20 triệu',  # Changed!
    'raw_data': {
        'title': 'Senior Python Developer',
        'company': 'Tech Corp',
        'description': 'Updated description...'
    }
}

# Upsert again
is_new, doc_id, status = upsert_job_posting(
    raw_coll, history_coll, updated_job
)

print(is_new)   # False (đã tồn tại)
print(status)   # 'updated'
print(doc_id)   # ObjectId('674a...') - Same ID

# Quy trình:
# 1. Old version archived to history
# 2. Document updated với new content
# 3. Version incremented: 1 -> 2
```

**Case 2b: Document đã tồn tại - Content không đổi**
```python
# Crawl lại - job không thay đổi
same_job = {
    'url': 'https://topcv.vn/job-999',
    'source': 'topcv',
    'title': 'Senior Python Developer',  # Same
    'company': 'Tech Corp',              # Same
    'salary_raw': '15-20 triệu',         # Same
    'raw_data': {...}                    # Same content
}

# Upsert
is_new, doc_id, status = upsert_job_posting(
    raw_coll, history_coll, same_job
)

print(is_new)   # False
print(status)   # 'unchanged'

# Chỉ update last_seen_timestamp
# Không tạo history, không tăng version
```

**Hash fields configuration**:
```python
# Default hash fields (nếu không chỉ định)
hash_fields = ['title', 'company', 'salary_raw', 'description', 'requirements']

# Custom hash fields
is_new, doc_id, status = upsert_job_posting(
    raw_coll, history_coll, job_item,
    hash_fields=['title', 'salary_raw'],  # Chỉ check 2 fields này
    enable_versioning=True
)

# Disable versioning (không lưu history)
is_new, doc_id, status = upsert_job_posting(
    raw_coll, history_coll, job_item,
    enable_versioning=False  # Không archive old versions
)
```

---

#### 4.1.5 Class: `MongoDBHelper`

**Mục đích**: Helper class cung cấp high-level interface để thao tác với MongoDB.

**Constructor**:
```python
def __init__(
    self,
    raw_collection: Collection,
    history_collection: Collection,
    enable_versioning: bool = True
)
```

**Methods**:

##### `upsert_job(job_item, hash_fields=None)`
Wrapper cho `upsert_job_posting()`.

```python
from config.connections import get_collection
from src.utils.database import MongoDBHelper

# Initialize helper
helper = MongoDBHelper(
    raw_collection=get_collection('raw_data'),
    history_collection=get_collection('history'),
    enable_versioning=True
)

# Upsert job
job_item = {...}
is_new, doc_id, status = helper.upsert_job(job_item)

if status == 'inserted':
    print(f"New job added: {doc_id}")
elif status == 'updated':
    print(f"Job updated: {doc_id}")
else:
    print(f"Job unchanged: {doc_id}")
```

##### `get_job(url, source)`
Lấy job posting theo URL và source.

```python
job = helper.get_job(
    url='https://topcv.vn/job-123',
    source='topcv'
)

if job:
    print(f"Found job: {job['title']}")
else:
    print("Job not found")
```

##### `mark_as_inactive(url, source)`
Đánh dấu job là inactive (không còn tồn tại trên website).

```python
# Khi crawl lại và không thấy job này nữa
success = helper.mark_as_inactive(
    url='https://topcv.vn/job-old',
    source='topcv'
)

# Document được update:
{
    'metadata': {
        'is_active': False,
        'deactivated_at': datetime(2025, 11, 24, 15, 0, 0)
    }
}
```

##### `get_active_jobs_count(source=None)`
Đếm số lượng jobs đang active.

```python
# Đếm tất cả jobs active
total = helper.get_active_jobs_count()
print(f"Total active jobs: {total}")

# Đếm theo source
topcv_count = helper.get_active_jobs_count(source='topcv')
print(f"TopCV active jobs: {topcv_count}")
```

##### `get_statistics()`
Lấy thống kê chi tiết về dữ liệu.

```python
stats = helper.get_statistics()

print(stats)
# {
#     'total_jobs': 5000,
#     'active_jobs': 4800,
#     'inactive_jobs': 200,
#     'by_source': {
#         'topcv': 3000,
#         'vietnamworks': 2000
#     },
#     'total_versions': 12000,  # From history
#     'avg_versions_per_job': 2.4
# }
```

##### `create_helper()` - Factory Function
Convenience function để tạo helper instance.

```python
from src.utils.database import create_helper

# Tự động load collections từ config
helper = create_helper(
    raw_collection_name='raw_data',
    history_collection_name='history',
    enable_versioning=True
)

# Giờ có thể dùng helper
helper.upsert_job(job_item)
```

---

### 4.2 Ví dụ Sử dụng Thực tế

#### Example 1: Basic Upsert Flow
```python
from config.connections import get_collection
from src.utils.database import upsert_job_posting

# Setup
raw_coll = get_collection('raw_data')
history_coll = get_collection('history')

# Job từ crawler
job_item = {
    'url': 'https://topcv.vn/job-12345',
    'source': 'topcv',
    'title': 'Python Developer',
    'company': 'ABC Tech',
    'salary_raw': '10-15 triệu',
    'location': 'Hà Nội',
    'raw_data': {
        'title': 'Python Developer',
        'company': 'ABC Tech',
        'description': 'Full job description...',
        'requirements': 'Python, Django, MySQL...',
        'benefits': 'Salary, insurance...'
    }
}

# Upsert
is_new, doc_id, status = upsert_job_posting(
    raw_coll, history_coll, job_item
)

print(f"Status: {status}")
if is_new:
    print(f"New job inserted with ID: {doc_id}")
else:
    if status == 'updated':
        print(f"Job updated: {doc_id}")
    else:
        print(f"Job unchanged: {doc_id}")
```

#### Example 2: Batch Processing với Helper
```python
from src.utils.database import create_helper

# Initialize helper
helper = create_helper()

# Batch crawl results
crawled_jobs = [
    {'url': 'https://topcv.vn/job-1', 'source': 'topcv', ...},
    {'url': 'https://topcv.vn/job-2', 'source': 'topcv', ...},
    # ... nhiều jobs
]

# Statistics
stats = {'inserted': 0, 'updated': 0, 'unchanged': 0}

for job in crawled_jobs:
    is_new, doc_id, status = helper.upsert_job(job)
    stats[status] += 1

print(f"Crawl results: {stats}")
# {'inserted': 50, 'updated': 20, 'unchanged': 30}
```

#### Example 3: Query và Analysis
```python
from config.connections import get_collection
from datetime import datetime, timedelta

raw_coll = get_collection('raw_data')

# Query 1: Jobs crawled trong 24h qua
last_24h = datetime.utcnow() - timedelta(hours=24)
recent_jobs = raw_coll.find({
    'crawl_timestamp': {'$gte': last_24h}
})

print(f"Jobs crawled in last 24h: {recent_jobs.count()}")

# Query 2: Jobs được update (version > 1)
updated_jobs = raw_coll.find({
    'metadata.version': {'$gt': 1}
})

print(f"Jobs that were updated: {updated_jobs.count()}")

# Query 3: Jobs với salary cao
high_salary_jobs = raw_coll.find({
    'raw_data.salary_min': {'$gte': 20000000}  # >= 20 triệu
})

# Query 4: Full-text search
search_results = raw_coll.find({
    '$text': {'$search': 'python django mongodb'}
})

for job in search_results:
    print(f"{job['title']} at {job['company']}")
```

#### Example 4: History Tracking
```python
from config.connections import get_collection
from bson import ObjectId

history_coll = get_collection('history')

# Xem lịch sử thay đổi của một job
job_id = ObjectId('674a1234...')

history_docs = history_coll.find({
    'original_id': job_id
}).sort('archived_at', -1)  # Newest first

print(f"History for job {job_id}:")
for i, doc in enumerate(history_docs, 1):
    print(f"\nVersion {doc['metadata']['version']}:")
    print(f"  Archived: {doc['archived_at']}")
    print(f"  Title: {doc['title']}")
    print(f"  Salary: {doc['salary_raw']}")
    print(f"  Location: {doc['location']}")
```

---

[Tiếp tục phần 5-12...]
