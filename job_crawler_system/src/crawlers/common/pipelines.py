"""
Scrapy Pipelines

Các pipeline để xử lý items sau khi được scraped:
1. ValidationPipeline: Validate dữ liệu
2. CleaningPipeline: Clean và normalize dữ liệu
3. MongoPipeline: Lưu vào MongoDB với versioning
4. QdrantPipeline: Sync vào Qdrant vector database với auto-embedding

Usage:
    Thêm vào settings.py:
    
    ITEM_PIPELINES = {
        'src.crawlers.common.pipelines.ValidationPipeline': 100,
        'src.crawlers.common.pipelines.CleaningPipeline': 200,
        'src.crawlers.common.pipelines.MongoPipeline': 300
    }
"""

import logging
from datetime import datetime
from typing import Dict, Any

try:
    from itemadapter import ItemAdapter
except ImportError:
    # Fallback if itemadapter not available
    class ItemAdapter:
        def __init__(self, item):
            self.item = item
        def get(self, key, default=None):
            return self.item.get(key, default)
        def __getitem__(self, key):
            return self.item[key]
        def __setitem__(self, key, value):
            self.item[key] = value

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """
    Validate items trước khi xử lý tiếp.
    
    Drop items không hợp lệ (thiếu required fields).
    """
    
    def __init__(self):
        self.stats = {
            'valid': 0,
            'invalid': 0
        }
    
    def process_item(self, item, spider):
        """Validate item."""
        adapter = ItemAdapter(item)
        
        # Required fields - RELAXED: only url and source are critical
        required_fields = ['url', 'source']
        
        # Check required fields
        for field in required_fields:
            if not adapter.get(field):
                logger.warning(
                    f"Item missing required field '{field}': {adapter.get('url', 'Unknown')}"
                )
                self.stats['invalid'] += 1
                raise DropItem(f"Missing required field: {field}")
        
        # Warn about missing optional important fields
        optional_important = ['company']
        for field in optional_important:
            if not adapter.get(field):
                logger.debug(f"Item missing optional field '{field}': {adapter.get('url', 'Unknown')}")

        # Hard-required content fields: drop item if any essential field is null/empty
        # STRICT: Must have title, description, requirements, and benefits
        strict_content_validation = True
        if spider and getattr(spider, 'name', ''):
            if spider.name.startswith('vietnamworks'):
                strict_content_validation = False
        
        if strict_content_validation:
            required_fields = ['title', 'description', 'requirements', 'benefits']
            missing_fields = []
            
            for field in required_fields:
                value = adapter.get(field)
                if isinstance(value, str):
                    value = value.strip()
                
                # Check for null, empty, or "N/A" values
                if not value or value == 'N/A' or len(value) < 10:
                    missing_fields.append(field)
            
            # Drop item if any required field is missing
            if missing_fields:
                logger.warning(
                    f"Item missing required fields {missing_fields}, dropping: {adapter.get('url', 'Unknown')}"
                )
                self.stats['invalid'] += 1
                raise DropItem(f"Missing required fields: {', '.join(missing_fields)}")
        else:
            # Relaxed validation for VietnamWorks: only require a non-empty title
            title = adapter.get('title')
            title_text = title.strip() if isinstance(title, str) else title
            if not title_text or title_text == 'N/A':
                logger.warning(
                    f"Item missing required field 'title', dropping: {adapter.get('url', 'Unknown')}"
                )
                self.stats['invalid'] += 1
                raise DropItem("Missing required field: title")
            
            # Warn about missing content fields but do not drop
            content_fields = ['description', 'requirements', 'benefits']
            for field in content_fields:
                value = adapter.get(field)
                if isinstance(value, str):
                    value = value.strip()
                if not value or value == 'N/A' or (isinstance(value, str) and len(value) < 10):
                    logger.debug(
                        f"Item missing content field '{field}': {adapter.get('url', 'Unknown')}"
                    )
        
        # Validate skills extraction for jobs with sufficient content
        # full_text = f"{adapter.get('description', '')} {adapter.get('requirements', '')}"
        # if len(full_text.strip()) >= 50:  # Only check for jobs with meaningful content
        #     skills = adapter.get('skills', [])
        #     skills_extracted = adapter.get('skills_extracted', True)
            
        #     if not skills_extracted or not skills:
        #         logger.warning(
        #             f"Item missing skills despite having sufficient content: {adapter.get('url', 'Unknown')}"
        #         )
        #         self.stats['invalid'] += 1
        #         raise DropItem("Missing skills for job with sufficient content")
        
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


class CleaningPipeline:
    """
    Clean và normalize dữ liệu.
    
    - Trim whitespace
    - Normalize dates
    - Convert data types
    """
    
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


class MongoPipeline:
    """
    Pipeline lưu items vào MongoDB với document versioning.
    
    Sử dụng MongoDBHelper từ src.utils.database để:
    - Upsert items (update hoặc insert)
    - Track document versions
    - Archive old versions to history collection
    """
    
    def __init__(self, mongo_uri=None, mongo_db=None):
        """
        Initialize pipeline.
        
        Args:
            mongo_uri: MongoDB connection URI (từ settings)
            mongo_db: Database name (từ settings)
        """
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
        """
        Create pipeline instance từ crawler settings.
        
        Scrapy sẽ gọi method này để khởi tạo pipeline.
        """
        # Get settings từ crawler hoặc từ config module
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
    
    def open_spider(self, spider):
        """
        Called khi spider mở.
        
        Setup MongoDB connection và helper.
        """
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
    
    def close_spider(self, spider):
        """
        Called khi spider đóng.
        
        Log statistics và cleanup.
        """
        logger.info(
            f"MongoPipeline stats: "
            f"inserted={self.stats['inserted']}, "
            f"updated={self.stats['updated']}, "
            f"unchanged={self.stats['unchanged']}, "
            f"errors={self.stats['errors']}"
        )
        
        # Cleanup nếu cần
        self.helper = None
    
    def process_item(self, item, spider):
        """
        Process và lưu item vào MongoDB.
        
        Args:
            item: Scrapy item
            spider: Spider instance
            
        Returns:
            Item (unchanged)
        """
        try:
            # Convert item to dict
            adapter = ItemAdapter(item)
            job_data = dict(adapter)
            
            # Upsert job using helper
            is_new, doc_id, status = self.helper.upsert_job(
                job_item=job_data,
                hash_fields=['title', 'company', 'salary_raw', 'description', 'requirements']
            )

            # Attach Mongo document id/status for downstream pipelines (e.g., Qdrant)
            if doc_id:
                try:
                    adapter['_id'] = str(doc_id)
                    adapter['db_status'] = status
                except Exception:
                    # Some Item classes lock fields; skip attaching to avoid pipeline break
                    logger.debug("Could not attach _id/db_status to item; continuing with job_data")
            
            # Update statistics
            if status == 'inserted':
                self.stats['inserted'] += 1
                logger.info(f"Inserted new job: {job_data.get('url')}")
            elif status == 'updated':
                self.stats['updated'] += 1
                logger.info(f"Updated job: {job_data.get('url')}")
            elif status == 'unchanged':
                self.stats['unchanged'] += 1
                logger.debug(f"Job unchanged: {job_data.get('url')}")
            
            # _id được gắn thêm để downstream pipeline nhận biết document đã dùng trong MongoDB

            return item
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error processing item: {e}")
            logger.error(f"Item URL: {adapter.get('url', 'Unknown')}")
            
            # Không raise exception để không dừng spider
            # Chỉ log error và tiếp tục
            return item


class DuplicatesPipeline:
    """
    Pipeline để filter duplicate items trong cùng một spider run.
    
    Note: Khác với MongoDB upsert, pipeline này chỉ filter trong memory
    trong cùng một lần chạy spider.
    """
    
    def __init__(self):
        self.urls_seen = set()
        self.stats = {
            'unique': 0,
            'duplicate': 0
        }
    
    def process_item(self, item, spider):
        """Check for duplicates."""
        adapter = ItemAdapter(item)
        url = adapter.get('url')
        
        if url in self.urls_seen:
            self.stats['duplicate'] += 1
            logger.debug(f"Duplicate item found: {url}")
            raise DropItem(f"Duplicate item: {url}")
        else:
            self.urls_seen.add(url)
            self.stats['unique'] += 1
            return item
    
    def close_spider(self, spider):
        """Log statistics."""
        logger.info(
            f"DuplicatesPipeline stats: "
            f"unique={self.stats['unique']}, duplicate={self.stats['duplicate']}"
        )


class LoggingPipeline:
    """
    Pipeline để log items vào collection riêng (crawler_logs).
    
    Useful cho debugging và monitoring.
    """
    
    def __init__(self):
        self.log_collection = None
    
    def open_spider(self, spider):
        """Setup log collection."""
        try:
            from config import get_collection
            self.log_collection = get_collection('logs')
            logger.info("LoggingPipeline initialized")
        except Exception as e:
            logger.warning(f"Could not initialize LoggingPipeline: {e}")
            self.log_collection = None
    
    def process_item(self, item, spider):
        """Log item processing."""
        if not self.log_collection:
            return item
        
        try:
            adapter = ItemAdapter(item)
            
            log_entry = {
                'spider': spider.name,
                'url': adapter.get('url'),
                'title': adapter.get('title'),
                'company': adapter.get('company'),
                'timestamp': datetime.utcnow(),
                'status': 'processed'
            }
            
            self.log_collection.insert_one(log_entry)
            
        except Exception as e:
            logger.error(f"Error logging item: {e}")
        
        return item


class QdrantPipeline:
    """
    Pipeline để sync jobs vào Qdrant vector database với auto-embedding.
    
    Flow:
    1. Nhận item sau khi đã lưu vào MongoDB (cần có _id)
    2. Tạo embedding từ position
    3. Lưu vào Qdrant với payload đầy đủ
    
    Note: Pipeline này nên chạy SAU MongoPipeline để có document ID.
    """
    
    def __init__(self, enable_qdrant: bool = True):
        """
        Initialize Qdrant pipeline.
        
        Args:
            enable_qdrant: Bật/tắt Qdrant sync (từ settings)
        """
        self.enable_qdrant = enable_qdrant
        self.wrapper = None
        
        self.stats = {
            'synced': 0,
            'failed': 0,
            'skipped': 0
        }
    
    @classmethod
    def from_crawler(cls, crawler):
        """
        Create pipeline instance từ crawler settings.
        
        Settings:
            ENABLE_QDRANT: True/False - bật/tắt Qdrant sync
        """
        # Get setting from crawler or config
        enable_qdrant = crawler.settings.getbool('ENABLE_QDRANT', True)
        
        return cls(enable_qdrant=enable_qdrant)
    
    def open_spider(self, spider):
        """
        Setup Qdrant wrapper khi spider bắt đầu.
        """
        if not self.enable_qdrant:
            logger.info("QdrantPipeline disabled by settings")
            return
        
        try:
            from src.utils.qdrant_wrapper import QdrantJobWrapper
            
            self.wrapper = QdrantJobWrapper()
            logger.info("QdrantPipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize QdrantPipeline: {e}")
            logger.warning("Qdrant sync will be disabled for this run")
            self.enable_qdrant = False
            self.wrapper = None
    
    def close_spider(self, spider):
        """Log statistics khi spider kết thúc."""
        if not self.enable_qdrant:
            return
        
        logger.info(
            f"QdrantPipeline stats: "
            f"synced={self.stats['synced']}, "
            f"failed={self.stats['failed']}, "
            f"skipped={self.stats['skipped']}"
        )
        
        self.wrapper = None
    
    def process_item(self, item, spider):
        """
        Process item và sync vào Qdrant.
        
        Note: MongoPipeline gắn _id sau khi upsert MongoDB; Qdrant dùng _id này
        làm point ID. Nếu chạy standalone và không có _id, fallback sang hash URL+source.
        """
        if not self.enable_qdrant or not self.wrapper:
            self.stats['skipped'] += 1
            return item
        
        try:
            adapter = ItemAdapter(item)
            job_data = dict(adapter)
            url = job_data.get('url', '')
            source = job_data.get('source', '')
            
            # Prefer MongoDB _id to align Qdrant IDs với logic dedup của MongoDB
            point_id = job_data.get('_id') or job_data.get('db_id')
            if point_id:
                point_id = str(point_id)
            else:
                # Fallback: deterministic hash từ URL + source (cũ)
                import hashlib
                point_id = hashlib.md5(f"{url}_{source}".encode()).hexdigest()
            
            # Sync to Qdrant
            success = self.wrapper.upsert_job(
                job_id=point_id,
                job_data=job_data
            )
            
            if success:
                self.stats['synced'] += 1
                logger.debug(f"Synced job to Qdrant: {url}")
            else:
                self.stats['failed'] += 1
                logger.warning(f"Failed to sync job to Qdrant: {url}")
            
        except Exception as e:
            self.stats['failed'] += 1
            logger.error(f"Error syncing item to Qdrant: {e}")
            # Don't raise - continue pipeline
        
        return item


# Exception class
class DropItem(Exception):
    """Exception để drop item từ pipeline."""
    pass


if __name__ == "__main__":
    # Test pipelines
    print("Testing Pipelines...\n")
    
    # Mock item
    from scrapy import Item, Field
    
    class TestItem(Item):
        url = Field()
        title = Field()
        company = Field()
        source = Field()
    
    # Test ValidationPipeline
    print("1. Testing ValidationPipeline...")
    pipeline = ValidationPipeline()
    
    # Valid item
    valid_item = TestItem()
    valid_item['url'] = 'https://www.topcv.vn/test'
    valid_item['title'] = 'Test Job'
    valid_item['company'] = 'Test Corp'
    valid_item['source'] = 'topcv'
    
    try:
        result = pipeline.process_item(valid_item, None)
        print("   ✓ Valid item passed")
    except DropItem:
        print("   ✗ Valid item dropped (unexpected)")
    
    # Invalid item (missing title)
    invalid_item = TestItem()
    invalid_item['url'] = 'https://www.topcv.vn/test2'
    invalid_item['company'] = 'Test Corp'
    invalid_item['source'] = 'topcv'
    
    try:
        result = pipeline.process_item(invalid_item, None)
        print("   ✗ Invalid item passed (unexpected)")
    except DropItem:
        print("   ✓ Invalid item dropped correctly")
    
    print("\n✓ Pipeline tests completed!")
