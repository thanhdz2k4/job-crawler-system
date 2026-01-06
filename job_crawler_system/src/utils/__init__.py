"""
Utils Package

Chứa các tiện ích dùng chung cho toàn bộ hệ thống crawler.
"""

from .database import (
    calculate_content_hash,
    upsert_job_posting,
    archive_to_history,
    get_latest_job_posting,
    is_content_changed,
    MongoDBHelper
)

__all__ = [
    'calculate_content_hash',
    'upsert_job_posting',
    'archive_to_history',
    'get_latest_job_posting',
    'is_content_changed',
    'MongoDBHelper'
]
