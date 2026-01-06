"""
Configuration Package

Package này cung cấp các tiện ích quản lý cấu hình và kết nối cho Job Crawler System.

Usage:
    from config import load_settings, get_mongo_client, get_collection
    
    # Load settings
    settings = load_settings()
    
    # Get MongoDB connection
    collection = get_collection('raw_data')
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path


# Import các hàm tiện ích từ connections module
from .connections import (
    get_mongo_client,
    get_database,
    get_collection,
    close_connection,
    setup_indexes,
    get_config as get_mongo_config
)


logger = logging.getLogger(__name__)


# Package version
__version__ = "1.0.0"

# Export các hàm chính
__all__ = [
    'load_settings',
    'get_setting',
    'get_mongo_client',
    'get_database',
    'get_collection',
    'close_connection',
    'setup_indexes',
    'get_mongo_config',
    'setup_logging',
    'Settings'
]


class Settings:
    """
    Singleton class để quản lý toàn bộ cấu hình hệ thống.
    
    Attributes:
        _instance: Singleton instance
        _settings: Dictionary chứa toàn bộ cấu hình
    """
    
    _instance: Optional['Settings'] = None
    _settings: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        """Implement Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._load_settings()
        return cls._instance
    
    def _load_settings(self) -> None:
        """Load cấu hình từ settings.yaml"""
        try:
            config_path = Path(__file__).parent / 'settings.yaml'
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self._settings = yaml.safe_load(f)
            
            # Override với biến môi trường nếu có
            self._override_from_env()
            
            logger.info("Settings loaded successfully")
            
        except FileNotFoundError:
            logger.warning("settings.yaml not found, using default settings")
            self._settings = self._get_default_settings()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing settings.yaml: {e}")
            self._settings = self._get_default_settings()
    
    def _override_from_env(self) -> None:
        """
        Override cấu hình từ biến môi trường.
        
        Các biến môi trường sử dụng prefix CRAWLER_
        Ví dụ: CRAWLER_MONGODB_URI, CRAWLER_LOG_LEVEL
        """
        # Override MongoDB URI
        if os.getenv('MONGO_URI'):
            self._settings['mongodb']['uri'] = os.getenv('MONGO_URI')
        
        # Override log level
        if os.getenv('LOG_LEVEL'):
            self._settings['logging']['level'] = os.getenv('LOG_LEVEL')
        
        # Override Docker network
        if os.getenv('DOCKER_NETWORK'):
            self._settings.setdefault('docker', {})['network'] = os.getenv('DOCKER_NETWORK')
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Trả về cấu hình mặc định"""
        return {
            'mongodb': {
                'uri': 'mongodb://localhost:27017',
                'database': 'job_crawler_db',
            },
            'logging': {
                'level': 'INFO',
            },
            'scrapy': {
                'concurrent_requests': 16,
                'download_delay': 2,
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Lấy giá trị cấu hình theo đường dẫn (dot notation).
        
        Args:
            key_path: Đường dẫn đến cấu hình, ví dụ: 'mongodb.uri'
            default: Giá trị mặc định nếu không tìm thấy
            
        Returns:
            Giá trị cấu hình hoặc giá trị mặc định
            
        Examples:
            >>> settings = Settings()
            >>> mongo_uri = settings.get('mongodb.uri')
            >>> delay = settings.get('scrapy.download_delay', 2)
        """
        keys = key_path.split('.')
        value = self._settings
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Lấy toàn bộ một section cấu hình.
        
        Args:
            section: Tên section (ví dụ: 'mongodb', 'scrapy')
            
        Returns:
            Dictionary chứa cấu hình của section
        """
        return self._settings.get(section, {}).copy()
    
    def all(self) -> Dict[str, Any]:
        """Trả về toàn bộ cấu hình"""
        return self._settings.copy()
    
    def reload(self) -> None:
        """Tải lại cấu hình từ file"""
        self._load_settings()
        logger.info("Settings reloaded")


# Global settings instance
_settings = Settings()


def load_settings(force_reload: bool = False) -> Dict[str, Any]:
    """
    Load toàn bộ cấu hình từ settings.yaml.
    
    Args:
        force_reload: Có buộc tải lại cấu hình không
        
    Returns:
        Dictionary chứa toàn bộ cấu hình
    """
    if force_reload:
        _settings.reload()
    return _settings.all()


def get_setting(key_path: str, default: Any = None) -> Any:
    """
    Lấy một giá trị cấu hình cụ thể.
    
    Args:
        key_path: Đường dẫn đến cấu hình (dot notation)
        default: Giá trị mặc định
        
    Returns:
        Giá trị cấu hình
        
    Examples:
        >>> from config import get_setting
        >>> mongo_uri = get_setting('mongodb.uri')
        >>> max_pages = get_setting('sources.topcv.max_pages', 50)
    """
    return _settings.get(key_path, default)


def get_section(section: str) -> Dict[str, Any]:
    """
    Lấy toàn bộ một section cấu hình.
    
    Args:
        section: Tên section
        
    Returns:
        Dictionary chứa cấu hình của section
    """
    return _settings.get_section(section)


def setup_logging() -> None:
    """
    Thiết lập logging cho hệ thống dựa trên cấu hình.
    
    Cấu hình logging bao gồm:
    - Console logging
    - File logging (nếu enabled)
    - MongoDB logging (nếu enabled)
    """
    log_config = get_section('logging')
    
    # Basic configuration
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_format = log_config.get('format', '%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[]
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(console_handler)
    
    # File handler (nếu enabled)
    if log_config.get('file_enabled', False):
        from logging.handlers import RotatingFileHandler
        
        log_file = log_config.get('file_path', 'logs/crawler.log')
        
        # Tạo thư mục logs nếu chưa tồn tại
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=log_config.get('file_max_bytes', 10485760),
            backupCount=log_config.get('file_backup_count', 5)
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
        
        logger.info(f"File logging enabled: {log_file}")
    
    logger.info(f"Logging configured at {log_config.get('level', 'INFO')} level")


def validate_config() -> bool:
    """
    Validate cấu hình hệ thống.
    
    Kiểm tra các cấu hình bắt buộc và tính hợp lệ của giá trị.
    
    Returns:
        True nếu cấu hình hợp lệ, False nếu không
    """
    try:
        settings = load_settings()
        
        # Kiểm tra MongoDB config
        if 'mongodb' not in settings:
            logger.error("Missing 'mongodb' configuration")
            return False
        
        # Kiểm tra Scrapy config
        if 'scrapy' not in settings:
            logger.error("Missing 'scrapy' configuration")
            return False
        
        # Kiểm tra sources config
        if 'sources' not in settings:
            logger.error("Missing 'sources' configuration")
            return False
        
        # Kiểm tra ít nhất 1 source được enabled
        sources = settings.get('sources', {})
        enabled_sources = [name for name, config in sources.items() if config.get('enabled', False)]
        
        if not enabled_sources:
            logger.error("No sources enabled in configuration")
            return False
        
        logger.info(f"Configuration validated successfully. Enabled sources: {', '.join(enabled_sources)}")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    # Test configuration loading
    import sys
    
    setup_logging()
    
    print("Testing configuration...\n")
    
    # Load settings
    settings = load_settings()
    print(f"✓ Settings loaded: {len(settings)} sections")
    
    # Test get_setting
    mongo_uri = get_setting('mongodb.uri')
    print(f"✓ MongoDB URI: {mongo_uri}")
    
    # Test get_section
    scrapy_config = get_section('scrapy')
    print(f"✓ Scrapy config: {len(scrapy_config)} settings")
    
    # Validate config
    print("\nValidating configuration...")
    if validate_config():
        print("✓ Configuration is valid")
    else:
        print("✗ Configuration validation failed")
        sys.exit(1)
    
    print("\n✓ All tests passed!")