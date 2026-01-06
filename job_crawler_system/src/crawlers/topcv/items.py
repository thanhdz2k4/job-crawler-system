"""
TopCV Scrapy Items

Định nghĩa cấu trúc dữ liệu cho job postings từ TopCV.
Sử dụng Scrapy Item để đảm bảo tính nhất quán của dữ liệu.

Usage:
    from src.crawlers.topcv.items import JobItem
    
    item = JobItem()
    item['title'] = 'Python Developer'
    item['company'] = 'Tech Corp'
"""

import scrapy
from datetime import datetime


class JobItem(scrapy.Item):
    """
    Item cho job posting từ TopCV.
    
    Fields:
        url: URL đầy đủ của job posting
        title: Tiêu đề công việc
        company: Tên công ty
        company_logo: URL logo công ty (optional)
        salary_raw: Mức lương dạng text gốc (e.g., "10-15 triệu", "Thỏa thuận")
        salary_min: Mức lương tối thiểu (số, VND)
        salary_max: Mức lương tối đa (số, VND)
        salary_currency: Đơn vị tiền tệ (VND, USD)
        location: Địa điểm làm việc
        experience: Kinh nghiệm yêu cầu
        level: Cấp bậc (e.g., "Nhân viên", "Quản lý")
        job_type: Loại hình công việc (Full-time, Part-time, Remote)
        deadline: Hạn nộp hồ sơ
        posted_date: Ngày đăng tin
        description: Mô tả công việc
        requirements: Yêu cầu công việc
        benefits: Phúc lợi
        skills: List các kỹ năng yêu cầu
        industries: List các ngành nghề
        contact_name: Tên người liên hệ
        contact_email: Email liên hệ
        contact_phone: Số điện thoại liên hệ
        raw_html: HTML thô của trang (để parse lại sau này)
        content_hash: Hash của nội dung (để detect changes)
        source: Nguồn dữ liệu (fixed: 'topcv')
        crawl_timestamp: Thời điểm crawl
        last_seen_timestamp: Lần cuối nhìn thấy job này
        http_status: HTTP status code của response
    """
    
    # Core fields
    url = scrapy.Field()
    title = scrapy.Field()
    company = scrapy.Field()
    company_logo = scrapy.Field()
    
    # Salary fields
    salary_raw = scrapy.Field()
    salary_min = scrapy.Field()
    salary_max = scrapy.Field()
    salary_currency = scrapy.Field()
    
    # Job details
    location = scrapy.Field()
    experience = scrapy.Field()
    level = scrapy.Field()
    job_type = scrapy.Field()
    
    # Dates
    deadline = scrapy.Field()
    posted_date = scrapy.Field()
    
    # Long text fields
    description = scrapy.Field()
    requirements = scrapy.Field()
    benefits = scrapy.Field()
    
    # Structured data
    skills = scrapy.Field()  # List[str]
    industries = scrapy.Field()  # List[str]
    
    # Contact info
    contact_name = scrapy.Field()
    contact_email = scrapy.Field()
    contact_phone = scrapy.Field()
    
    # Raw data & metadata
    raw_html = scrapy.Field()
    raw_data = scrapy.Field()  # Dict chứa toàn bộ raw data
    content_hash = scrapy.Field()
    source = scrapy.Field()  # Always 'topcv'
    crawl_timestamp = scrapy.Field()
    last_seen_timestamp = scrapy.Field()
    http_status = scrapy.Field()
    # Pipeline/DB metadata
    _id = scrapy.Field()          # Mongo document id for downstream pipelines (Qdrant)
    db_status = scrapy.Field()    # inserted/updated/unchanged marker from MongoPipeline
    
    def __repr__(self):
        """Representation cho debugging."""
        return f"JobItem(title='{self.get('title', 'N/A')}', company='{self.get('company', 'N/A')}')"


class JobListItem(scrapy.Item):
    """
    Item đơn giản cho danh sách jobs (trang list).
    Dùng để crawl danh sách trước, sau đó crawl chi tiết.
    
    Fields:
        url: URL của job posting detail
        title: Tiêu đề công việc
        company: Tên công ty
        salary_raw: Mức lương text
        location: Địa điểm
        posted_date: Ngày đăng (nếu có)
        is_hot: Job hot/urgent
        is_featured: Job nổi bật
    """
    url = scrapy.Field()
    title = scrapy.Field()
    company = scrapy.Field()
    salary_raw = scrapy.Field()
    location = scrapy.Field()
    posted_date = scrapy.Field()
    is_hot = scrapy.Field()
    is_featured = scrapy.Field()
    source = scrapy.Field()
    # Optional metadata
    _id = scrapy.Field()
    db_status = scrapy.Field()
    
    def __repr__(self):
        return f"JobListItem(url='{self.get('url', 'N/A')}')"
