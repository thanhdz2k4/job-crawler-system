# TÀI LIỆU HƯỚNG DẪN - HỆ THỐNG CRAWL DỮ LIỆU VIỆC LÀM

## 📚 GIỚI THIỆU

Bộ tài liệu hướng dẫn chi tiết về hệ thống thu thập dữ liệu việc làm từ TopCV.vn và các trang tuyển dụng khác.

---

## 📖 CẤU TRÚC TÀI LIỆU

Tài liệu được chia thành 4 phần chính:

### [PHẦN 1: Tổng quan & Config](./HUONG_DAN_CHI_TIET.md)
**Nội dung**:
1. Tổng quan Hệ thống
2. Cấu trúc Dự án
3. **Config Module** - Quản lý Cấu hình
   - `config/__init__.py`: Load config functions
   - `config/connections.py`: MongoDB connection factory
   - `config/settings.yaml`: File cấu hình chính
4. **Database Utilities** - Xử lý Dữ liệu MongoDB
   - Content hashing
   - Document versioning
   - Upsert logic với history
   - MongoDBHelper class

**Khi nào đọc**: Setup ban đầu, hiểu cấu trúc hệ thống, cấu hình MongoDB

---

### [PHẦN 2: Items & Parser](./HUONG_DAN_CHI_TIET_PART2.md)
**Nội dung**:
5. **Items Module** - Định nghĩa Cấu trúc Dữ liệu
   - `JobItem`: Full item với 30+ fields
   - `JobListItem`: Simplified item cho list pages
   - Field types và validation
6. **Parser Module** - Trích xuất Dữ liệu HTML
   - `clean_text()`: Clean whitespace
   - `extract_salary()`: Parse salary text
   - `parse_date()`: Parse Vietnamese dates
   - `extract_skills()`: Keyword matching
   - `parse_job_list_item()`: Parse list page
   - `parse_job_detail()`: Parse detail page

**Khi nào đọc**: Implement parser cho source mới, debug parsing issues, customize data extraction

---

### [PHẦN 3: Spider & Pipelines](./HUONG_DAN_CHI_TIET_PART3.md)
**Nội dung**:
7. **Spider Module** - Thu thập Dữ liệu
   - `TopCVSpider`: Main spider với incremental crawling
   - `TopCVFullSpider`: Full crawl variant
   - Pagination handling
   - Request prioritization
   - Error handling
8. **Pipelines Module** - Xử lý Item
   - `ValidationPipeline`: Validate required fields
   - `DuplicatesPipeline`: Filter in-memory duplicates
   - `CleaningPipeline`: Clean & normalize data
   - `MongoPipeline`: Save to MongoDB với versioning
   - `LoggingPipeline`: Log items (optional)

**Khi nào đọc**: Implement spider mới, customize crawling logic, hiểu pipeline flow

---

### [PHẦN 4: Middlewares & Usage](./HUONG_DAN_CHI_TIET_PART4.md)
**Nội dung**:
9. **Middlewares Module** - Tăng cường Spider
   - `UserAgentRotationMiddleware`: Rotate User-Agent
   - `ProxyRotationMiddleware`: Rotate proxies
   - `CustomRetryMiddleware`: Enhanced retry logic
   - `HeadersMiddleware`: Custom headers
10. **Scrapy Settings** - Cấu hình Scrapy
11. **Hướng dẫn Sử dụng**
    - Setup môi trường
    - Configuration
    - Running spiders
    - Testing components
    - Monitoring & logs
12. **Troubleshooting**
    - Common issues
    - Debugging tips
    - Performance tuning

**Khi nào đọc**: Deploy production, optimize performance, debug issues, monitor crawling

---

## 🎯 HƯỚNG DẪN ĐỌC

### Cho Người Mới Bắt đầu

**Lộ trình học**:
1. ✅ Đọc **Phần 1** (Tổng quan & Config) - Hiểu kiến trúc hệ thống
2. ✅ Setup môi trường theo **Phần 4 - Section 11.1**
3. ✅ Chạy spider đơn giản theo **Phần 4 - Section 11.3**
4. ✅ Đọc **Phần 2** (Items & Parser) - Hiểu cách extract data
5. ✅ Đọc **Phần 3** (Spider & Pipelines) - Hiểu flow crawling
6. ✅ Đọc **Phần 4** (Middlewares & Usage) - Advanced topics

**Time estimate**: 3-4 giờ để đọc hiểu toàn bộ

### Cho Developer Có Kinh nghiệm

**Quick start**:
1. Đọc **Phần 1 - Section 3** (Config Module) - 20 phút
2. Đọc **Phần 3 - Section 7** (Spider Module) - 30 phút
3. Đọc **Phần 3 - Section 8** (Pipelines) - 20 phút
4. Tham khảo **Phần 4 - Section 11** (Usage) khi cần

**Time estimate**: 1-2 giờ

### Cho Maintainers

**Reference sections**:
- Config: **Phần 1 - Section 3**
- Database: **Phần 1 - Section 4**
- Parser: **Phần 2 - Section 6**
- Spider: **Phần 3 - Section 7**
- Troubleshooting: **Phần 4 - Section 12**

---

## 🔍 TÌM KIẾM NHANH

### Theo Chủ đề

| Chủ đề | File | Section |
|--------|------|---------|
| Setup MongoDB | Phần 4 | 11.1.2 |
| Configuration | Phần 1 | 3 |
| Content Hashing | Phần 1 | 4.1.1 |
| Document Versioning | Phần 1 | 4.1.3, 4.1.4 |
| Parse Salary | Phần 2 | 6.3 |
| Parse Date | Phần 2 | 6.4 |
| Extract Skills | Phần 2 | 6.5 |
| Spider Implementation | Phần 3 | 7.2 |
| Incremental Crawling | Phần 3 | 7.2.4 |
| Pipeline Flow | Phần 3 | 8 |
| User-Agent Rotation | Phần 4 | 9.2 |
| Proxy Rotation | Phần 4 | 9.3 |
| Run Spider | Phần 4 | 11.3 |
| MongoDB Query | Phần 4 | 11.5.2 |
| Troubleshooting | Phần 4 | 12 |

### Theo Task

| Task | Sections |
|------|----------|
| **Setup từ đầu** | Phần 1 (1-2), Phần 4 (11.1) |
| **Thêm source mới** | Phần 2 (5-6), Phần 3 (7) |
| **Customize parser** | Phần 2 (6) |
| **Debug crawling** | Phần 4 (12.2) |
| **Optimize performance** | Phần 4 (9, 12.3) |
| **Monitor system** | Phần 4 (11.5) |
| **Query data** | Phần 1 (4.2), Phần 4 (11.5.2) |

---

## 💡 EXAMPLES & USE CASES

### Use Case 1: Chạy Crawler Lần Đầu

```bash
# 1. Setup MongoDB
docker run -d -p 27017:27017 --name mongodb mongo:7.0

# 2. Install dependencies
cd job_crawler_system
pip install -r requirements.txt

# 3. Setup indexes
python -c "from config.connections import setup_indexes; setup_indexes()"

# 4. Run spider
scrapy crawl topcv_spider -a max_pages=10
```

**Xem**: Phần 4 - Section 11.1, 11.3

---

### Use Case 2: Thêm Source Mới (VietnamWorks)

**Steps**:
1. Tạo `src/crawlers/vietnamworks/items.py` (copy từ topcv)
2. Tạo `src/crawlers/vietnamworks/parser.py` - customize CSS selectors
3. Tạo `src/crawlers/vietnamworks/spider.py` - inherit từ `TopCVSpider`
4. Update `config/settings.yaml`:
```yaml
sources:
  vietnamworks:
    enabled: true
    base_url: "https://www.vietnamworks.com"
    start_urls:
      - "https://www.vietnamworks.com/tim-viec-lam"
```

**Xem**: Phần 2 (5-6), Phần 3 (7)

---

### Use Case 3: Query Dữ liệu

**Example 1: Get jobs với Python skills**
```python
from config.connections import get_collection

raw_coll = get_collection('raw_data')

python_jobs = raw_coll.find({
    'raw_data.skills': 'python',
    'metadata.is_active': True
})

for job in python_jobs:
    print(f"{job['title']} at {job['company']}")
    print(f"  Salary: {job.get('salary_raw')}")
    print(f"  Location: {job.get('location')}")
```

**Example 2: Track job changes**
```python
from config.connections import get_collection
from bson import ObjectId

history_coll = get_collection('history')

# Get history of a job
job_id = ObjectId('...')
history = history_coll.find({
    'original_id': job_id
}).sort('archived_at', -1)

for version in history:
    print(f"Version {version['metadata']['version']}:")
    print(f"  Archived: {version['archived_at']}")
    print(f"  Title: {version['title']}")
    print(f"  Salary: {version['salary_raw']}")
```

**Xem**: Phần 1 (4.2), Phần 4 (11.5.2)

---

## 📊 COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                     USER COMMANDS                           │
│  scrapy crawl topcv_spider -a max_pages=10                 │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
    ┌──────────┐       ┌──────────┐      ┌──────────┐
    │ Config   │       │ Spider   │      │ MongoDB  │
    │ Loader   │──────▶│ Engine   │─────▶│ Database │
    └──────────┘       └──────────┘      └──────────┘
           │                  │                  │
           │                  ▼                  │
           │           ┌──────────┐              │
           │           │Middleware│              │
           │           │(UA, etc) │              │
           │           └──────────┘              │
           │                  │                  │
           │                  ▼                  │
           │           ┌──────────┐              │
           │           │ Parser   │              │
           │           │ Extract  │              │
           │           └──────────┘              │
           │                  │                  │
           │                  ▼                  │
           │           ┌──────────┐              │
           │           │Pipelines │              │
           │           │Validate/ │              │
           │           │Clean/Save│              │
           │           └──────────┘              │
           │                  │                  │
           └──────────────────┼──────────────────┘
                              ▼
                    ┌──────────────────┐
                    │ Database Utils   │
                    │ Upsert/Version   │
                    └──────────────────┘
```

## 🔄 DATA FLOW (FUNCTION-BY-FUNCTION)

| Bước | Hàm/Phương thức | Nhận dữ liệu từ | Trả dữ liệu cho | Vai trò chính |
|------|-----------------|-----------------|-----------------|----------------|
| 1 | `config.load_settings()` → `Settings._load_settings()` | `config/settings.yaml` + biến môi trường | Bộ nhớ singleton `Settings` | Đọc toàn bộ cấu hình, merge env (`MONGO_URI`, `LOG_LEVEL`, …). |
| 2 | `config.get_setting(key)` | Singleton `Settings` | Spider, middleware, pipeline | Trích giá trị cụ thể (ví dụ `scrapy.user_agents`) để các module dùng runtime. |
| 3 | `config.connections.MongoDBConnectionFactory.get_client()` | Giá trị từ bước 1-2 | `MongoClient` pool | Tạo kết nối MongoDB duy nhất, sẵn sàng cho pipelines/helper. |
| 4 | `TopCVSpider.start_requests()` (`src/crawlers/topcv/spider.py`) | `self.start_urls` (config) | Scrapy scheduler | Bắn các `scrapy.Request` đầu tiên vào hàng đợi.
| 5 | Middleware `UserAgentRotationMiddleware.process_request()` | Request từ bước 4 | Request đã gắn header | Chèn User-Agent, headers, proxy (nếu bật) trước khi rời Scrapy. |
| 6 | `TopCVSpider.parse_job_list(response)` | HTML trang list | `parse_job_list_item()` + Scrapy | Lấy danh sách job sơ bộ, sinh request chi tiết.
| 7 | `parse_job_list_item(selector)` | Selector từng job list | Dict `{url,title,...}` | `parse_job_list` (gắn vào `meta['list_data']`). |
| 8 | `TopCVSpider.parse_job_detail(response)` | HTML trang chi tiết + `list_data` | `parse_job_detail()` và `validate_job_item()` | Hợp nhất dữ liệu danh sách + chi tiết, tạo `JobItem`. |
| 9 | `parse_job_detail(response)` | DOM chi tiết | Dict giàu dữ liệu (title, salary, raw_html, …) | `parse_job_detail` (caller) để map vào `JobItem`. |
| 10 | `ValidationPipeline.process_item(item)` | `JobItem` từ bước 8 | `CleaningPipeline` | Kiểm tra trường bắt buộc (`url`, `source`), URL hợp lệ; raise `DropItem` nếu thiếu. |
| 11 | `CleaningPipeline.process_item(item)` | Item hợp lệ | `MongoPipeline` (hoặc pipelines khác) | Chuẩn hóa text, timestamps, list fields. |
| 12 | `MongoPipeline.process_item(item)` | Item đã clean | `MongoDBHelper.upsert_job()` | Chuyển `ItemAdapter` → dict, gọi helper để ghi DB; cập nhật thống kê `inserted/updated/unchanged`. |
| 13 | `MongoDBHelper.upsert_job()` → `upsert_job_posting()` (`src/utils/database.py`) | Dict job + collection `raw_data/history` | MongoDB `job_postings_raw`, `job_postings_history` | Tính `content_hash`, so sánh với bản cũ. Nếu mới → insert. Nếu khác → `archive_to_history()` rồi update version. Nếu giống → chỉ cập nhật `last_seen_timestamp`. Trả về bộ `(is_new, doc_id, status)` cho pipeline. |
| 14 | `archive_to_history(history_collection, original_doc)` | Document cũ từ bước 13 | Collection `history` | Sao lưu bản cũ với `original_id`, `version_timestamp` giúp truy vết thay đổi. |
| 15 | `MongoPipeline.process_item` (hậu xử lý) | Kết quả từ helper | Logger + Stats | Ghi log `Inserted/Updated/Unchanged`, gắn `_id` vào item để spider khác có thể dùng. |

### Luồng dữ liệu diễn giải

1. **Bootstrap cấu hình**: `load_settings()` nạp file YAML, singleton giữ trong RAM; các lệnh khác (spider, middleware, pipelines) chỉ gọi `get_setting()` để rút phần cần thiết nên tránh IO thừa.
2. **Khởi động crawler**: `start_requests()` tạo request đầu tiên, middleware xếp chồng chỉnh sửa header/proxy trước khi Scrapy gửi ra ngoài.
3. **Thu thập danh sách**: `parse_job_list()` xử lý HTML list, giao `parse_job_list_item()` chịu trách nhiệm bóc từng thẻ DOM → dict đơn giản. Dữ liệu này gói vào `meta['list_data']` theo từng request chi tiết để tái sử dụng.
4. **Phân tích chi tiết**: `parse_job_detail()` dùng parser module để trích mô tả, yêu cầu, lương, kỹ năng; sau đó ghép lại với `list_data` nhằm tránh thiếu trường khi detail không có.
5. **Pipeline xử lý**: Chuỗi pipeline tuần tự nhận `JobItem` và quyết định có bỏ, clean hay giữ nguyên trước khi giao cho Mongo.
6. **Lưu trữ & versioning**: `MongoPipeline` gọi `MongoDBHelper.upsert_job()`; helper lấy document hiện tại (nếu có), tính hash và quyết định insert/update/skip. Khi update có thay đổi nội dung, bản cũ được `archive_to_history()` để duy trì lịch sử.
7. **Kết quả cuối**: `job_postings_raw` giữ snapshot mới nhất (kèm `metadata.version`, `last_seen_timestamp`), `job_postings_history` lưu mọi bản cũ, `crawler_logs` lưu log pipeline nếu bật `LoggingPipeline`.

Nhìn tổng thể, mỗi hàm chỉ nhận loại dữ liệu rõ ràng (config dict, Scrapy request/response, Item dict) và trả kết quả cụ thể cho bước kế tiếp. Điều này giúp truy dấu dễ dàng: muốn biết dữ liệu sai ở đâu chỉ cần xác định hàm nào nhận vào và trả ra bất thường ở chuỗi trên.

---

## 🔧 DEVELOPMENT WORKFLOW

### Workflow 1: Fix Bug trong Parser

1. **Identify issue**: Salary không parse đúng
2. **Read docs**: Phần 2 - Section 6.3 (`extract_salary`)
3. **Write test**:
```python
# test_parser.py
from src.crawlers.topcv.parser import extract_salary

def test_salary_parsing():
    result = extract_salary("Từ 10 triệu")
    assert result['min'] == 10000000
    assert result['max'] is None
```
4. **Fix code** trong `parser.py`
5. **Run test**: `python test_parser.py`
6. **Test với spider**: `scrapy crawl topcv_spider -a max_pages=1 -s LOG_LEVEL=DEBUG`

### Workflow 2: Add New Feature

1. **Plan**: Thêm support cho job deadline
2. **Read docs**: Phần 2 - Section 5 (Items), Section 6 (Parser)
3. **Implement**:
   - Add field to `JobItem`
   - Add parsing logic to `parser.py`
   - Update spider to extract deadline
4. **Test**: `scrapy crawl topcv_spider -a max_pages=2`
5. **Verify DB**:
```bash
mongosh
use job_crawler_db
db.job_postings_raw.findOne({}, {deadline: 1})
```

---

## 📞 SUPPORT & CONTACT

### Báo Lỗi
- Kiểm tra **Phần 4 - Section 12** (Troubleshooting) trước
- Search trong docs (Ctrl+F)
- Check logs: `logs/crawl_*.log`

### Đóng góp
- Fork project
- Đọc docs để hiểu architecture
- Submit pull request với tests

---

## 📝 VERSION HISTORY

### Current: v1.0
- ✅ Core crawling system
- ✅ TopCV spider
- ✅ MongoDB integration
- ✅ Document versioning
- ✅ Complete documentation

### Planned: v1.1
- [ ] VietnamWorks spider
- [ ] ITviec spider
- [ ] Airflow DAGs
- [ ] API endpoints

---

## 🎓 LEARNING RESOURCES

### Prerequisites Knowledge
- **Python**: Basic syntax, OOP, decorators
- **Scrapy**: Official tutorial (https://docs.scrapy.org/en/latest/intro/tutorial.html)
- **MongoDB**: CRUD operations, aggregation
- **HTML/CSS**: Selectors, DOM structure

### Related Topics
- **Web Scraping Ethics**: robots.txt, rate limiting
- **Data Quality**: Validation, cleaning, deduplication
- **Database Design**: Indexing, query optimization
- **System Design**: Architecture patterns, scalability

---

**Tài liệu này là nguồn tham khảo đầy đủ và chi tiết nhất cho hệ thống crawling. Hãy bookmark và reference khi cần!** 🚀
