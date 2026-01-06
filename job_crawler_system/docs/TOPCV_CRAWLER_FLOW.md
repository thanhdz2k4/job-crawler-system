# TopCV Crawler - Luồng Chạy Chi Tiết

## Tổng Quan

Crawler TopCV được xây dựng bằng Scrapy framework để thu thập dữ liệu việc làm từ website TopCV.vn. Crawler hoạt động theo mô hình 2 giai đoạn: **List Crawling** và **Detail Crawling**.

---

## Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────────┐
│                    TopCV Crawler System                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Start Requests                                           │
│     └─→ https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&page=1&saturday_status=0          │
│                                                              │
│  2. List Page Crawling (parse_job_list)                     │
│     ├─→ Extract job URLs                                     │
│     ├─→ Parse basic info (title, company, salary)           │
│     └─→ Pagination                                           │
│                                                              │
│  3. Detail Page Crawling (parse_job_detail)                 │
│     ├─→ Filter HTML (chỉ lấy phần liên quan)                │
│     ├─→ Parse từ các class cụ thể                            │
│     └─→ Validate & Create Item                               │
│                                                              │
│  4. Pipeline Processing                                      │
│     ├─→ ValidationPipeline                                   │
│     └─→ MongoPipeline → MongoDB                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Luồng Chạy Chi Tiết

### Phase 1: Khởi Tạo Spider

**File:** `spider.py` - Class `TopCVSpider`

```python
def __init__(self, max_pages=10, incremental=True):
    # Khởi tạo các tham số
    self.max_pages = 10          # Số trang tối đa
    self.incremental = True       # Bật incremental crawling
    self.start_urls = [
        'https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&page=1&saturday_status=0'
    ]
```

**Thống kê được khởi tạo:**
- `pages_crawled`: Số trang đã crawl
- `jobs_found`: Số job đã tìm thấy
- `jobs_detailed`: Số job đã parse chi tiết
- `jobs_skipped`: Số job bị skip (invalid)

---

### Phase 2: Bắt Đầu Crawling

**Method:** `start_requests()`

```python
def start_requests(self):
    for url in self.start_urls:
        yield scrapy.Request(
            url=url,
            callback=self.parse_job_list,  # Callback xử lý response
            meta={'page': 1},               # Metadata: trang hiện tại
            errback=self.errback_httpbin,   # Xử lý lỗi
            dont_filter=True                # Không filter duplicate URLs
        )
```

**Flow:**
1. Tạo request đầu tiên đến trang list
2. Scrapy download HTML
3. Gọi `parse_job_list()` với response

---

### Phase 3: Parse Trang Danh Sách

**Method:** `parse_job_list(response)`

#### 3.1. Xử Lý Encoding

```python
# Kiểm tra response có decode được không
try:
    if not response.text:
        logger.error("Empty response body")
        return
except Exception as e:
    # Xử lý brotli encoding nếu cần
    response = self._handle_brotli_encoding(response)
```

**Vấn đề:** TopCV có thể trả về HTML nén bằng Brotli  
**Giải pháp:** Tự động decompress nếu cần

#### 3.2. Tìm Job Items

```python
# Tìm các job items bằng CSS selector
job_selectors = response.css(
    '.job-item, .job-list-item, .job-item-search-result'
)
```

**Kết quả:** Danh sách các selector chứa thông tin job

#### 3.3. Parse Thông Tin Cơ Bản Từng Job

**File:** `parser.py` - Function `parse_job_list_item()`

```python
for job_selector in job_selectors:
    # Parse basic info
    job_data = parse_job_list_item(job_selector)
    # Kết quả:
    # {
    #     'url': '...',
    #     'title': '...',
    #     'company': '...',
    #     'salary_raw': '...',
    #     'location': '...',
    #     'posted_date': datetime(...),
    #     'is_hot': True/False
    # }
```

**Các field được extract:**
- **URL**: `h3.title a::attr(href)`
- **Title**: `h3.title a span::text` hoặc `h3.title a::text`
- **Company**: `a.company::text`
- **Salary**: `.title-salary::text`
- **Location**: `.address::text`
- **Posted Date**: `.time::text` hoặc `.up-date::text` → Parse thành datetime
- **Logo**: `a.logo img::attr(src)`

#### 3.4. Tạo Request Cho Trang Chi Tiết

```python
# Make absolute URL
job_url = urljoin(response.url, job_data['url'])

# Request trang detail
yield scrapy.Request(
    url=job_url,
    callback=self.parse_job_detail,
    meta={'list_data': job_data},  # Truyền data từ list page
    errback=self.errback_httpbin,
    priority=10  # Ưu tiên cao hơn list pages
)
```

**Lưu ý:**
- `list_data` được lưu trong `meta` để merge sau
- `priority=10` đảm bảo detail pages được xử lý trước

#### 3.5. Incremental Crawling Check

```python
if self.incremental and job_data.get('posted_date'):
    if isinstance(job_data['posted_date'], datetime):
        age = datetime.now() - job_data['posted_date']
        if age > timedelta(hours=24):
            logger.info("Job older than 24h, considering stop")
            # Có thể set self.stop_crawling = True
```

**Mục đích:** Dừng crawl khi gặp job cũ hơn 24h (tiết kiệm tài nguyên)

#### 3.6. Pagination

```python
if current_page < self.max_pages and not self.stop_crawling:
    next_page = self._get_next_page_url(response, current_page)
    
    if next_page:
        yield scrapy.Request(
            url=next_page,
            callback=self.parse_job_list,
            meta={'page': current_page + 1}
        )
```

**Method:** `_get_next_page_url()`

**2 cách tìm trang tiếp theo:**
1. **Tìm link "Next"** trong HTML:
   ```python
   next_link = response.css('a.next::attr(href)').get()
   ```

2. **Construct URL** với page parameter:
   ```python
   # URL format: ?type_keyword=1&page=1&saturday_status=0
   # Update page parameter trong URL có nhiều parameters
   if 'page=' in response.url:
       next_url = re.sub(r'page=\d+', f'page={next_page_num}', response.url)
   else:
       separator = '&' if '?' in response.url else '?'
       next_url = f"{response.url}{separator}page={next_page_num}"
   ```

---

### Phase 4: Parse Trang Chi Tiết

**Method:** `parse_job_detail(response)`

#### 4.1. Lọc HTML Trước Khi Parse

**Method:** `_filter_relevant_html(response)`

**Mục đích:** Chỉ giữ các phần HTML liên quan, loại bỏ phần không cần thiết

```python
def _filter_relevant_html(self, response):
    sections = {
        'header': response.css('#header-job-info').get(),           # Title
        'detail': response.css('#box-job-information-detail').get(), # Nội dung
        'company': response.css('.job-detail__box--right.job-detail__company').get()
    }
    
    # Tạo HTML mới chỉ chứa 3 phần này
    filtered_html = f"""<!DOCTYPE html>
    <html>
    <body>
        {sections['header']} {sections['detail']} {sections['company']}
    </body>
    </html>"""
    
    return HtmlResponse(body=filtered_html.encode('utf-8'))
```

**Lợi ích:**
- Giảm kích thước HTML từ ~500KB xuống ~50KB (90%)
- Tăng tốc độ parse
- Giảm nhiễu từ phần không liên quan

#### 4.2. Parse Dữ Liệu Từ Các Class Cụ Thể

**File:** `parser.py` - Function `parse_job_detail()`

##### 4.2.1. Title

```python
# Ưu tiên class mới
title_element = response.css('.job-detail__info--title')
if title_element:
    job['title'] = clean_text(" ".join(title_element.css('::text').getall()))
else:
    # Fallback về các selector cũ
    job['title'] = try_selectors([...])
```

**Class:** `.job-detail__info--title`

##### 4.2.2. Company

```python
company_element = response.css('.job-detail__company--information')
if company_element:
    job['company'] = clean_text(" ".join(company_element.css('::text').getall()))
```

**Class:** `.job-detail__company--information`

##### 4.2.3. Deadline

```python
deadline_element = response.css('.job-detail__info--deadline-date')
if deadline_element:
    deadline_txt = clean_text(" ".join(deadline_element.css('::text').getall()))
    job['deadline'] = parse_date(deadline_txt)  # Parse thành datetime
```

**Class:** `.job-detail__info--deadline-date`  
**Xử lý:** Parse text thành `datetime` object

##### 4.2.4. Description

```python
description_items = response.css('.job-description__item')
for item in description_items:
    item_classes = item.css('::attr(class)').get() or ""
    # Skip requirement và benefit
    if 'requirement' not in item_classes and 'benefit' not in item_classes:
        text = clean_text(" ".join(item.css('::text').getall()))
        if text and len(text) > 10:
            job['description'] = text
            break
```

**Class:** `.job-description__item` (không có `requirement` hoặc `benefit`)

##### 4.2.5. Requirements

```python
requirement_items = response.css(
    '.job-description__item.job-detail-section.requirement'
)
if requirement_items:
    all_requirement_texts = []
    for req_item in requirement_items:
        text = clean_text(" ".join(req_item.css('::text').getall()))
        if text:
            all_requirement_texts.append(text)
    job['requirements'] = " ".join(all_requirement_texts)
```

**Class:** `.job-description__item.job-detail-section.requirement`  
**Lưu ý:** Lấy text từ TẤT CẢ requirement items và join lại

##### 4.2.6. Benefits

```python
benefit_items = response.css(
    '.job-description__item.job-detail-section.benefit'
)
if benefit_items:
    all_benefit_texts = []
    for ben_item in benefit_items:
        text = clean_text(" ".join(ben_item.css('::text').getall()))
        if text:
            all_benefit_texts.append(text)
    job['benefits'] = " ".join(all_benefit_texts)
```

**Class:** `.job-description__item.job-detail-section.benefit`

##### 4.2.7. Location

```python
location_items = response.css('.job-description__item')
for item in location_items:
    item_classes = item.css('::attr(class)').get() or ""
    if 'requirement' not in item_classes and 'benefit' not in item_classes:
        text = clean_text(" ".join(item.css('::text').getall()))
        # Phân biệt với description bằng cách so sánh text
        if text and len(text) > 5 and text != description_text:
            location_text = text
            break
```

**Class:** `.job-description__item` (phân biệt với description)

##### 4.2.8. Salary

```python
salary_txt = try_selectors([...])
salary_data = extract_salary(salary_txt)
job.update({
    'salary_raw': salary_data['raw'],      # "10-20 triệu"
    'salary_min': salary_data['min'],      # 10000000
    'salary_max': salary_data['max'],      # 20000000
    'salary_currency': salary_data['currency']  # "VND"
})
```

**Xử lý:**
- Parse text "10-20 triệu" → min=10,000,000, max=20,000,000
- Detect currency (VND/USD)
- Handle "thỏa thuận", "cạnh tranh"

##### 4.2.9. Experience

```python
job['experience'] = try_selectors([
    '.box-info-job .job-detail-info-experience .job-detail-info-value',
    ...
])
```

#### 4.3. Xử Lý Dữ Liệu

##### 4.3.1. Merge Với List Data

```python
list_data = response.meta.get('list_data', {})
for key, value in list_data.items():
    # Nếu detail page thiếu thông tin, dùng data từ list page
    if key not in job_data or not job_data[key]:
        job_data[key] = value
```

**Mục đích:** Đảm bảo không mất thông tin nếu detail page thiếu

##### 4.3.2. Extract Skills

```python
full_text = f"{job['description']} {job['requirements']}"
job['skills'] = extract_skills(full_text)
```

**Function:** `extract_skills()`  
**Cách hoạt động:**
- Tìm keywords trong danh sách skills phổ biến
- Sử dụng word boundary để tránh partial match
- Ví dụ: "java" không match trong "javascript"

**Skills được detect:**
- Languages: Python, Java, JavaScript, TypeScript, C#, PHP, Golang, Ruby
- Frameworks: React, Angular, Vue, Node.js, Django, Flask, Spring, Laravel
- Databases: SQL, MySQL, PostgreSQL, MongoDB, Redis
- Cloud/DevOps: AWS, Azure, Docker, Kubernetes, Git, Linux, CI/CD
- Others: Machine Learning, AI, Data Analysis, Excel

##### 4.3.3. Validate

```python
if not validate_job_item(job_data):
    logger.warning("Invalid job item, skipping")
    self.stats['jobs_skipped'] += 1
    return
```

**Function:** `validate_job_item()`  
**Kiểm tra:**
- Có `title` không?
- Có `url` không?

#### 4.4. Tạo Item

```python
item = JobItem()
# Populate tất cả fields
for key, value in job_data.items():
    if key in item.fields:
        item[key] = value

# Set required fields
item['source'] = 'topcv'
item['crawl_timestamp'] = datetime.utcnow()
item['url'] = response.url
item['http_status'] = response.status
item['raw_data'] = filtered_html  # HTML đã lọc

yield item  # → Đi qua Pipeline
```

---

### Phase 5: Pipeline Processing

**Settings:** `custom_settings['ITEM_PIPELINES']`

#### 5.1. ValidationPipeline (Priority: 100)

**File:** `src/crawlers/common/pipelines.py`

**Chức năng:**
- Validate dữ liệu
- Clean và normalize
- Log errors

#### 5.2. MongoPipeline (Priority: 300)

**File:** `src/crawlers/common/pipelines.py`

**Chức năng:**
- Lưu item vào MongoDB
- Handle duplicates
- Indexing

---

## Sơ Đồ Luồng Hoàn Chỉnh

```
┌──────────────────────────────────────────────────────────────┐
│                    START: scrapy crawl topcv_spider         │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  start_requests()    │
                │  - Tạo request đầu   │
                │    tiên đến list page│
                └──────────┬───────────┘
                           │
                           ▼
            ┌───────────────────────────────┐
            │    parse_job_list()          │
            │  ┌─────────────────────────┐ │
            │  │ 1. Handle encoding      │ │
            │  │ 2. Tìm job items        │ │
            │  │ 3. Parse basic info     │ │
            │  │ 4. Tạo detail requests  │ │
            │  │ 5. Pagination           │ │
            │  └─────────────────────────┘ │
            └───────────┬─────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────┐              ┌───────────────┐
│ Detail Request│              │ Next Page      │
│ (Priority 10) │              │ Request        │
└───────┬───────┘              └───────┬───────┘
        │                               │
        │                               │ (Loop)
        │                               │
        ▼                               │
┌───────────────────────────────┐       │
│   parse_job_detail()          │       │
│  ┌─────────────────────────┐ │       │
│  │ 1. _filter_relevant_html()│ │       │
│  │ 2. Parse từ class cụ thể  │ │       │
│  │    - Title                │ │       │
│  │    - Company              │ │       │
│  │    - Deadline             │ │       │
│  │    - Description          │ │       │
│  │    - Requirements         │ │       │
│  │    - Benefits             │ │       │
│  │    - Location             │ │       │
│  │    - Salary               │ │       │
│  │ 3. Merge list data        │ │       │
│  │ 4. Extract skills         │ │       │
│  │ 5. Validate               │ │       │
│  │ 6. Create Item            │ │       │
│  └─────────────────────────┘ │       │
└───────────┬───────────────────┘       │
            │                           │
            ▼                           │
    ┌───────────────┐                   │
    │ Yield Item    │                   │
    └───────┬───────┘                   │
            │                           │
            ▼                           │
    ┌───────────────┐                   │
    │ Validation    │                   │
    │ Pipeline      │                   │
    └───────┬───────┘                   │
            │                           │
            ▼                           │
    ┌───────────────┐                   │
    │ MongoPipeline │                   │
    │ → MongoDB     │                   │
    └───────────────┘                   │
                                        │
                                        │
            ┌───────────────────────────┘
            │
            ▼
    ┌───────────────┐
    │   CLOSED      │
    │ - Log stats   │
    │ - Summary     │
    └───────────────┘
```

---

## Các Class CSS Selector Được Sử Dụng

### Trang List

| Field | Selector | Mô Tả |
|-------|----------|-------|
| Job Container | `.job-item, .job-list-item, .job-item-search-result` | Container chứa thông tin job |
| URL | `h3.title a::attr(href)` | Link đến trang detail |
| Title | `h3.title a span::text` hoặc `h3.title a::text` | Tên công việc |
| Company | `a.company::text` | Tên công ty |
| Salary | `.title-salary::text` | Lương (raw text) |
| Location | `.address::text` | Địa điểm |
| Posted Date | `.time::text` hoặc `.up-date::text` | Ngày đăng |
| Logo | `a.logo img::attr(src)` | Logo công ty |

### Trang Detail

| Field | Class/ID | Mô Tả |
|-------|----------|-------|
| **Title** | `.job-detail__info--title` | Tên công việc |
| **Company** | `.job-detail__company--information` | Thông tin công ty |
| **Deadline** | `.job-detail__info--deadline-date` | Hạn nộp hồ sơ |
| **Description** | `.job-description__item` (không có `requirement`/`benefit`) | Mô tả công việc |
| **Requirements** | `.job-description__item.job-detail-section.requirement` | Yêu cầu ứng viên |
| **Benefits** | `.job-description__item.job-detail-section.benefit` | Quyền lợi |
| **Location** | `.job-description__item` (phân biệt với description) | Địa điểm làm việc |
| **Salary** | `.box-info-job .job-detail-info-salary .job-detail-info-value` | Lương |
| **Experience** | `.box-info-job .job-detail-info-experience .job-detail-info-value` | Kinh nghiệm |

### HTML Filtering

| Section | ID/Class | Mô Tả |
|---------|----------|-------|
| Header | `#header-job-info` | Chứa title và thông tin cơ bản |
| Detail | `#box-job-information-detail` | Chứa nội dung tuyển dụng |
| Company | `.job-detail__box--right.job-detail__company` | Thông tin công ty |

---

## Các Hàm Xử Lý Dữ Liệu

### 1. `clean_text(text)`

**Mục đích:** Làm sạch text, loại bỏ whitespace thừa

```python
def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)  # Thay nhiều space bằng 1 space
    return text.strip()
```

**Ví dụ:**
- Input: `"  Python    Developer  \n\n  "`
- Output: `"Python Developer"`

### 2. `extract_salary(salary_text)`

**Mục đích:** Parse salary text thành min, max, currency

**Input:** `"10-20 triệu"`  
**Output:**
```python
{
    'raw': '10-20 triệu',
    'min': 10000000,
    'max': 20000000,
    'currency': 'VND'
}
```

**Xử lý:**
- Detect currency (VND/USD)
- Parse multiplier (triệu = 1,000,000)
- Handle "thỏa thuận", "cạnh tranh"

### 3. `parse_date(date_text)`

**Mục đích:** Parse date text thành datetime object

**Input:** `"Cập nhật 2 giờ trước"`  
**Output:** `datetime(2025, 11, 29, 20, 0, 0)`

**Hỗ trợ:**
- Relative dates: "hôm nay", "hôm qua", "2 giờ trước", "3 ngày trước"
- Absolute dates: "DD/MM/YYYY"

### 4. `extract_skills(text)`

**Mục đích:** Tìm skills từ description và requirements

**Input:** `"Tuyển dụng Python Developer, React, MongoDB"`  
**Output:** `['python', 'react', 'mongodb']`

**Cách hoạt động:**
- Tìm keywords trong danh sách skills phổ biến
- Sử dụng word boundary để tránh partial match
- Case-insensitive matching

---

## Cấu Hình Spider

### Custom Settings

```python
custom_settings = {
    'DOWNLOAD_DELAY': 2,              # Delay 2 giây giữa các request
    'CONCURRENT_REQUESTS': 8,          # 8 requests đồng thời
    'ROBOTSTXT_OBEY': True,           # Tuân thủ robots.txt
    'COOKIES_ENABLED': True,          # Bật cookies
    'ITEM_PIPELINES': {
        'src.crawlers.common.pipelines.ValidationPipeline': 100,
        'src.crawlers.common.pipelines.MongoPipeline': 300,
    }
}
```

### Parameters

**Khi chạy spider:**
```bash
scrapy crawl topcv_spider -a max_pages=20 -a incremental=False
```

- `max_pages`: Số trang tối đa cần crawl (default: 10)
- `incremental`: Bật/tắt incremental crawling (default: True)

---

## Error Handling

### 1. Encoding Issues

**Vấn đề:** TopCV có thể trả về HTML nén bằng Brotli  
**Giải pháp:** `_handle_brotli_encoding()`

```python
def _handle_brotli_encoding(self, response):
    try:
        import brotli
        body = brotli.decompress(response.body)
        return HtmlResponse(body=body, encoding='utf-8')
    except:
        return response
```

### 2. Request Failures

**Method:** `errback_httpbin()`

```python
def errback_httpbin(self, failure):
    logger.error(f"Request failed: {failure.request.url}")
    logger.error(f"Error: {failure.value}")
```

### 3. Missing Fields

**Validation:** `validate_job_item()`

```python
if not validate_job_item(job_data):
    logger.warning("Invalid job item, skipping")
    self.stats['jobs_skipped'] += 1
    return
```

### 4. Fallback Selectors

Nếu class mới không tìm thấy, sử dụng fallback selectors:

```python
# Title
if not title_element:
    job['title'] = try_selectors([
        '#header-job-info h1',
        'h1.job-detail-title',
        'h1',
        ...
    ])
```

---

## Statistics & Logging

### Statistics Tracking

```python
self.stats = {
    'pages_crawled': 0,      # Số trang đã crawl
    'jobs_found': 0,         # Số job đã tìm thấy
    'jobs_detailed': 0,      # Số job đã parse chi tiết
    'jobs_skipped': 0       # Số job bị skip
}
```

### Summary Logging

**Method:** `closed(reason)`

```python
def closed(self, reason):
    logger.info(f"Spider closed: {reason}")
    logger.info(
        f"Summary: "
        f"Pages={self.stats['pages_crawled']}, "
        f"Jobs Found={self.stats['jobs_found']}, "
        f"Jobs Detailed={self.stats['jobs_detailed']}, "
        f"Jobs Skipped={self.stats['jobs_skipped']}"
    )
```

---

## Kết Quả Đầu Ra

Mỗi job được lưu vào MongoDB với cấu trúc:

```json
{
    "title": "Python Developer",
    "company": "ABC Company",
    "description": "Mô tả công việc...",
    "requirements": "Yêu cầu ứng viên...",
    "benefits": "Quyền lợi...",
    "location": "Hà Nội",
    "salary_raw": "10-20 triệu",
    "salary_min": 10000000,
    "salary_max": 20000000,
    "salary_currency": "VND",
    "deadline": "2025-12-31T00:00:00",
    "experience": "2-5 năm",
    "skills": ["python", "react", "mongodb"],
    "url": "https://www.topcv.vn/viec-lam/...",
    "source": "topcv",
    "crawl_timestamp": "2025-11-29T10:00:00",
    "http_status": 200,
    "raw_data": "<html>...</html>"
}
```

---

## Tối Ưu Hóa

### 1. HTML Filtering

- **Trước:** HTML ~500KB
- **Sau:** HTML ~50KB
- **Tiết kiệm:** 90% dung lượng

### 2. Priority System

- Detail pages: `priority=10` (xử lý trước)
- List pages: `priority=0` (mặc định)

### 3. Incremental Crawling

- Dừng khi gặp job cũ hơn 24h
- Tiết kiệm tài nguyên

### 4. Concurrent Requests

- 8 requests đồng thời
- Tăng tốc độ crawl

---

## Cách Chạy

### Basic

```bash
cd job_crawler_system
scrapy crawl topcv_spider
```

### Với Parameters

```bash
# Crawl 5 trang đầu tiên (1-2-3-4-5), không incremental
scrapy crawl topcv_spider -a max_pages=5 -a incremental=False

# Crawl với delay 3 giây
scrapy crawl topcv_spider -s DOWNLOAD_DELAY=3

# Crawl tuần tự từng page 1-2-3-4-5
scrapy crawl topcv_spider -a max_pages=5
```

### Full Spider (không incremental)

```bash
scrapy crawl topcv_full_spider -a max_pages=50
```

### URL Structure

Crawler sử dụng URL format với đầy đủ parameters:
```
https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&page=1&saturday_status=0
```

Pagination sẽ tự động update page parameter:
- Page 1: `?type_keyword=1&page=1&saturday_status=0`
- Page 2: `?type_keyword=1&page=2&saturday_status=0`
- Page 3: `?type_keyword=1&page=3&saturday_status=0`
- ...

---

## Troubleshooting

### 1. Không tìm thấy job items

**Nguyên nhân:** CSS selector không đúng  
**Giải pháp:** Kiểm tra HTML structure của TopCV, cập nhật selector

### 2. Encoding errors

**Nguyên nhân:** Brotli compression  
**Giải pháp:** Cài đặt `pip install brotli`

### 3. Missing fields

**Nguyên nhân:** Class CSS thay đổi  
**Giải pháp:** Cập nhật selectors trong `parser.py`

### 4. Rate limiting

**Nguyên nhân:** Request quá nhanh  
**Giải pháp:** Tăng `DOWNLOAD_DELAY` lên 3-5 giây

---

## Tài Liệu Tham Khảo

- **Scrapy Documentation:** https://docs.scrapy.org/
- **TopCV Website:** https://www.topcv.vn/
- **Parser Module:** `src/crawlers/topcv/parser.py`
- **Spider Module:** `src/crawlers/topcv/spider.py`

---

## Changelog

### Version 1.0 (Nov 2025)
- ✅ Implement basic crawling flow
- ✅ HTML filtering optimization
- ✅ Class-based parsing
- ✅ Incremental crawling support
- ✅ Error handling & logging

---

**Tác giả:** Smart Recruitment System Team  
**Cập nhật:** November 2025
