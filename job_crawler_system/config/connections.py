"""
Database Connection Factory Module

Module này cung cấp factory pattern để tạo và quản lý kết nối tới MongoDB.
Sử dụng Singleton pattern để đảm bảo chỉ có một connection pool duy nhất.

Usage:
    from config.connections import get_mongo_client, get_database, get_collection
    
    # Lấy MongoDB client
    client = get_mongo_client()
    
    # Lấy database
    db = get_database()
    
    # Lấy collection cụ thể
    collection = get_collection('job_postings_raw')
"""

import os
import logging
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ConfigurationError
import yaml


logger = logging.getLogger(__name__)


class MongoDBConnectionFactory:
    """
    Singleton Factory class để quản lý MongoDB connections.
    
    Attributes:
        _instance: Singleton instance
        _client: MongoDB client instance
        _config: Configuration dictionary từ settings.yaml
    """
    
    _instance: Optional['MongoDBConnectionFactory'] = None
    _client: Optional[MongoClient] = None
    _config: Optional[dict] = None
    
    def __new__(cls):
        """Implement Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(MongoDBConnectionFactory, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self) -> None:
        """Load configuration từ settings.yaml"""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                'settings.yaml'
            )
            
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
                self._config = full_config.get('mongodb', {})
                
            logger.info("Configuration loaded successfully")
            
        except FileNotFoundError:
            logger.warning("settings.yaml not found, using default configuration")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing settings.yaml: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """Trả về cấu hình mặc định nếu không load được từ file"""
        return {
            'uri': 'mongodb://localhost:27017',
            'database': 'job_crawler_db',
            'collections': {
                'raw_data': 'job_postings_raw',
                'history': 'job_postings_history',
                'logs': 'crawler_logs'
            },
            'max_pool_size': 100,
            'min_pool_size': 10,
            'connection_timeout_ms': 5000,
            'server_selection_timeout_ms': 5000
        }
    
    def get_client(self) -> MongoClient:
        """
        Tạo hoặc trả về MongoDB client instance.
        
        Ưu tiên sử dụng biến môi trường MONGO_URI nếu có,
        nếu không sẽ dùng giá trị từ settings.yaml.
        
        Returns:
            MongoClient: MongoDB client instance
            
        Raises:
            ConnectionFailure: Nếu không thể kết nối tới MongoDB
        """
        if self._client is None:
            try:
                # Ưu tiên lấy URI từ biến môi trường (cho Docker)
                mongo_uri = os.getenv('MONGO_URI', self._config.get('uri'))
                
                # Tạo MongoDB client với connection pool settings
                self._client = MongoClient(
                    mongo_uri,
                    maxPoolSize=self._config.get('max_pool_size', 100),
                    minPoolSize=self._config.get('min_pool_size', 10),
                    connectTimeoutMS=self._config.get('connection_timeout_ms', 5000),
                    serverSelectionTimeoutMS=self._config.get('server_selection_timeout_ms', 5000),
                    # Tùy chọn bổ sung cho production
                    retryWrites=True,
                    retryReads=True,
                )
                
                # Test connection
                self._client.admin.command('ping')
                logger.info(f"Successfully connected to MongoDB at {mongo_uri}")
                
            except ConnectionFailure as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
            except ConfigurationError as e:
                logger.error(f"MongoDB configuration error: {e}")
                raise
        
        return self._client
    
    def get_database(self, db_name: Optional[str] = None) -> Database:
        """
        Trả về MongoDB database instance.
        
        Args:
            db_name: Tên database. Nếu None, sử dụng giá trị từ config.
            
        Returns:
            Database: MongoDB database instance
        """
        client = self.get_client()
        
        # Ưu tiên biến môi trường, sau đó parameter, cuối cùng là config
        database_name = (
            os.getenv('MONGO_DATABASE') or 
            db_name or 
            self._config.get('database', 'job_crawler_db')
        )
        
        return client[database_name]
    
    def get_collection(
        self, 
        collection_name: str, 
        db_name: Optional[str] = None
    ) -> Collection:
        """
        Trả về MongoDB collection instance.
        
        Args:
            collection_name: Tên collection hoặc key trong config
                           (ví dụ: 'raw_data' sẽ map tới 'job_postings_raw')
            db_name: Tên database (optional)
            
        Returns:
            Collection: MongoDB collection instance
        """
        db = self.get_database(db_name)
        
        # Kiểm tra xem collection_name có phải là key trong config không
        collections_config = self._config.get('collections', {})
        actual_collection_name = collections_config.get(
            collection_name, 
            collection_name
        )
        
        return db[actual_collection_name]
    
    def close(self) -> None:
        """Đóng MongoDB connection"""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("MongoDB connection closed")
    
    def get_config(self) -> dict:
        """Trả về configuration dictionary"""
        return self._config.copy()


# Global factory instance
_factory = MongoDBConnectionFactory()


# Convenience functions để sử dụng trực tiếp
def get_mongo_client() -> MongoClient:
    """
    Lấy MongoDB client instance.
    
    Returns:
        MongoClient: MongoDB client
    """
    return _factory.get_client()


def get_database(db_name: Optional[str] = None) -> Database:
    """
    Lấy MongoDB database instance.
    
    Args:
        db_name: Tên database (optional)
        
    Returns:
        Database: MongoDB database
    """
    return _factory.get_database(db_name)


def get_collection(
    collection_name: str, 
    db_name: Optional[str] = None
) -> Collection:
    """
    Lấy MongoDB collection instance.
    
    Args:
        collection_name: Tên collection hoặc key trong config
        db_name: Tên database (optional)
        
    Returns:
        Collection: MongoDB collection
        
    Examples:
        >>> # Sử dụng key từ config
        >>> raw_collection = get_collection('raw_data')
        >>> # Sử dụng tên collection trực tiếp
        >>> custom_collection = get_collection('my_custom_collection')
    """
    return _factory.get_collection(collection_name, db_name)


def close_connection() -> None:
    """Đóng MongoDB connection"""
    _factory.close()


def get_config() -> dict:
    """Lấy MongoDB configuration"""
    return _factory.get_config()


def setup_indexes() -> None:
    """
    Thiết lập các indexes cần thiết cho collections.
    
    Tạo các indexes theo khuyến nghị trong tài liệu:
    - Unique compound index trên (url, source)
    - Text index cho tìm kiếm full-text
    - Hashed index cho content_hash
    - TTL index cho logs (tùy chọn)
    """
    try:
        # Lấy collection
        raw_collection = get_collection('raw_data')
        history_collection = get_collection('history')
        logs_collection = get_collection('logs')
        
        logger.info("Setting up MongoDB indexes...")
        
        # 1. Unique compound index cho raw_data collection
        raw_collection.create_index(
            [("url", 1), ("source", 1)],
            unique=True,
            name="idx_url_source_unique"
        )
        logger.info("Created unique compound index on (url, source)")
        
        # 2. Text index cho tìm kiếm
        raw_collection.create_index(
            [("raw_data.title", "text"), ("raw_data.company", "text")],
            name="idx_text_search"
        )
        logger.info("Created text index for search")
        
        # 3. Hashed index cho content_hash
        raw_collection.create_index(
            [("content_hash", 1)],
            name="idx_content_hash"
        )
        logger.info("Created index on content_hash")
        
        # 4. Index cho crawl_timestamp (để query theo thời gian)
        raw_collection.create_index(
            [("crawl_timestamp", -1)],
            name="idx_crawl_timestamp"
        )
        logger.info("Created index on crawl_timestamp")
        
        # 5. Index cho is_active (để filter dữ liệu active)
        raw_collection.create_index(
            [("metadata.is_active", 1)],
            name="idx_is_active"
        )
        logger.info("Created index on is_active")
        
        # 6. Index cho history collection
        history_collection.create_index(
            [("original_id", 1), ("version_timestamp", -1)],
            name="idx_history_lookup"
        )
        logger.info("Created index on history collection")
        
        # 7. TTL index cho logs (xóa logs sau 30 ngày)
        logs_collection.create_index(
            [("timestamp", 1)],
            expireAfterSeconds=2592000,  # 30 days
            name="idx_logs_ttl"
        )
        logger.info("Created TTL index on logs collection")
        
        logger.info("All indexes created successfully")
        
    except Exception as e:
        logger.error(f"Error setting up indexes: {e}")
        raise


if __name__ == "__main__":
    # Test connection
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    
    try:
        print("Testing MongoDB connection...")
        client = get_mongo_client()
        print(f"✓ Connected successfully")
        
        db = get_config()
        print(f"✓ Database: {db}")
        

        close_connection()
        print("\n✓ Connection closed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)