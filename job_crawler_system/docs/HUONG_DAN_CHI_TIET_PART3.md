# HƯỚNG DẪN CHI TIẾT - PHẦN 3

## 7. SPIDER MODULE - THU THẬP DỮ LIỆU

### 7.1 File: `src/crawlers/topcv/spider.py`

**Mục đích**: Scrapy spider để thu thập dữ liệu từ TopCV.vn

### 7.2 Class: `TopCVSpider`

#### 7.2.1 Spider Configuration

```python
class TopCVSpider(scrapy.Spider):
    name = 'topcv_spider'
    allowed_domains = ['topcv.vn']
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 8,
        'ROBOTSTXT_OBEY': True,
        'COOKIES_ENABLED': True,
        'ITEM_PIPELINES': {
            'src.crawlers.common.pipelines.ValidationPipeline': 100,
            'src.crawlers.common.pipelines.MongoPipeline': 300,
        }
    }
```

**Giải thích**:
- `name`: Tên spider (dùng để chạy: `scrapy crawl topcv_spider`)
- `allowed_domains`: Chỉ crawl trong domain này
- `custom_settings`: Override Scrapy settings cho spider này

#### 7.2.2 Constructor & Initialization

```python
def __init__(
    self, 
    max_pages: int = 10,
    incremental: bool = True,
    *args, 
    **kwargs
):
    super().__init__(*args, **kwargs)
    
    self.max_pages = int(max_pages)
    self.incremental = incremental
    self.stop_crawling = False
    
    # Statistics
    self.stats = {
        'pages_crawled': 0,
        'jobs_found': 0,
        'jobs_detailed': 0,
        'jobs_skipped': 0
    }
    
    # Start URLs
    self.start_urls = [
        'https://www.topcv.vn/tim-viec-lam-moi-nhat',
    ]
```

**Parameters**:
- `max_pages`: Số trang tối đa cần crawl (default: 10)
- `incremental`: Bật incremental crawling - dừng khi gặp job cũ (default: True)

**Usage**:
```bash
# Default: max_pages=10, incremental=True
scrapy crawl topcv_spider

# Custom max_pages
scrapy crawl topcv_spider -a max_pages=50

# Disable incremental (crawl tất cả)
scrapy crawl topcv_spider -a incremental=False -a max_pages=100
```

#### 7.2.3 Method: `start_requests()`

**Mục đích**: Generate initial requests

```python
def start_requests(self):
    """Generate initial requests."""
    for url in self.start_urls:
        yield scrapy.Request(
            url=url,
            callback=self.parse_job_list,
            meta={'page': 1},
            errback=self.errback_httpbin,
            dont_filter=True
        )
```

**Giải thích**:
- `callback`: Function xử lý response
- `meta`: Dictionary chứa metadata (page number)
- `errback`: Function xử lý lỗi
- `dont_filter`: Không filter duplicate URL (cho pagination)

#### 7.2.4 Method: `parse_job_list()` - Core Parsing Logic

**Quy trình xử lý trang danh sách**:

```
┌─────────────────────────────────────────┐
│ parse_job_list(response)                │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 1. Check & Handle Encoding (Brotli)    │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 2. Extract job items từ page           │
│    (.job-item-search-result)           │
└─────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ For each job:   │
        └─────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 3. Parse basic info (list item)        │
│    → parse_job_list_item()             │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 4. Check incremental crawling          │
│    - Nếu job cũ (crawled < 24h)       │
│      → Set stop_crawling = True        │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 5. Generate Request cho detail page    │
│    callback=parse_job_detail           │
│    priority=10 (high)                  │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ 6. Generate pagination request         │
│    (next page) if not stop_crawling    │
└─────────────────────────────────────────┘
```

**Code Implementation**:

```python
def parse_job_list(self, response):
    current_page = response.meta.get('page', 1)
    self.stats['pages_crawled'] += 1
    
    logger.info(f"Parsing job list page {current_page}: {response.url}")
    
    # Extract job items
    job_selectors = response.css('.job-item-search-result')
    
    if not job_selectors:
        logger.warning(f"No jobs found on page {current_page}")
        return
    
    jobs_on_page = 0
    
    for job_selector in job_selectors:
        if self.stop_crawling:
            logger.info("Stopping crawl due to incremental logic")
            return
        
        # Parse basic info
        job_data = parse_job_list_item(job_selector)
        
        if not job_data.get('url'):
            logger.warning("Job item missing URL, skipping")
            continue
        
        # Make absolute URL
        absolute_url = urljoin(response.url, job_data['url'])
        job_data['url'] = absolute_url
        
        # Check incremental crawling
        if self.incremental:
            posted_date = job_data.get('posted_date')
            if posted_date:
                days_old = (datetime.now() - posted_date).days
                
                if days_old > 1:  # Job older than 1 day
                    logger.info(f"Found old job (posted {days_old} days ago), stopping")
                    self.stop_crawling = True
                    return
        
        # Generate request for detail page
        yield scrapy.Request(
            url=absolute_url,
            callback=self.parse_job_detail,
            meta={'list_item': job_data},
            priority=10,  # High priority for detail pages
            errback=self.errback_httpbin
        )
        
        jobs_on_page += 1
        self.stats['jobs_found'] += 1
    
    logger.info(f"Found {jobs_on_page} jobs on page {current_page}")
    
    # Pagination - generate next page request
    if current_page < self.max_pages and not self.stop_crawling:
        next_page = current_page + 1
        next_url = f"{self.start_urls[0]}?page={next_page}"
        
        yield scrapy.Request(
            url=next_url,
            callback=self.parse_job_list,
            meta={'page': next_page},
            priority=5,  # Lower priority than detail pages
            errback=self.errback_httpbin,
            dont_filter=True
        )
```

**Key Features**:

**1. Incremental Crawling**:
```python
if self.incremental:
    posted_date = job_data.get('posted_date')
    if posted_date:
        days_old = (datetime.now() - posted_date).days
        
        if days_old > 1:  # Stop at old jobs
            self.stop_crawling = True
            return
```

**2. Request Prioritization**:
- Detail pages: `priority=10` (cao)
- Pagination: `priority=5` (thấp)
→ Scrapy ưu tiên crawl chi tiết trước

**3. Statistics Tracking**:
```python
self.stats = {
    'pages_crawled': 0,      # Số trang list đã crawl
    'jobs_found': 0,         # Số jobs tìm thấy
    'jobs_detailed': 0,      # Số jobs đã crawl chi tiết
    'jobs_skipped': 0        # Số jobs bị skip
}
```

#### 7.2.5 Method: `parse_job_detail()` - Detail Page Parsing

**Quy trình**:

```python
def parse_job_detail(self, response):
    """Parse job detail page và merge với list item."""
    
    self.stats['jobs_detailed'] += 1
    
    # Parse full details
    detail_data = parse_job_detail(response)
    
    if not detail_data:
        logger.error(f"Failed to parse job detail: {response.url}")
        return
    
    # Get basic info from list page
    list_item = response.meta.get('list_item', {})
    
    # Create JobItem
    item = JobItem()
    
    # Merge data: detail_data takes precedence
    for key, value in list_item.items():
        item[key] = value
    
    for key, value in detail_data.items():
        item[key] = value
    
    # Add metadata
    item['source'] = 'topcv'
    item['crawl_timestamp'] = datetime.utcnow()
    item['last_seen_timestamp'] = datetime.utcnow()
    
    # Calculate content hash
    item['raw_data'] = detail_data
    item['content_hash'] = calculate_content_hash(
        detail_data,
        fields=['title', 'company', 'salary_raw', 'description', 'requirements']
    )
    
    # Validate before yielding
    if validate_job_item(item):
        yield item
    else:
        logger.warning(f"Invalid job item: {response.url}")
        self.stats['jobs_skipped'] += 1
```

**Data Flow**:
```
List Item (basic)  +  Detail Data (full)  →  JobItem (complete)
     │                       │                      │
     ▼                       ▼                      ▼
  url: ...              description: ...      url: ...
  title: ...            requirements: ...     title: ...
  company: ...          benefits: ...         company: ...
  salary_raw: ...       skills: [...]         description: ...
  location: ...         contact_email: ...    requirements: ...
                                              ... (all fields)
```

#### 7.2.6 Method: `errback_httpbin()` - Error Handling

```python
def errback_httpbin(self, failure):
    """Handle request failures."""
    
    logger.error(f"Request failed: {failure.request.url}")
    logger.error(f"Reason: {failure.value}")
    
    # Log failure type
    if failure.check(HttpError):
        response = failure.value.response
        logger.error(f"HttpError on {response.url}: {response.status}")
    elif failure.check(DNSLookupError):
        logger.error(f"DNSLookupError on {failure.request.url}")
    elif failure.check(TimeoutError):
        logger.error(f"TimeoutError on {failure.request.url}")
```

#### 7.2.7 Method: `closed()` - Spider Shutdown

```python
def closed(self, reason):
    """Called when spider closes - log statistics."""
    
    logger.info("=" * 60)
    logger.info("Spider closed: TopCVSpider")
    logger.info(f"Reason: {reason}")
    logger.info("=" * 60)
    logger.info("Statistics:")
    logger.info(f"  Pages crawled: {self.stats['pages_crawled']}")
    logger.info(f"  Jobs found: {self.stats['jobs_found']}")
    logger.info(f"  Jobs detailed: {self.stats['jobs_detailed']}")
    logger.info(f"  Jobs skipped: {self.stats['jobs_skipped']}")
    logger.info("=" * 60)
```

**Output Example**:
```
============================================================
Spider closed: TopCVSpider
Reason: finished
============================================================
Statistics:
  Pages crawled: 10
  Jobs found: 200
  Jobs detailed: 198
  Jobs skipped: 2
============================================================
```

---

### 7.3 Class: `TopCVFullSpider` - Full Crawl Variant

**Khác biệt với `TopCVSpider`**:
- Không có incremental crawling (crawl toàn bộ)
- Default `max_pages` cao hơn (100)

```python
class TopCVFullSpider(TopCVSpider):
    """
    Full spider variant - không dùng incremental crawling.
    Dùng cho full refresh hoặc initial crawl.
    """
    
    name = 'topcv_full_spider'
    
    def __init__(self, *args, **kwargs):
        # Force incremental=False
        kwargs['incremental'] = False
        kwargs.setdefault('max_pages', 100)
        super().__init__(*args, **kwargs)
        
        logger.info("TopCVFullSpider initialized - full crawl mode")
```

**Usage**:
```bash
# Full crawl - không dừng ở jobs cũ
scrapy crawl topcv_full_spider -a max_pages=200

# Với custom settings
scrapy crawl topcv_full_spider \
    -a max_pages=500 \
    -s DOWNLOAD_DELAY=5 \
    -s CONCURRENT_REQUESTS=4
```

---

### 7.4 Spider Usage Examples

#### Example 1: Basic Crawl
```bash
cd job_crawler_system

# Crawl 10 trang (default)
scrapy crawl topcv_spider

# Output logs cho thấy progress
# 2025-11-24 10:00:00 [topcv_spider] INFO: Parsing job list page 1
# 2025-11-24 10:00:05 [topcv_spider] INFO: Found 20 jobs on page 1
# ...
```

#### Example 2: Custom Parameters
```bash
# Crawl 50 trang
scrapy crawl topcv_spider -a max_pages=50

# Disable incremental
scrapy crawl topcv_spider -a incremental=False -a max_pages=100

# Combine multiple params
scrapy crawl topcv_spider \
    -a max_pages=30 \
    -a incremental=True \
    -s DOWNLOAD_DELAY=3
```

#### Example 3: Custom Settings
```bash
# Override Scrapy settings
scrapy crawl topcv_spider \
    -s DOWNLOAD_DELAY=5 \
    -s CONCURRENT_REQUESTS=4 \
    -s LOG_LEVEL=DEBUG

# Export to file
scrapy crawl topcv_spider \
    -o output/jobs_$(date +%Y%m%d).json \
    -a max_pages=20
```

#### Example 4: Production Crawl
```bash
# Production settings: slow, careful
scrapy crawl topcv_spider \
    -a max_pages=100 \
    -a incremental=True \
    -s DOWNLOAD_DELAY=3 \
    -s CONCURRENT_REQUESTS=4 \
    -s LOG_LEVEL=INFO \
    --logfile logs/topcv_$(date +%Y%m%d_%H%M%S).log
```

---

## 8. PIPELINES MODULE - XỬ LÝ ITEM

### 8.1 File: `src/crawlers/common/pipelines.py`

**Mục đích**: Pipelines để xử lý items sau khi được scraped.

**Pipeline Flow**:
```
Item scraped by spider
        │
        ▼
┌───────────────────────────┐
│ ValidationPipeline (100)  │  ← Validate required fields
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│ DuplicatesPipeline (200)  │  ← Filter in-memory duplicates
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│ CleaningPipeline (250)    │  ← Clean & normalize data
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│ MongoPipeline (300)       │  ← Save to MongoDB với versioning
└───────────────────────────┘
        │
        ▼
┌───────────────────────────┐
│ LoggingPipeline (400)     │  ← Log to MongoDB (optional)
└───────────────────────────┘
```

**Priority**: Số càng nhỏ, chạy càng sớm.

---

### 8.2 Class: `ValidationPipeline`

**Mục đích**: Validate items, drop invalid items.

```python
class ValidationPipeline:
    """Validate items trước khi xử lý tiếp."""
    
    def __init__(self):
        self.stats = {
            'valid': 0,
            'invalid': 0
        }
    
    def process_item(self, item, spider):
        """Validate item."""
        adapter = ItemAdapter(item)
        
        # Required fields
        required_fields = ['url', 'source']
        
        # Check required fields
        for field in required_fields:
            if not adapter.get(field):
                logger.warning(
                    f"Item missing required field '{field}': "
                    f"{adapter.get('url', 'Unknown')}"
                )
                self.stats['invalid'] += 1
                raise DropItem(f"Missing required field: {field}")
        
        # Validate URL format
        url = adapter.get('url')
        if not url.startswith('http'):
            logger.warning(f"Invalid URL format: {url}")
            self.stats['invalid'] += 1
            raise DropItem("Invalid URL format")
        
        self.stats['valid'] += 1
        return item
    
    def close_spider(self, spider):
        """Log statistics when spider closes."""
        logger.info(
            f"ValidationPipeline stats: "
            f"valid={self.stats['valid']}, invalid={self.stats['invalid']}"
        )
```

**Behavior**:
- ✅ Valid item → Pass to next pipeline
- ❌ Invalid item → Raise `DropItem` exception → Bị loại bỏ

**Example**:
```python
# Valid item
item = {
    'url': 'https://topcv.vn/job-123',
    'source': 'topcv',
    'title': 'Python Dev'
}
# → Pass validation

# Invalid item - missing URL
item = {
    'source': 'topcv',
    'title': 'Python Dev'
}
# → DropItem("Missing required field: url")

# Invalid item - wrong URL format
item = {
    'url': 'not-a-valid-url',
    'source': 'topcv'
}
# → DropItem("Invalid URL format")
```

---

### 8.3 Class: `DuplicatesPipeline`

**Mục đích**: Filter in-memory duplicates trong cùng một crawl session.

```python
class DuplicatesPipeline:
    """Filter duplicate items trong cùng crawl session."""
    
    def __init__(self):
        self.urls_seen = set()
        self.stats = {
            'unique': 0,
            'duplicates': 0
        }
    
    def process_item(self, item, spider):
        """Check for duplicates."""
        adapter = ItemAdapter(item)
        url = adapter.get('url')
        
        if url in self.urls_seen:
            self.stats['duplicates'] += 1
            raise DropItem(f"Duplicate item found: {url}")
        else:
            self.urls_seen.add(url)
            self.stats['unique'] += 1
            return item
    
    def close_spider(self, spider):
        """Log statistics."""
        logger.info(
            f"DuplicatesPipeline stats: "
            f"unique={self.stats['unique']}, "
            f"duplicates={self.stats['duplicates']}"
        )
```

**Use case**: Trong một crawl session, có thể crawl trùng job nếu:
- Job xuất hiện ở nhiều trang khác nhau
- Pagination overlap
- Error retry

---

### 8.4 Class: `CleaningPipeline`

**Mục đích**: Clean và normalize dữ liệu.

```python
class CleaningPipeline:
    """Clean và normalize dữ liệu."""
    
    def process_item(self, item, spider):
        """Clean item data."""
        adapter = ItemAdapter(item)
        
        # Clean text fields
        text_fields = ['title', 'company', 'location', 'description', 'requirements']
        for field in text_fields:
            value = adapter.get(field)
            if value and isinstance(value, str):
                # Trim and clean
                cleaned = value.strip()
                adapter[field] = cleaned if cleaned else None
        
        # Ensure timestamps are datetime objects
        if adapter.get('crawl_timestamp') is None:
            adapter['crawl_timestamp'] = datetime.utcnow()
        
        # Ensure lists
        if adapter.get('skills') and not isinstance(adapter['skills'], list):
            adapter['skills'] = []
        
        if adapter.get('industries') and not isinstance(adapter['industries'], list):
            adapter['industries'] = []
        
        return item
```

**Cleaning operations**:
1. Trim whitespace từ text fields
2. Convert empty strings → `None`
3. Ensure timestamps are datetime objects
4. Ensure array fields are lists (không phải None hoặc single value)

---

### 8.5 Class: `MongoPipeline` - Core Pipeline

**Mục đích**: Lưu items vào MongoDB với document versioning.

#### 8.5.1 Initialization

```python
class MongoPipeline:
    """Pipeline lưu items vào MongoDB với document versioning."""
    
    def __init__(self, mongo_uri=None, mongo_db=None):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.helper = None
        
        self.stats = {
            'inserted': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0
        }
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance từ crawler settings."""
        try:
            from config import get_setting
            
            mongo_uri = get_setting('mongodb.uri')
            mongo_db = get_setting('mongodb.database')
        except:
            # Fallback to Scrapy settings
            mongo_uri = crawler.settings.get('MONGO_URI', 'mongodb://localhost:27017')
            mongo_db = crawler.settings.get('MONGO_DATABASE', 'job_crawler_db')
        
        return cls(
            mongo_uri=mongo_uri,
            mongo_db=mongo_db
        )
```

#### 8.5.2 Spider Lifecycle

```python
def open_spider(self, spider):
    """Called khi spider mở - Setup MongoDB connection."""
    logger.info("Opening MongoDB connection...")
    
    try:
        from src.utils.database import create_helper
        
        # Create helper với collections từ config
        self.helper = create_helper(
            raw_collection_name='raw_data',
            history_collection_name='history',
            enable_versioning=True
        )
        
        logger.info("MongoDB helper initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB helper: {e}")
        raise
```

```python
def close_spider(self, spider):
    """Called khi spider đóng - Log statistics."""
    logger.info("=" * 60)
    logger.info("MongoPipeline Statistics:")
    logger.info(f"  Inserted: {self.stats['inserted']}")
    logger.info(f"  Updated: {self.stats['updated']}")
    logger.info(f"  Unchanged: {self.stats['unchanged']}")
    logger.info(f"  Errors: {self.stats['errors']}")
    logger.info("=" * 60)
```

#### 8.5.3 Processing Items

```python
def process_item(self, item, spider):
    """Process và save item to MongoDB."""
    try:
        # Convert item to dict
        item_dict = dict(item)
        
        # Upsert using helper
        is_new, doc_id, status = self.helper.upsert_job(item_dict)
        
        # Update statistics
        self.stats[status] += 1
        
        # Log result
        if status == 'inserted':
            logger.info(f"Inserted new job: {item_dict.get('url')}")
        elif status == 'updated':
            logger.info(f"Updated job: {item_dict.get('url')}")
        else:
            logger.debug(f"Unchanged job: {item_dict.get('url')}")
        
        return item
        
    except Exception as e:
        self.stats['errors'] += 1
        logger.error(f"Error processing item: {e}")
        logger.error(f"Item URL: {item.get('url', 'Unknown')}")
        # Don't raise - continue processing other items
        return item
```

**Flow**:
```
Item → Convert to dict → Upsert via helper → Update stats → Log
```

---

### 8.6 Class: `LoggingPipeline` (Optional)

**Mục đích**: Log items vào MongoDB logs collection.

```python
class LoggingPipeline:
    """Log items to MongoDB logs collection."""
    
    def open_spider(self, spider):
        """Setup logs collection."""
        from config.connections import get_collection
        self.logs_collection = get_collection('logs')
    
    def process_item(self, item, spider):
        """Log item."""
        log_entry = {
            'spider': spider.name,
            'url': item.get('url'),
            'title': item.get('title'),
            'company': item.get('company'),
            'timestamp': datetime.utcnow(),
            'status': 'processed'
        }
        
        self.logs_collection.insert_one(log_entry)
        
        return item
```

---

### 8.7 Pipeline Configuration trong Settings

```python
# File: src/crawlers/settings.py

ITEM_PIPELINES = {
    'src.crawlers.common.pipelines.ValidationPipeline': 100,
    'src.crawlers.common.pipelines.DuplicatesPipeline': 200,
    'src.crawlers.common.pipelines.CleaningPipeline': 250,
    'src.crawlers.common.pipelines.MongoPipeline': 300,
    # 'src.crawlers.common.pipelines.LoggingPipeline': 400,  # Optional
}
```

**Enable/Disable pipelines**:
```python
# Disable một pipeline
ITEM_PIPELINES = {
    'src.crawlers.common.pipelines.ValidationPipeline': 100,
    # 'src.crawlers.common.pipelines.DuplicatesPipeline': None,  # Disabled
    'src.crawlers.common.pipelines.CleaningPipeline': 250,
    'src.crawlers.common.pipelines.MongoPipeline': 300,
}
```

---

[Tiếp tục phần Middlewares và Usage trong file tiếp theo...]
