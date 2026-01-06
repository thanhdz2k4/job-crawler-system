"""
JobsGo Scrapy Items

Định nghĩa cấu trúc dữ liệu cho job postings từ JobsGo.
Sử dụng chung JobItem với TopCV để đảm bảo tính nhất quán.
"""

from src.crawlers.topcv.items import JobItem, JobListItem

__all__ = ['JobItem', 'JobListItem']
