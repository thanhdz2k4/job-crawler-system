# HƯỚNG DẪN CHI TIẾT - PHẦN 4 (CUỐI)

## 9. MIDDLEWARES MODULE - TĂNG CƯỜNG SPIDER

### 9.1 File: `src/crawlers/common/middlewares.py`

**Mục đích**: Downloader middlewares để tăng cường khả năng crawling.

**Middleware Types**:
1. **UserAgentRotationMiddleware**: Rotate User-Agent headers
2. **ProxyRotationMiddleware**: Rotate proxies (optional)
3. **CustomRetryMiddleware**: Enhanced retry logic
4. **CloudflareBypassMiddleware**: Handle Cloudflare challenges

---

### 9.2 Class: `UserAgentRotationMiddleware`

**Mục đích**: Rotate User-Agent headers để tránh bị detect là bot.

#### 9.2.1 Initialization

```python
class UserAgentRotationMiddleware:
    """Middleware để rotate User-Agent headers."""
    
    def __init__(self, user_agents: List[str]):
        self.user_agents = user_agents
        
        if not self.user_agents:
            raise NotConfigured("No user agents provided")
        
        self.stats = {
            'requests': 0,
            'user_agents_used': {}
        }
        
        logger.info(
            f"UserAgentRotationMiddleware initialized with "
            f"{len(self.user_agents)} user agents"
        )
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        # Try to load from config module
        try:
            from config import get_setting
            user_agents = get_setting('scrapy.user_agents', [])
        except:
            # Fallback to Scrapy settings
            user_agents = crawler.settings.getlist('USER_AGENTS', [])
        
        # Default user agents nếu không có trong config
        if not user_agents:
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Firefox/121.0',
            ]
        
        middleware = cls(user_agents=user_agents)
        
        # Connect to spider_closed signal
        crawler.signals.connect(
            middleware.spider_closed, 
            signal=signals.spider_closed
        )
        
        return middleware
```

#### 9.2.2 Request Processing

```python
def process_request(self, request: Request, spider):
    """Process request: Add random User-Agent header."""
    
    # Select random User-Agent
    user_agent = random.choice(self.user_agents)
    request.headers['User-Agent'] = user_agent
    
    # Update stats
    self.stats['requests'] += 1
    self.stats['user_agents_used'][user_agent] = \
        self.stats['user_agents_used'].get(user_agent, 0) + 1
    
    logger.debug(f"Using User-Agent: {user_agent[:50]}...")
```

#### 9.2.3 Statistics

```python
def spider_closed(self, spider):
    """Log statistics when spider closes."""
    logger.info(
        f"UserAgentRotationMiddleware stats: "
        f"total_requests={self.stats['requests']}, "
        f"unique_user_agents={len(self.stats['user_agents_used'])}"
    )
```

**Example Output**:
```
UserAgentRotationMiddleware stats: total_requests=1500, unique_user_agents=4
```

---

### 9.3 Class: `ProxyRotationMiddleware`

**Mục đích**: Rotate proxies để tránh IP bị ban.

```python
class ProxyRotationMiddleware:
    """Middleware để rotate proxies."""
    
    def __init__(self, proxies: List[str], enabled: bool = False):
        self.proxies = proxies
        self.enabled = enabled
        
        if not self.enabled:
            raise NotConfigured("ProxyRotationMiddleware is disabled")
        
        if not self.proxies:
            raise NotConfigured("No proxies provided")
        
        self.stats = {
            'requests': 0,
            'proxies_used': {},
            'proxy_errors': 0
        }
        
        logger.info(
            f"ProxyRotationMiddleware initialized with "
            f"{len(self.proxies)} proxies"
        )
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        try:
            from config import get_setting
            
            enabled = get_setting('proxy.enabled', False)
            proxies = get_setting('proxy.servers', [])
        except:
            enabled = crawler.settings.get('PROXY_ENABLED', False)
            proxies = crawler.settings.getlist('PROXY_SERVERS', [])
        
        return cls(proxies=proxies, enabled=enabled)
    
    def process_request(self, request: Request, spider):
        """Add random proxy to request."""
        
        # Select random proxy
        proxy = random.choice(self.proxies)
        request.meta['proxy'] = proxy
        
        # Update stats
        self.stats['requests'] += 1
        self.stats['proxies_used'][proxy] = \
            self.stats['proxies_used'].get(proxy, 0) + 1
        
        logger.debug(f"Using proxy: {proxy}")
    
    def process_exception(self, request, exception, spider):
        """Handle proxy errors."""
        
        if 'proxy' in request.meta:
            proxy = request.meta['proxy']
            logger.warning(f"Proxy error with {proxy}: {exception}")
            self.stats['proxy_errors'] += 1
            
            # Retry with different proxy
            new_proxy = random.choice(self.proxies)
            request.meta['proxy'] = new_proxy
            
            return request
```

**Configuration**:
```yaml
# config/settings.yaml
proxy:
  enabled: true
  type: "http"
  servers:
    - "http://proxy1.example.com:8080"
    - "http://proxy2.example.com:8080"
    - "http://proxy3.example.com:8080"
```

**Enable trong settings**:
```python
# src/crawlers/settings.py
DOWNLOADER_MIDDLEWARES = {
    'src.crawlers.common.middlewares.ProxyRotationMiddleware': 410,
}
```

---

### 9.4 Class: `CustomRetryMiddleware`

**Mục đích**: Enhanced retry logic với custom HTTP codes.

```python
class CustomRetryMiddleware(BaseRetryMiddleware):
    """Custom retry middleware với enhanced logic."""
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # Load retry settings
        self.max_retry_times = settings.getint('RETRY_TIMES', 3)
        self.retry_http_codes = set(
            int(x) for x in settings.getlist('RETRY_HTTP_CODES')
        )
        
        # Custom: exponential backoff
        self.use_exponential_backoff = True
        self.base_delay = 5  # seconds
        
        logger.info(
            f"CustomRetryMiddleware initialized: "
            f"max_retry={self.max_retry_times}, "
            f"retry_codes={self.retry_http_codes}"
        )
    
    def process_response(self, request, response, spider):
        """Process response - retry if needed."""
        
        if response.status in self.retry_http_codes:
            retry_times = request.meta.get('retry_times', 0) + 1
            
            if retry_times <= self.max_retry_times:
                logger.warning(
                    f"Retrying {request.url} "
                    f"(failed with {response.status}, "
                    f"attempt {retry_times}/{self.max_retry_times})"
                )
                
                # Exponential backoff
                if self.use_exponential_backoff:
                    delay = self.base_delay * (2 ** (retry_times - 1))
                    request.meta['download_delay'] = delay
                    logger.debug(f"Retry delay: {delay}s")
                
                # Clone request for retry
                retry_req = request.copy()
                retry_req.meta['retry_times'] = retry_times
                retry_req.dont_filter = True
                
                return retry_req
            else:
                logger.error(
                    f"Gave up retrying {request.url} "
                    f"(failed {retry_times} times)"
                )
        
        return response
```

**Exponential Backoff**:
```
Attempt 1: 5 seconds
Attempt 2: 10 seconds
Attempt 3: 20 seconds
```

---

### 9.5 Class: `HeadersMiddleware`

**Mục đích**: Add custom headers to requests.

```python
class HeadersMiddleware:
    """Add custom headers to requests."""
    
    def process_request(self, request: Request, spider):
        """Add custom headers."""
        
        # Add Accept-Language
        request.headers['Accept-Language'] = 'en,vi'
        
        # Add Accept
        request.headers['Accept'] = 'text/html,application/xhtml+xml'
        
        # Add DNT (Do Not Track)
        request.headers['DNT'] = '1'
        
        # Add Cache-Control
        request.headers['Cache-Control'] = 'max-age=0'
```

---

### 9.6 Middleware Configuration

**Enable trong settings.py**:
```python
# src/crawlers/settings.py

DOWNLOADER_MIDDLEWARES = {
    # Disable default UserAgentMiddleware
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    
    # Enable custom middlewares
    'src.crawlers.common.middlewares.UserAgentRotationMiddleware': 400,
    'src.crawlers.common.middlewares.HeadersMiddleware': 410,
    
    # Retry middleware
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
    'src.crawlers.common.middlewares.CustomRetryMiddleware': 550,
    
    # Proxy middleware (disabled by default)
    # 'src.crawlers.common.middlewares.ProxyRotationMiddleware': 410,
}
```

**Priority**: Số càng nhỏ, chạy càng sớm trong request chain.

---

## 10. SCRAPY SETTINGS - CẤU HÌNH SCRAPY

### 10.1 File: `src/crawlers/settings.py`

**Mục đích**: Cấu hình Scrapy project.

### 10.2 Basic Settings

```python
BOT_NAME = "job_crawler_system"

SPIDER_MODULES = ["src.crawlers.topcv", "src.crawlers.common"]
NEWSPIDER_MODULE = "src.crawlers.topcv"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Concurrent requests
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# Download settings
DOWNLOAD_DELAY = 2
DOWNLOAD_TIMEOUT = 30
```

### 10.3 Load Configuration từ Config Module

```python
try:
    from config import get_setting, get_section
    
    # MongoDB settings
    MONGO_URI = get_setting('mongodb.uri', 'mongodb://localhost:27017')
    MONGO_DATABASE = get_setting('mongodb.database', 'job_crawler_db')
    
    # Scrapy settings from config
    scrapy_config = get_section('scrapy') or {}
    
    CONCURRENT_REQUESTS = scrapy_config.get('concurrent_requests', 16)
    DOWNLOAD_DELAY = scrapy_config.get('download_delay', 2)
    
except ImportError:
    # Fallback to default values
    MONGO_URI = 'mongodb://localhost:27017'
    MONGO_DATABASE = 'job_crawler_db'
    CONCURRENT_REQUESTS = 16
    DOWNLOAD_DELAY = 2
```

### 10.4 AutoThrottle Extension

```python
# Enable AutoThrottle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
```

**AutoThrottle benefits**:
- Tự động điều chỉnh tốc độ crawl
- Tránh overload server
- Tối ưu throughput

---

## 11. HƯỚNG DẪN SỬ DỤNG

### 11.1 Setup Môi trường

#### 11.1.1 Install Python Dependencies

```bash
cd job_crawler_system

# Tạo virtual environment (khuyến nghị)
python -m venv venv

# Activate
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 11.1.2 Setup MongoDB

**Option 1: Local MongoDB**
```bash
# Windows
net start MongoDB

# Linux
sudo systemctl start mongodb

# Mac
brew services start mongodb-community
```

**Option 2: Docker MongoDB**
```bash
docker run -d \
    --name mongodb \
    -p 27017:27017 \
    -v mongodb_data:/data/db \
    mongo:7.0
```

**Verify MongoDB**:
```bash
mongosh

# In mongo shell
show dbs
use job_crawler_db
db.job_postings_raw.find().limit(1)
```

#### 11.1.3 Setup Indexes

```bash
cd job_crawler_system

# Run setup script
python -c "from config.connections import setup_indexes; setup_indexes()"
```

**Output**:
```
Created unique compound index on (url, source)
Created text index for search
Created index on content_hash
Created index on crawl_timestamp
Created index on crawl_timestamp for history
Indexes created successfully!
```

---

### 11.2 Configuration

#### 11.2.1 Edit `config/settings.yaml`

```yaml
# Customize MongoDB connection
mongodb:
  uri: "mongodb://localhost:27017"
  database: "job_crawler_db"

# Customize Scrapy settings
scrapy:
  download_delay: 3
  concurrent_requests: 8

# Enable/disable sources
sources:
  topcv:
    enabled: true
    custom_settings:
      max_pages: 50
```

#### 11.2.2 Environment Variables (Optional)

```bash
# Create .env file
cat > .env << EOF
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE=job_crawler_db
LOG_LEVEL=INFO
EOF

# Load environment variables
source .env  # Linux/Mac
# Or use python-dotenv in code
```

---

### 11.3 Running Spiders

#### 11.3.1 Basic Usage

```bash
cd job_crawler_system

# Run spider với default settings
scrapy crawl topcv_spider

# Run với log file
scrapy crawl topcv_spider \
    --logfile logs/crawl_$(date +%Y%m%d_%H%M%S).log
```

#### 11.3.2 Custom Parameters

```bash
# Crawl 50 trang
scrapy crawl topcv_spider -a max_pages=50

# Disable incremental (full crawl)
scrapy crawl topcv_spider -a incremental=False -a max_pages=100

# Full spider
scrapy crawl topcv_full_spider -a max_pages=200
```

#### 11.3.3 Custom Settings

```bash
# Slower crawl (production)
scrapy crawl topcv_spider \
    -a max_pages=100 \
    -s DOWNLOAD_DELAY=5 \
    -s CONCURRENT_REQUESTS=4 \
    -s LOG_LEVEL=INFO

# Debug mode
scrapy crawl topcv_spider \
    -a max_pages=5 \
    -s LOG_LEVEL=DEBUG
```

#### 11.3.4 Export to File

```bash
# Export to JSON
scrapy crawl topcv_spider \
    -o output/jobs_$(date +%Y%m%d).json \
    -a max_pages=20

# Export to CSV
scrapy crawl topcv_spider \
    -o output/jobs.csv \
    -t csv \
    -a max_pages=10
```

---

### 11.4 Testing Components

#### 11.4.1 Test Parser

```bash
cd job_crawler_system

python src/crawlers/topcv/parser.py
```

**Output**:
```
Testing parser functions...
✓ clean_text: "  Python   Developer\n\n  " → "Python Developer"
✓ extract_salary: "10 - 15 triệu" → min=10M, max=15M VND
✓ parse_date: "Hôm nay" → 2025-11-24
✓ extract_skills: Found ['python', 'django', 'docker']
All tests passed!
```

#### 11.4.2 Test Database Utils

```bash
python src/utils/database.py
```

#### 11.4.3 Test Config

```bash
python -c "from config import load_config; import json; print(json.dumps(load_config(), indent=2))"
```

#### 11.4.4 Test MongoDB Connection

```bash
python -c "from config.connections import get_mongo_client; client = get_mongo_client(); print('Connected:', client.server_info())"
```

---

### 11.5 Monitoring và Logs

#### 11.5.1 View Logs

```bash
# Real-time log tailing
tail -f logs/crawl_latest.log

# Search logs
grep "ERROR" logs/crawl_*.log
grep "Inserted" logs/crawl_*.log
```

#### 11.5.2 MongoDB Query

```bash
mongosh

use job_crawler_db

# Count jobs
db.job_postings_raw.countDocuments()

# Recent jobs
db.job_postings_raw.find().sort({crawl_timestamp: -1}).limit(10)

# Jobs by source
db.job_postings_raw.countDocuments({source: "topcv"})

# Jobs updated today
db.job_postings_raw.countDocuments({
    crawl_timestamp: {
        $gte: new Date(new Date().setHours(0,0,0,0))
    }
})

# Search jobs
db.job_postings_raw.find({
    $text: {$search: "python developer"}
})

# Job with highest salary
db.job_postings_raw.find({
    "raw_data.salary_min": {$ne: null}
}).sort({"raw_data.salary_min": -1}).limit(10)
```

#### 11.5.3 Statistics Query

```python
# Create stats script: scripts/get_stats.py
from config.connections import get_collection

raw_coll = get_collection('raw_data')
history_coll = get_collection('history')

print("=== Job Crawler Statistics ===")
print(f"Total jobs: {raw_coll.count_documents({})}")
print(f"Active jobs: {raw_coll.count_documents({'metadata.is_active': True})}")
print(f"Inactive jobs: {raw_coll.count_documents({'metadata.is_active': False})}")

# By source
pipeline = [
    {"$group": {"_id": "$source", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
print("\nJobs by source:")
for doc in raw_coll.aggregate(pipeline):
    print(f"  {doc['_id']}: {doc['count']}")

print(f"\nTotal history versions: {history_coll.count_documents({})}")
```

Run:
```bash
python scripts/get_stats.py
```

---

## 12. TROUBLESHOOTING

### 12.1 Common Issues

#### Issue 1: MongoDB Connection Error

**Error**:
```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 111] Connection refused
```

**Solution**:
```bash
# Check MongoDB is running
sudo systemctl status mongodb  # Linux
net start MongoDB              # Windows

# Start MongoDB
sudo systemctl start mongodb   # Linux
net start MongoDB             # Windows

# Check connection
mongosh
```

#### Issue 2: Import Error

**Error**:
```
ModuleNotFoundError: No module named 'config'
```

**Solution**:
```bash
# Ensure you're in project root
cd job_crawler_system

# Check Python path
python -c "import sys; print(sys.path)"

# Run spider from correct directory
scrapy crawl topcv_spider
```

#### Issue 3: Brotli Encoding Error

**Error**:
```
Cannot decode response body
```

**Solution**:
```bash
# Install brotli
pip install brotli

# Or use brotlipy
pip install brotlipy
```

#### Issue 4: Rate Limiting / IP Ban

**Symptoms**:
- Many 429 errors
- Requests timing out
- Empty responses

**Solution**:
```bash
# Increase delay
scrapy crawl topcv_spider -s DOWNLOAD_DELAY=5

# Reduce concurrency
scrapy crawl topcv_spider -s CONCURRENT_REQUESTS=2

# Enable proxy rotation
# Edit config/settings.yaml:
proxy:
  enabled: true
  servers:
    - "http://proxy1:8080"
```

---

### 12.2 Debugging Tips

#### Tip 1: Enable Debug Logging

```bash
scrapy crawl topcv_spider -s LOG_LEVEL=DEBUG
```

#### Tip 2: Scrapy Shell

```bash
# Test selectors interactively
scrapy shell "https://www.topcv.vn/tim-viec-lam-moi-nhat"

# In shell
>>> response.css('.job-item-search-result').getall()
>>> response.css('h3.title a::attr(href)').get()
```

#### Tip 3: Test Single URL

```bash
# Create test spider
scrapy parse https://www.topcv.vn/viec-lam/job-123 \
    --spider=topcv_spider \
    --callback=parse_job_detail
```

---

### 12.3 Performance Tuning

#### For Speed:
```python
# settings.py
CONCURRENT_REQUESTS = 32
DOWNLOAD_DELAY = 1
AUTOTHROTTLE_ENABLED = False
```

#### For Safety:
```python
# settings.py
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 5
AUTOTHROTTLE_ENABLED = True
```

---

## 13. KẾT LUẬN

### 13.1 Tính năng Đã triển khai

✅ **Core Components**:
- Items: JobItem với 30+ fields
- Parser: Extract salary, skills, dates
- Spider: Pagination & incremental crawling
- Pipelines: Validation, cleaning, MongoDB upsert
- Middlewares: User-Agent rotation, retry logic

✅ **Database**:
- Content hashing
- Document versioning
- Upsert logic với history tracking
- Indexes optimization

✅ **Configuration**:
- Centralized YAML config
- MongoDB connection factory
- Environment variables support

### 13.2 Best Practices

1. **Respect robots.txt**: Always set `ROBOTSTXT_OBEY = True`
2. **Use appropriate delays**: `DOWNLOAD_DELAY >= 2` seconds
3. **Monitor crawling**: Check logs và MongoDB statistics
4. **Incremental crawling**: Save bandwidth và time
5. **Error handling**: Implement retry logic và error callbacks

### 13.3 Next Steps

- [ ] Add more sources (VietnamWorks, ITviec, ...)
- [ ] Implement Airflow DAGs for scheduling
- [ ] Add data analysis và reporting
- [ ] Implement notifications (email/Slack)
- [ ] Add ML-based field extraction
- [ ] Build API để query data
- [ ] Create dashboard với visualization

---

**Tài liệu này cover toàn bộ hệ thống từ config, database, parser, spider, pipelines đến middlewares và usage. Mỗi component được giải thích chi tiết với examples và best practices.**
