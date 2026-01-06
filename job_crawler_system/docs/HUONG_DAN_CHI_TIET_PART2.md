# HƯỚNG DẪN CHI TIẾT - PHẦN 2

## 5. ITEMS MODULE - ĐỊNH NGHĨA CẤU TRÚC DỮ LIỆU

### 5.1 File: `src/crawlers/topcv/items.py`

**Mục đích**: Định nghĩa cấu trúc dữ liệu cho job postings bằng Scrapy Items.

**Tại sao dùng Scrapy Items**:
- ✅ Type definition rõ ràng
- ✅ Validation tự động
- ✅ Serialization/Deserialization
- ✅ IDE auto-completion
- ✅ Documentation built-in

### 5.2 Class: `JobItem`

**Full item cho job posting detail** - Chứa 30+ fields.

#### 5.2.1 Core Fields

```python
class JobItem(scrapy.Item):
    # Core identification
    url = scrapy.Field()              # URL đầy đủ của job posting
    title = scrapy.Field()            # Tiêu đề công việc
    company = scrapy.Field()          # Tên công ty
    company_logo = scrapy.Field()     # URL logo công ty
```

**Ví dụ**:
```python
from src.crawlers.topcv.items import JobItem

item = JobItem()
item['url'] = 'https://www.topcv.vn/viec-lam/python-developer-1234'
item['title'] = 'Python Developer'
item['company'] = 'ABC Technology'
item['company_logo'] = 'https://cdn.topcv.vn/logos/abc-tech.jpg'
```

#### 5.2.2 Salary Fields

```python
salary_raw = scrapy.Field()         # Text gốc: "10-15 triệu", "Thỏa thuận"
salary_min = scrapy.Field()         # Numeric min: 10000000
salary_max = scrapy.Field()         # Numeric max: 15000000
salary_currency = scrapy.Field()    # "VND", "USD"
```

**Ví dụ parsing**:
```python
# Raw text từ website
item['salary_raw'] = '10 - 15 triệu'

# Parsed values (sau khi qua parser)
item['salary_min'] = 10000000    # 10 triệu VND
item['salary_max'] = 15000000    # 15 triệu VND
item['salary_currency'] = 'VND'

# Thỏa thuận case
item['salary_raw'] = 'Thỏa thuận'
item['salary_min'] = None
item['salary_max'] = None
item['salary_currency'] = 'VND'
```

#### 5.2.3 Job Details Fields

```python
location = scrapy.Field()           # "Hà Nội", "TP.HCM", "Remote"
experience = scrapy.Field()         # "1-2 năm", "Không yêu cầu"
level = scrapy.Field()              # "Nhân viên", "Quản lý", "Trưởng phòng"
job_type = scrapy.Field()           # "Full-time", "Part-time", "Remote", "Freelance"
```

**Ví dụ**:
```python
item['location'] = 'Hà Nội, Quận Hoàn Kiếm'
item['experience'] = '2-3 năm kinh nghiệm'
item['level'] = 'Nhân viên chính thức'
item['job_type'] = 'Full-time'
```

#### 5.2.4 Date Fields

```python
deadline = scrapy.Field()           # Hạn nộp hồ sơ: datetime object
posted_date = scrapy.Field()        # Ngày đăng tin: datetime object
```

**Ví dụ**:
```python
from datetime import datetime

item['posted_date'] = datetime(2025, 11, 20, 10, 30, 0)
item['deadline'] = datetime(2025, 12, 20, 23, 59, 59)
```

#### 5.2.5 Long Text Fields

```python
description = scrapy.Field()        # Mô tả công việc (HTML hoặc plain text)
requirements = scrapy.Field()       # Yêu cầu công việc
benefits = scrapy.Field()           # Phúc lợi, quyền lợi
```

**Ví dụ**:
```python
item['description'] = """
Chúng tôi đang tìm kiếm Python Developer có kinh nghiệm để tham gia
dự án phát triển hệ thống backend cho ứng dụng fintech...
"""

item['requirements'] = """
- 2+ năm kinh nghiệm Python
- Thành thạo Django/Flask
- Có kiến thức về SQL, MongoDB
- Am hiểu RESTful API
"""

item['benefits'] = """
- Lương: 15-20 triệu (thỏa thuận theo năng lực)
- Bảo hiểm đầy đủ
- 13th month salary
- Teambuilding hàng quý
"""
```

#### 5.2.6 Structured Data Fields

```python
skills = scrapy.Field()             # List[str] - Danh sách kỹ năng
industries = scrapy.Field()         # List[str] - Danh sách ngành nghề
```

**Ví dụ**:
```python
item['skills'] = [
    'Python',
    'Django',
    'Flask',
    'PostgreSQL',
    'MongoDB',
    'Docker',
    'Redis',
    'Git'
]

item['industries'] = [
    'Công nghệ thông tin',
    'Phần mềm',
    'Fintech'
]
```

#### 5.2.7 Contact Information Fields

```python
contact_name = scrapy.Field()       # Tên người liên hệ
contact_email = scrapy.Field()      # Email liên hệ
contact_phone = scrapy.Field()      # Số điện thoại
```

**Ví dụ**:
```python
item['contact_name'] = 'Ms. Nguyễn Thị A'
item['contact_email'] = 'hr@abctech.com'
item['contact_phone'] = '024 1234 5678'
```

#### 5.2.8 Metadata Fields

```python
raw_html = scrapy.Field()           # HTML thô của trang (để parse lại)
raw_data = scrapy.Field()           # Dict chứa toàn bộ raw data
content_hash = scrapy.Field()       # SHA256 hash của content
source = scrapy.Field()             # Nguồn: 'topcv', 'vietnamworks'
crawl_timestamp = scrapy.Field()    # Thời điểm crawl
last_seen_timestamp = scrapy.Field()# Lần cuối thấy job này
http_status = scrapy.Field()        # HTTP status code (200, 404...)
```

**Ví dụ**:
```python
from datetime import datetime

item['raw_html'] = response.body.decode('utf-8')
item['raw_data'] = {
    'title': 'Python Developer',
    'company': 'ABC Tech',
    # ... all fields as dict
}
item['content_hash'] = 'e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0'
item['source'] = 'topcv'
item['crawl_timestamp'] = datetime.utcnow()
item['http_status'] = 200
```

---

### 5.3 Class: `JobListItem`

**Simplified item cho trang danh sách** - Chỉ chứa thông tin cơ bản.

**Mục đích**: 
- Crawl nhanh danh sách jobs
- Extract URLs để crawl chi tiết sau
- Tiết kiệm bandwidth

```python
class JobListItem(scrapy.Item):
    url = scrapy.Field()              # URL của job detail
    title = scrapy.Field()            # Tiêu đề
    company = scrapy.Field()          # Tên công ty
    salary_raw = scrapy.Field()       # Mức lương text
    location = scrapy.Field()         # Địa điểm
    posted_date = scrapy.Field()      # Ngày đăng
    is_hot = scrapy.Field()           # Job hot/urgent flag
    is_featured = scrapy.Field()      # Job nổi bật flag
    source = scrapy.Field()           # Nguồn dữ liệu
```

**Ví dụ**:
```python
from src.crawlers.topcv.items import JobListItem

list_item = JobListItem()
list_item['url'] = 'https://www.topcv.vn/viec-lam/python-dev-1234'
list_item['title'] = 'Python Developer'
list_item['company'] = 'ABC Tech'
list_item['salary_raw'] = '10-15 triệu'
list_item['location'] = 'Hà Nội'
list_item['is_hot'] = True
list_item['is_featured'] = False
list_item['source'] = 'topcv'
```

---

### 5.4 Usage trong Spider

**2-Step Crawling Strategy**:

```python
# Step 1: Parse list page → JobListItem
def parse_job_list(self, response):
    for job_selector in response.css('.job-item'):
        # Parse basic info
        list_item = parse_job_list_item(job_selector)
        
        # Crawl detail page
        yield scrapy.Request(
            url=list_item['url'],
            callback=self.parse_job_detail,
            meta={'list_item': list_item},  # Pass basic info
            priority=10  # High priority for details
        )

# Step 2: Parse detail page → JobItem (merge với list_item)
def parse_job_detail(self, response):
    # Parse full details
    detail_data = parse_job_detail(response)
    
    # Merge với basic info từ list page
    list_item = response.meta.get('list_item', {})
    
    # Create full JobItem
    item = JobItem()
    
    # From list
    item['url'] = list_item.get('url')
    item['title'] = list_item.get('title')
    item['company'] = list_item.get('company')
    item['salary_raw'] = list_item.get('salary_raw')
    item['location'] = list_item.get('location')
    
    # From detail
    item['description'] = detail_data.get('description')
    item['requirements'] = detail_data.get('requirements')
    item['benefits'] = detail_data.get('benefits')
    item['skills'] = detail_data.get('skills')
    # ...
    
    yield item
```

---

## 6. PARSER MODULE - TRÍCH XUẤT DỮ LIỆU HTML

### 6.1 File: `src/crawlers/topcv/parser.py`

**Mục đích**: Chứa các functions để parse HTML và extract data từ TopCV.

**Tại sao tách parser riêng**:
- ✅ Dễ test độc lập
- ✅ Reusable cho nhiều spiders
- ✅ Dễ maintain khi HTML structure thay đổi
- ✅ Separation of concerns

---

### 6.2 Function: `clean_text()`

**Signature**:
```python
def clean_text(text: Optional[str]) -> str
```

**Mục đích**: Clean text - loại bỏ whitespace thừa, newlines, HTML remnants.

**Ví dụ**:
```python
from src.crawlers.topcv.parser import clean_text

# Input: text với nhiều whitespace
dirty = "  Python   Developer\n\n  Full-time  "
clean = clean_text(dirty)
print(clean)  # "Python Developer Full-time"

# Input: text với HTML entities
dirty = "Salary: &nbsp;&nbsp;10-15 triệu"
clean = clean_text(dirty)
print(clean)  # "Salary: 10-15 triệu"

# Input: None hoặc empty
print(clean_text(None))    # ""
print(clean_text(""))      # ""
print(clean_text("   "))   # ""
```

**Implementation**:
```python
def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    
    # Remove HTML tags remnants
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normalize whitespace (multiple spaces/tabs/newlines → single space)
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    return text.strip()
```

---

### 6.3 Function: `extract_salary()`

**Signature**:
```python
def extract_salary(salary_text: str) -> Dict[str, Any]
```

**Mục đích**: Parse salary text thành min, max, currency.

**Returns**:
```python
{
    'raw': str,        # Text gốc
    'min': float,      # Mức lương min (VND)
    'max': float,      # Mức lương max (VND)
    'currency': str    # 'VND' hoặc 'USD'
}
```

**Ví dụ**:

**Case 1: Range với "triệu"**
```python
result = extract_salary("10 - 15 triệu")
print(result)
# {
#     'raw': '10 - 15 triệu',
#     'min': 10000000,
#     'max': 15000000,
#     'currency': 'VND'
# }
```

**Case 2: Thỏa thuận**
```python
result = extract_salary("Thỏa thuận")
print(result)
# {
#     'raw': 'Thỏa thuận',
#     'min': None,
#     'max': None,
#     'currency': 'VND'
# }
```

**Case 3: USD**
```python
result = extract_salary("$1000 - $2000")
print(result)
# {
#     'raw': '$1000 - $2000',
#     'min': 1000.0,
#     'max': 2000.0,
#     'currency': 'USD'
# }
```

**Case 4: "Up to" / "Đến"**
```python
result = extract_salary("Up to 20 triệu")
print(result)
# {
#     'raw': 'Up to 20 triệu',
#     'min': None,
#     'max': 20000000,
#     'currency': 'VND'
# }
```

**Case 5: Single value (default to min)**
```python
result = extract_salary("Từ 10 triệu")
print(result)
# {
#     'raw': 'Từ 10 triệu',
#     'min': 10000000,
#     'max': None,
#     'currency': 'VND'
# }
```

**Implementation logic**:
```python
def extract_salary(salary_text: str) -> Dict[str, Any]:
    result = {
        'raw': clean_text(salary_text),
        'min': None,
        'max': None,
        'currency': 'VND'
    }
    
    if not salary_text:
        return result
    
    text_lower = salary_text.lower()
    
    # 1. Check negotiable keywords
    if any(k in text_lower for k in ['thỏa thuận', 'thương lượng', 'negotiable']):
        return result
    
    # 2. Detect currency
    multiplier = 1
    if '$' in salary_text or 'usd' in text_lower:
        result['currency'] = 'USD'
    else:
        result['currency'] = 'VND'
        if 'triệu' in text_lower:
            multiplier = 1000000
        elif 'trăm' in text_lower and 'nghìn' in text_lower:
            multiplier = 100000
    
    # 3. Extract numbers
    numbers = re.findall(r'(\d+(?:\.\d+)?)', salary_text)
    
    # 4. Parse min/max
    if len(numbers) >= 2:
        result['min'] = float(numbers[0]) * multiplier
        result['max'] = float(numbers[1]) * multiplier
    elif len(numbers) == 1:
        val = float(numbers[0]) * multiplier
        if any(k in text_lower for k in ['tới', 'đến', 'up to', 'dưới']):
            result['max'] = val
        else:
            result['min'] = val
    
    return result
```

---

### 6.4 Function: `parse_date()`

**Signature**:
```python
def parse_date(date_text: str) -> Optional[datetime]
```

**Mục đích**: Parse Vietnamese date formats thành datetime object.

**Supported formats**:
- Relative: "Hôm nay", "Hôm qua", "X ngày trước", "X giờ trước"
- Absolute: "15/11/2025", "15-11-2025"

**Ví dụ**:

```python
from src.crawlers.topcv.parser import parse_date
from datetime import datetime

# Hôm nay
result = parse_date("Hôm nay")
print(result)  # datetime(2025, 11, 24, ...)

# X ngày trước
result = parse_date("Cập nhật 3 ngày trước")
print(result)  # datetime(2025, 11, 21, ...)

# X giờ trước
result = parse_date("2 giờ trước")
print(result)  # datetime(2025, 11, 24, ...) - 2 hours

# Absolute date
result = parse_date("15/11/2025")
print(result)  # datetime(2025, 11, 15, 0, 0, 0)

# Invalid/Unknown format
result = parse_date("Unknown format")
print(result)  # None
```

**Implementation**:
```python
def parse_date(date_text: str) -> Optional[datetime]:
    if not date_text:
        return None
    
    text = clean_text(date_text.lower())
    now = datetime.now()
    
    # Relative dates
    if 'hôm nay' in text:
        return now
    if 'hôm qua' in text:
        return now - timedelta(days=1)
    
    # Pattern: "X ngày/giờ/phút trước"
    match = re.search(r'(\d+)\s*(giờ|ngày|phút)', text)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'ngày':
            return now - timedelta(days=val)
        elif unit == 'giờ':
            return now - timedelta(hours=val)
        elif unit == 'phút':
            return now - timedelta(minutes=val)
    
    # Absolute dates: DD/MM/YYYY
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
    if match:
        try:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))
            return datetime(year, month, day)
        except ValueError:
            pass
    
    return None
```

---

### 6.5 Function: `extract_skills()`

**Signature**:
```python
def extract_skills(text: str) -> List[str]
```

**Mục đích**: Extract programming skills từ text bằng keyword matching.

**Skills được detect** (50+ skills):
- Languages: Python, Java, JavaScript, TypeScript, C#, PHP, Golang, Ruby
- Frameworks: React, Angular, Vue, Django, Flask, Spring, Laravel
- Databases: SQL, MySQL, PostgreSQL, MongoDB, Redis
- DevOps: Docker, Kubernetes, AWS, Azure, CI/CD, Linux
- Other: Git, Machine Learning, AI, Data Analysis

**Ví dụ**:

```python
from src.crawlers.topcv.parser import extract_skills

# Case 1: Job description
description = """
We are looking for a Python Developer with experience in:
- Django and Flask frameworks
- MongoDB and PostgreSQL databases
- Docker and Kubernetes
- AWS cloud services
"""

skills = extract_skills(description)
print(skills)
# ['python', 'django', 'flask', 'mongodb', 'postgresql', 'docker', 'kubernetes', 'aws']

# Case 2: Requirements section
requirements = """
Yêu cầu:
- 2+ năm kinh nghiệm React, Redux
- Thành thạo TypeScript, JavaScript
- Có kinh nghiệm với Node.js, Express
- Biết sử dụng Git, CI/CD
"""

skills = extract_skills(requirements)
print(skills)
# ['react', 'typescript', 'javascript', 'nodejs', 'git', 'ci/cd']

# Case 3: Skills list
skills_text = "Python, Java, C#, SQL, Docker, Kubernetes, AWS"
skills = extract_skills(skills_text)
print(skills)
# ['python', 'java', 'c#', 'sql', 'docker', 'kubernetes', 'aws']
```

**Implementation**:
```python
def extract_skills(text: str) -> List[str]:
    if not text:
        return []
    
    # Common skills list
    common_skills = [
        'python', 'java', 'javascript', 'typescript', 'c#', '.net',
        'php', 'golang', 'ruby', 'react', 'angular', 'vue', 'nodejs',
        'django', 'flask', 'spring', 'laravel', 'sql', 'mysql',
        'postgresql', 'mongodb', 'redis', 'aws', 'azure', 'docker',
        'kubernetes', 'git', 'linux', 'ci/cd', 'machine learning',
        'ai', 'data analysis', 'excel'
    ]
    
    found = set()
    text_lower = text.lower()
    
    for skill in common_skills:
        # Use word boundary to avoid partial matches
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            found.add(skill)
    
    return list(found)
```

**Lưu ý**:
- Sử dụng word boundary `\b` để tránh match partial (ví dụ: "java" trong "javascript")
- Skills được normalize về lowercase
- Kết quả là set (loại bỏ trùng lặp) rồi convert sang list

---

### 6.6 Function: `parse_job_list_item()`

**Signature**:
```python
def parse_job_list_item(selector: Any) -> Dict[str, Any]
```

**Mục đích**: Parse job item từ trang danh sách (search page).

**Input**: Scrapy selector object (div.job-item-search-result)

**Output**: Dictionary chứa basic job info

**TopCV HTML Structure**:
```html
<div class="job-item-search-result">
    <a class="logo">
        <img src="logo-url.jpg" />
    </a>
    <div class="job-info">
        <h3 class="title">
            <a href="/viec-lam/python-dev-1234">
                <span>Python Developer</span>
            </a>
        </h3>
        <a class="company">ABC Technology</a>
        <div class="title-salary">10 - 15 triệu</div>
        <div class="address">Hà Nội</div>
        <div class="time">Hôm nay</div>
    </div>
    <div class="avatar-hot"></div>  <!-- If job is hot -->
</div>
```

**Ví dụ**:
```python
from src.crawlers.topcv.parser import parse_job_list_item

# Trong spider
def parse_job_list(self, response):
    for job_selector in response.css('.job-item-search-result'):
        # Parse basic info
        job_data = parse_job_list_item(job_selector)
        
        print(job_data)
        # {
        #     'url': '/viec-lam/python-dev-1234',
        #     'title': 'Python Developer',
        #     'company': 'ABC Technology',
        #     'company_logo': 'https://cdn.topcv.vn/logos/abc.jpg',
        #     'salary_raw': '10 - 15 triệu',
        #     'location': 'Hà Nội',
        #     'posted_date': datetime(2025, 11, 24, ...),
        #     'is_hot': True
        # }
```

**Implementation**:
```python
def parse_job_list_item(selector: Any) -> Dict[str, Any]:
    job = {}
    try:
        # 1. URL & Title
        link_tag = selector.css('h3.title a')
        job['url'] = link_tag.css('::attr(href)').get()
        
        title_raw = link_tag.css('span::text').get() or link_tag.css('::text').get()
        job['title'] = clean_text(title_raw)
        
        # 2. Company
        job['company'] = clean_text(selector.css('a.company::text').get())
        
        # 3. Logo
        job['company_logo'] = selector.css('a.logo img::attr(src)').get()
        
        # 4. Salary
        job['salary_raw'] = clean_text(selector.css('.title-salary::text').get())
        
        # 5. Location
        job['location'] = clean_text(selector.css('.address::text').get())
        
        # 6. Posted Date
        date_raw = selector.css('.time::text').get()
        job['posted_date'] = parse_date(date_raw)
        
        # 7. Flags
        job['is_hot'] = bool(selector.css('.avatar-hot').get())
        
        return job
        
    except Exception as e:
        logger.error(f"Error parsing list item: {e}")
        return {}
```

---

### 6.7 Function: `parse_job_detail()`

**Signature**:
```python
def parse_job_detail(response: Any) -> Dict[str, Any]
```

**Mục đích**: Parse chi tiết từ trang job detail.

**Input**: Scrapy response object

**Output**: Dictionary với đầy đủ job details

**TopCV Detail Page Structure**:
```html
<div id="header-job-info">
    <h1 class="job-detail-title">Python Developer</h1>
    <div class="company-title">ABC Technology</div>
</div>

<div class="box-info-job">
    <div class="job-detail-info-salary">
        <div class="job-detail-info-value">10 - 15 triệu</div>
    </div>
    <div class="job-detail-info-address">
        <div class="job-detail-info-value">Hà Nội</div>
    </div>
    <div class="job-detail-info-experience">
        <div class="job-detail-info-value">2-3 năm</div>
    </div>
    <div class="job-detail-info-level">
        <div class="job-detail-info-value">Nhân viên</div>
    </div>
</div>

<div class="job-description">
    <h2>Mô tả công việc</h2>
    <div class="content">...</div>
</div>

<div class="job-requirements">
    <h2>Yêu cầu công việc</h2>
    <div class="content">...</div>
</div>

<div class="job-benefits">
    <h2>Quyền lợi</h2>
    <div class="content">...</div>
</div>
```

**Ví dụ**:
```python
from src.crawlers.topcv.parser import parse_job_detail

# Trong spider
def parse_job_detail(self, response):
    detail_data = parse_job_detail(response)
    
    print(detail_data)
    # {
    #     'title': 'Python Developer',
    #     'company': 'ABC Technology',
    #     'url': 'https://www.topcv.vn/viec-lam/python-dev-1234',
    #     'salary_raw': '10 - 15 triệu',
    #     'salary_min': 10000000,
    #     'salary_max': 15000000,
    #     'salary_currency': 'VND',
    #     'location': 'Hà Nội, Quận Hoàn Kiếm',
    #     'experience': '2-3 năm kinh nghiệm',
    #     'level': 'Nhân viên chính thức',
    #     'job_type': 'Full-time',
    #     'description': 'Full job description...',
    #     'requirements': 'Requirements list...',
    #     'benefits': 'Benefits list...',
    #     'skills': ['python', 'django', 'docker', 'postgresql'],
    #     'contact_name': 'Ms. Nguyễn Thị A',
    #     'contact_email': 'hr@abctech.com',
    #     'http_status': 200
    # }
```

**Implementation** (simplified):
```python
def parse_job_detail(response: Any) -> Dict[str, Any]:
    job = {}
    try:
        # Header section
        header = response.css('#header-job-info')
        job['title'] = clean_text(header.css('h1.job-detail-title::text').get())
        job['company'] = clean_text(header.css('.company-title::text').get())
        job['url'] = response.url
        job['http_status'] = response.status
        
        # Info box
        box = response.css('.box-info-job')
        
        # Salary
        salary_txt = box.css('.job-detail-info-salary .job-detail-info-value::text').get()
        salary_data = extract_salary(salary_txt)
        job.update({
            'salary_raw': salary_data['raw'],
            'salary_min': salary_data['min'],
            'salary_max': salary_data['max'],
            'salary_currency': salary_data['currency']
        })
        
        # Location
        job['location'] = clean_text(
            box.css('.job-detail-info-address .job-detail-info-value::text').get()
        )
        
        # Experience
        job['experience'] = clean_text(
            box.css('.job-detail-info-experience .job-detail-info-value::text').get()
        )
        
        # Level
        job['level'] = clean_text(
            box.css('.job-detail-info-level .job-detail-info-value::text').get()
        )
        
        # Job type
        job['job_type'] = clean_text(
            box.css('.job-detail-info-type .job-detail-info-value::text').get()
        )
        
        # Long text fields
        job['description'] = clean_text(
            response.css('.job-description .content').get()
        )
        
        job['requirements'] = clean_text(
            response.css('.job-requirements .content').get()
        )
        
        job['benefits'] = clean_text(
            response.css('.job-benefits .content').get()
        )
        
        # Extract skills from description + requirements
        combined_text = f"{job.get('description', '')} {job.get('requirements', '')}"
        job['skills'] = extract_skills(combined_text)
        
        # Contact info
        contact = response.css('.contact-box')
        job['contact_name'] = clean_text(contact.css('.contact-name::text').get())
        job['contact_email'] = clean_text(contact.css('.contact-email::text').get())
        job['contact_phone'] = clean_text(contact.css('.contact-phone::text').get())
        
        return job
        
    except Exception as e:
        logger.error(f"Error parsing job detail: {e}")
        return {}
```

---

### 6.8 Function: `validate_job_item()`

**Signature**:
```python
def validate_job_item(job_data: Dict[str, Any]) -> bool
```

**Mục đích**: Validate job item có đủ required fields không.

**Required fields**:
- `url`: Bắt buộc
- `source`: Bắt buộc
- `title`: Khuyến nghị (warning nếu thiếu)
- `company`: Khuyến nghị

**Ví dụ**:
```python
from src.crawlers.topcv.parser import validate_job_item

# Valid item
job1 = {
    'url': 'https://topcv.vn/job-123',
    'source': 'topcv',
    'title': 'Python Developer',
    'company': 'ABC Tech'
}

print(validate_job_item(job1))  # True

# Invalid item (missing URL)
job2 = {
    'source': 'topcv',
    'title': 'Python Developer'
}

print(validate_job_item(job2))  # False

# Valid but incomplete (missing company)
job3 = {
    'url': 'https://topcv.vn/job-123',
    'source': 'topcv',
    'title': 'Python Developer'
}

print(validate_job_item(job3))  # True (with warning log)
```

---

[Tiếp tục trong file tiếp theo...]
