"""
Database Utilities Module

Cung cấp các helper functions để tương tác với MongoDB,
bao gồm document versioning, content hashing, và upsert logic.

Usage:
    from src.utils.database import calculate_content_hash, upsert_job_posting
    
    hash_value = calculate_content_hash(job_data)
    result = upsert_job_posting(collection, job_item)
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pymongo.collection import Collection
from pymongo.results import UpdateResult
from bson import ObjectId

logger = logging.getLogger(__name__)


def calculate_content_hash(
    content: Dict[str, Any],
    fields: Optional[list] = None,
    algorithm: str = 'sha256'
) -> str:
    """
    Tính toán hash của content để phát hiện thay đổi.
    
    Args:
        content: Dictionary chứa dữ liệu cần hash
        fields: List các fields cần hash. Nếu None, hash toàn bộ content.
                Thường dùng: ['title', 'company', 'salary_raw', 'description']
        algorithm: Thuật toán hash ('md5', 'sha256'). Default: sha256
    
    Returns:
        String hash hex
        
    Examples:
        >>> data = {'title': 'Python Dev', 'company': 'ABC Corp'}
        >>> hash_val = calculate_content_hash(data)
        >>> print(hash_val)  # e5d4c3b2a1...
    """
    try:
        # Nếu không chỉ định fields, dùng toàn bộ content
        if fields is None:
            content_to_hash = content
        else:
            # Chỉ lấy các fields được chỉ định
            content_to_hash = {k: content.get(k, '') for k in fields}
        
        # Chuyển thành string có thứ tự (sorted keys)
        content_str = str(sorted(content_to_hash.items()))
        
        # Tính hash
        if algorithm == 'md5':
            hash_obj = hashlib.md5(content_str.encode('utf-8'))
        elif algorithm == 'sha256':
            hash_obj = hashlib.sha256(content_str.encode('utf-8'))
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        return hash_obj.hexdigest()
        
    except Exception as e:
        logger.error(f"Error calculating content hash: {e}")
        # Fallback: return empty hash
        return ""


def is_content_changed(
    old_doc: Dict[str, Any],
    new_content: Dict[str, Any],
    hash_fields: Optional[list] = None
) -> bool:
    """
    Kiểm tra xem content có thay đổi so với document cũ không.
    
    Args:
        old_doc: Document cũ từ database
        new_content: Content mới cần so sánh
        hash_fields: Fields dùng để tính hash
    
    Returns:
        True nếu content thay đổi, False nếu giống nhau
    """
    old_hash = old_doc.get('content_hash', '')
    new_hash = calculate_content_hash(new_content, fields=hash_fields)
    
    return old_hash != new_hash


def archive_to_history(
    history_collection: Collection,
    original_doc: Dict[str, Any]
) -> Optional[ObjectId]:
    """
    Lưu trữ version cũ của document vào history collection.
    
    Args:
        history_collection: MongoDB collection cho history
        original_doc: Document gốc cần archive
    
    Returns:
        ObjectId của document đã insert vào history, hoặc None nếu lỗi
    """
    try:
        # Tạo history document
        history_doc = original_doc.copy()
        
        # Lưu _id gốc
        history_doc['original_id'] = original_doc.get('_id')
        
        # Xóa _id để MongoDB tự tạo _id mới cho history
        if '_id' in history_doc:
            del history_doc['_id']
        
        # Thêm metadata
        history_doc['version_timestamp'] = datetime.utcnow()
        history_doc['archived_at'] = datetime.utcnow()
        
        # Insert vào history collection
        result = history_collection.insert_one(history_doc)
        
        logger.info(
            f"Archived document to history: "
            f"original_id={original_doc.get('_id')}, "
            f"history_id={result.inserted_id}"
        )
        
        return result.inserted_id
        
    except Exception as e:
        logger.error(f"Error archiving document to history: {e}")
        return None


def get_latest_job_posting(
    collection: Collection,
    url: str,
    source: str
) -> Optional[Dict[str, Any]]:
    """
    Lấy job posting mới nhất từ database theo URL và source.
    
    Args:
        collection: MongoDB collection
        url: URL của job posting
        source: Nguồn dữ liệu (e.g., 'topcv', 'vietnamworks')
    
    Returns:
        Document nếu tìm thấy, None nếu không tìm thấy
    """
    try:
        return collection.find_one({'url': url, 'source': source})
    except Exception as e:
        logger.error(f"Error getting latest job posting: {e}")
        return None


def upsert_job_posting(
    raw_collection: Collection,
    history_collection: Collection,
    job_item: Dict[str, Any],
    hash_fields: Optional[list] = None,
    enable_versioning: bool = True
) -> Tuple[bool, Optional[ObjectId], str]:
    """
    Insert hoặc update job posting với document versioning.
    
    Quy trình:
    1. Kiểm tra xem job đã tồn tại chưa (dựa vào url + source)
    2. Nếu chưa tồn tại: Insert mới
    3. Nếu đã tồn tại:
       a. Tính hash của content mới
       b. So sánh với hash cũ
       c. Nếu khác nhau:
          - Lưu version cũ vào history
          - Update document với data mới
          - Tăng version number
       d. Nếu giống nhau:
          - Chỉ update last_seen_timestamp
    
    Args:
        raw_collection: Collection chứa dữ liệu chính
        history_collection: Collection chứa lịch sử
        job_item: Dictionary chứa dữ liệu job posting
        hash_fields: Fields dùng để tính hash (để detect changes)
        enable_versioning: Có lưu history hay không
    
    Returns:
        Tuple (is_new, document_id, status)
        - is_new: True nếu là document mới
        - document_id: ObjectId của document
        - status: 'inserted', 'updated', 'unchanged'
    """
    try:
        url = job_item.get('url')
        source = job_item.get('source')
        
        if not url or not source:
            raise ValueError("Job item must have 'url' and 'source' fields")
        
        # Tính hash cho content mới
        if hash_fields is None:
            # Default fields để detect changes
            hash_fields = ['title', 'company', 'salary_raw', 'description', 'requirements']
        
        # Calculate hash directly from job_item (not raw_data which may not exist)
        new_hash = calculate_content_hash(job_item, fields=hash_fields)
        job_item['content_hash'] = new_hash
        
        # Thêm timestamp
        current_time = datetime.utcnow()
        job_item['last_seen_timestamp'] = current_time
        
        # Kiểm tra document đã tồn tại chưa
        existing_doc = get_latest_job_posting(raw_collection, url, source)
        
        if not existing_doc:
            # Deduplicate by content hash to avoid inserting identical jobs with different URLs
            duplicate_doc = raw_collection.find_one({
                'content_hash': new_hash,
                'source': source
            })
            
            if duplicate_doc:
                duplicate_id = duplicate_doc.get('_id')
                logger.info(
                    f"Duplicate content detected for {url} - "
                    f"reusing existing document {duplicate_id}"
                )
                
                update_fields = {
                    'last_seen_timestamp': current_time,
                    'metadata.is_active': True,
                    'content_hash': new_hash
                }
                
                if duplicate_doc.get('url') != url:
                    alt_urls = duplicate_doc.get('alternate_urls', [])
                    if url not in alt_urls:
                        alt_urls.append(url)
                    update_fields['alternate_urls'] = alt_urls
                
                raw_collection.update_one(
                    {'_id': duplicate_id},
                    {'$set': update_fields}
                )
                
                return False, duplicate_id, 'unchanged'
            
            # === CASE 1: Document mới ===
            job_item['crawl_timestamp'] = current_time
            job_item['metadata'] = {
                'version': 1,
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            }
            
            result = raw_collection.insert_one(job_item)
            
            logger.info(f"Inserted new job posting: {url} from {source}")
            return True, result.inserted_id, 'inserted'
        
        else:
            # === CASE 2: Document đã tồn tại ===
            old_hash = existing_doc.get('content_hash', '')
            
            if old_hash != new_hash:
                # Content thay đổi - Update với versioning
                logger.info(
                    f"Content changed for {url}: "
                    f"old_hash={old_hash[:8]}..., new_hash={new_hash[:8]}..."
                )
                
                # Archive version cũ vào history
                if enable_versioning:
                    archive_to_history(history_collection, existing_doc)
                
                # Update document với data mới
                current_version = existing_doc.get('metadata', {}).get('version', 1)
                job_item['metadata'] = existing_doc.get('metadata', {})
                job_item['metadata']['version'] = current_version + 1
                job_item['metadata']['updated_at'] = current_time
                job_item['metadata']['is_active'] = True
                job_item['crawl_timestamp'] = current_time
                
                raw_collection.update_one(
                    {'_id': existing_doc['_id']},
                    {'$set': job_item}
                )
                
                logger.info(
                    f"Updated job posting: {url} "
                    f"(version {current_version} -> {current_version + 1})"
                )
                return False, existing_doc['_id'], 'updated'
            
            else:
                # Content không đổi - Chỉ update last_seen_timestamp
                raw_collection.update_one(
                    {'_id': existing_doc['_id']},
                    {
                        '$set': {
                            'last_seen_timestamp': current_time,
                            'metadata.is_active': True
                        }
                    }
                )
                
                logger.debug(f"Job posting unchanged: {url}")
                return False, existing_doc['_id'], 'unchanged'
        
    except Exception as e:
        logger.error(f"Error upserting job posting: {e}")
        raise


class MongoDBHelper:
    """
    Helper class để thao tác với MongoDB cho job crawler.
    
    Cung cấp các phương thức high-level để:
    - Upsert job postings với versioning
    - Query job postings
    - Mark jobs as inactive
    - Get statistics
    
    Usage:
        from config import get_collection
        from src.utils.database import MongoDBHelper
        
        helper = MongoDBHelper(
            raw_collection=get_collection('raw_data'),
            history_collection=get_collection('history')
        )
        
        # Upsert job
        is_new, doc_id, status = helper.upsert_job(job_item)
    """
    
    def __init__(
        self,
        raw_collection: Collection,
        history_collection: Collection,
        enable_versioning: bool = True
    ):
        """
        Initialize MongoDB helper.
        
        Args:
            raw_collection: Collection cho dữ liệu chính
            history_collection: Collection cho lịch sử
            enable_versioning: Bật/tắt document versioning
        """
        self.raw_collection = raw_collection
        self.history_collection = history_collection
        self.enable_versioning = enable_versioning
        
        logger.info(
            f"MongoDBHelper initialized: "
            f"raw={raw_collection.name}, "
            f"history={history_collection.name}, "
            f"versioning={enable_versioning}"
        )
    
    def upsert_job(
        self,
        job_item: Dict[str, Any],
        hash_fields: Optional[list] = None
    ) -> Tuple[bool, Optional[ObjectId], str]:
        """
        Upsert job posting (wrapper cho upsert_job_posting function).
        
        Returns:
            Tuple (is_new, document_id, status)
        """
        return upsert_job_posting(
            raw_collection=self.raw_collection,
            history_collection=self.history_collection,
            job_item=job_item,
            hash_fields=hash_fields,
            enable_versioning=self.enable_versioning
        )
    
    def get_job(self, url: str, source: str) -> Optional[Dict[str, Any]]:
        """Lấy job posting theo URL và source."""
        return get_latest_job_posting(self.raw_collection, url, source)
    
    def mark_as_inactive(self, url: str, source: str) -> bool:
        """
        Đánh dấu job posting là inactive (không còn tồn tại trên site).
        
        Args:
            url: URL của job
            source: Nguồn dữ liệu
            
        Returns:
            True nếu thành công
        """
        try:
            result = self.raw_collection.update_one(
                {'url': url, 'source': source},
                {
                    '$set': {
                        'metadata.is_active': False,
                        'metadata.deactivated_at': datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Marked job as inactive: {url}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error marking job as inactive: {e}")
            return False
    
    def get_active_jobs_count(self, source: Optional[str] = None) -> int:
        """
        Đếm số lượng job postings đang active.
        
        Args:
            source: Filter theo source (optional)
            
        Returns:
            Số lượng jobs active
        """
        query = {'metadata.is_active': True}
        if source:
            query['source'] = source
        
        return self.raw_collection.count_documents(query)
    
    def get_statistics(self, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy thống kê về job postings.
        
        Args:
            source: Filter theo source (optional)
            
        Returns:
            Dictionary chứa statistics
        """
        try:
            query = {} if not source else {'source': source}
            
            total_jobs = self.raw_collection.count_documents(query)
            
            active_query = {**query, 'metadata.is_active': True}
            active_jobs = self.raw_collection.count_documents(active_query)
            
            # Latest crawl timestamp
            latest_doc = self.raw_collection.find_one(
                query,
                sort=[('crawl_timestamp', -1)]
            )
            latest_crawl = latest_doc.get('crawl_timestamp') if latest_doc else None
            
            # Version statistics
            pipeline = [
                {'$match': query},
                {
                    '$group': {
                        '_id': None,
                        'avg_version': {'$avg': '$metadata.version'},
                        'max_version': {'$max': '$metadata.version'}
                    }
                }
            ]
            
            version_stats = list(self.raw_collection.aggregate(pipeline))
            avg_version = version_stats[0].get('avg_version', 0) if version_stats else 0
            max_version = version_stats[0].get('max_version', 0) if version_stats else 0
            
            stats = {
                'total_jobs': total_jobs,
                'active_jobs': active_jobs,
                'inactive_jobs': total_jobs - active_jobs,
                'latest_crawl_timestamp': latest_crawl,
                'avg_version': round(avg_version, 2),
                'max_version': max_version,
                'source': source or 'all'
            }
            
            logger.info(f"Statistics: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def get_jobs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        source: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """
        Lấy jobs trong khoảng thời gian.
        
        Args:
            start_date: Ngày bắt đầu
            end_date: Ngày kết thúc
            source: Filter theo source (optional)
            limit: Giới hạn số lượng kết quả
            
        Returns:
            List các job documents
        """
        query = {
            'crawl_timestamp': {
                '$gte': start_date,
                '$lte': end_date
            }
        }
        
        if source:
            query['source'] = source
        
        return list(
            self.raw_collection.find(query)
            .sort('crawl_timestamp', -1)
            .limit(limit)
        )


# Convenience functions để import trực tiếp
def create_helper(
    raw_collection_name: str = 'raw_data',
    history_collection_name: str = 'history',
    enable_versioning: bool = True
) -> MongoDBHelper:
    """
    Tạo MongoDBHelper instance với config mặc định.
    
    Args:
        raw_collection_name: Tên collection chính (key trong config)
        history_collection_name: Tên history collection (key trong config)
        enable_versioning: Bật/tắt versioning
    
    Returns:
        MongoDBHelper instance
    """
    from config import get_collection
    
    return MongoDBHelper(
        raw_collection=get_collection(raw_collection_name),
        history_collection=get_collection(history_collection_name),
        enable_versioning=enable_versioning
    )


if __name__ == "__main__":
    # Test module
    import sys
    from config import setup_logging, get_collection
    
    setup_logging()
    
    print("Testing Database Utils...\n")
    
    # Test 1: Hash calculation
    print("1. Testing hash calculation...")
    test_data = {
        'title': 'Python Developer',
        'company': 'Tech Corp',
        'salary': '1000-2000 USD'
    }
    hash1 = calculate_content_hash(test_data)
    hash2 = calculate_content_hash(test_data)  # Should be same
    print(f"   Hash 1: {hash1[:16]}...")
    print(f"   Hash 2: {hash2[:16]}...")
    print(f"   ✓ Hashes match: {hash1 == hash2}")
    
    # Test 2: MongoDBHelper
    print("\n2. Testing MongoDBHelper...")
    try:
        helper = create_helper()
        print(f"   ✓ Helper created")
        
        # Test statistics
        stats = helper.get_statistics()
        print(f"   ✓ Statistics: {stats}")
        
        print("\n✓ All tests passed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
