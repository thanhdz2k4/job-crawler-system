"""
Rate Limiting Configuration Module

Module này cung cấp các hàm để load và quản lý cấu hình rate limiting
từ file rate_limiting.yaml.
"""

import os
import logging
from typing import Dict, Any, Optional
import yaml

logger = logging.getLogger(__name__)


class RateLimitingConfig:
    """
    Class để quản lý cấu hình rate limiting.
    
    Load cấu hình từ rate_limiting.yaml và cung cấp các phương thức
    để truy cập các thiết lập rate limiting.
    """
    
    _instance: Optional['RateLimitingConfig'] = None
    _config: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        """Implement Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(RateLimitingConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self) -> None:
        """Load configuration từ rate_limiting.yaml"""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                'rate_limiting.yaml'
            )
            
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
                
            logger.info("Rate limiting configuration loaded successfully")
            
        except FileNotFoundError:
            logger.warning("rate_limiting.yaml not found, using default configuration")
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing rate_limiting.yaml: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Trả về cấu hình mặc định nếu không load được từ file"""
        return {
            'global': {
                'download_delay': 20,
                'randomize_download_delay': True,
                'concurrent_requests': 1,
                'concurrent_requests_per_domain': 1
            },
            'autothrottle': {
                'enabled': True,
                'start_delay': 20,
                'max_delay': 180,
                'target_concurrency': 0.2,
                'debug': True
            },
            'rate_limit_middleware': {
                'base_delay': 60,
                'max_delay': 600,
                'max_retry_times': 3
            },
            'domains': {
                'topcv.vn': {
                    'download_delay': 25,
                    'max_delay': 300,
                    'concurrent_requests': 1,
                    'max_pages_per_run': 5
                }
            },
            'retry': {
                'enabled': True,
                'times': 3,
                'http_codes': [500, 502, 503, 504, 408, 429]
            },
            'schedule': {
                'cron': "0 7 * * *",
                'timeout': 3,
                'default_max_pages': 5
            }
        }
    
    def get_global_settings(self) -> Dict[str, Any]:
        """Lấy cấu hình global rate limiting"""
        return self._config.get('global', {})
    
    def get_autothrottle_settings(self) -> Dict[str, Any]:
        """Lấy cấu hình AutoThrottle"""
        return self._config.get('autothrottle', {})
    
    def get_rate_limit_middleware_settings(self) -> Dict[str, Any]:
        """Lấy cấu hình RateLimitMiddleware"""
        return self._config.get('rate_limit_middleware', {})
    
    def get_domain_settings(self, domain: str) -> Dict[str, Any]:
        """
        Lấy cấu hình cho domain cụ thể.
        
        Args:
            domain: Tên domain (ví dụ: 'topcv.vn')
            
        Returns:
            Dict: Cấu hình cho domain đó, hoặc rỗng nếu không có
        """
        domains_config = self._config.get('domains', {})
        return domains_config.get(domain, {})
    
    def get_retry_settings(self) -> Dict[str, Any]:
        """Lấy cấu hình retry"""
        return self._config.get('retry', {})
    
    def get_schedule_settings(self) -> Dict[str, Any]:
        """Lấy cấu hình schedule"""
        return self._config.get('schedule', {})
    
    def get_user_agents(self) -> list:
        """Lấy danh sách user agents"""
        user_agents_config = self._config.get('user_agents', {})
        return user_agents_config.get('agents', [])
    
    def get_proxy_settings(self) -> Dict[str, Any]:
        """Lấy cấu hình proxy"""
        return self._config.get('proxy', {})
    
    def get_scrapy_settings(self, domain: str = None) -> Dict[str, Any]:
        """
        Lấy tất cả cấu hình Scrapy cần thiết cho rate limiting.
        
        Args:
            domain: Tên domain để áp dụng cấu hình đặc biệt (optional)
            
        Returns:
            Dict: Dictionary chứa tất cả settings cho Scrapy
        """
        settings = {}
        
        # Global settings
        global_config = self.get_global_settings()
        settings.update({
            'DOWNLOAD_DELAY': global_config.get('download_delay', 20),
            'RANDOMIZE_DOWNLOAD_DELAY': global_config.get('randomize_download_delay', True),
            'CONCURRENT_REQUESTS': global_config.get('concurrent_requests', 1),
            'CONCURRENT_REQUESTS_PER_DOMAIN': global_config.get('concurrent_requests_per_domain', 1),
        })
        
        # AutoThrottle settings
        autothrottle_config = self.get_autothrottle_settings()
        settings.update({
            'AUTOTHROTTLE_ENABLED': autothrottle_config.get('enabled', True),
            'AUTOTHROTTLE_START_DELAY': autothrottle_config.get('start_delay', 20),
            'AUTOTHROTTLE_MAX_DELAY': autothrottle_config.get('max_delay', 180),
            'AUTOTHROTTLE_TARGET_CONCURRENCY': autothrottle_config.get('target_concurrency', 0.2),
            'AUTOTHROTTLE_DEBUG': autothrottle_config.get('debug', True),
        })
        
        # RateLimitMiddleware settings
        middleware_config = self.get_rate_limit_middleware_settings()
        settings.update({
            'RATE_LIMIT_BASE_DELAY': middleware_config.get('base_delay', 60),
            'RATE_LIMIT_MAX_DELAY': middleware_config.get('max_delay', 600),
        })
        
        # Retry settings
        retry_config = self.get_retry_settings()
        settings.update({
            'RETRY_ENABLED': retry_config.get('enabled', True),
            'RETRY_TIMES': retry_config.get('times', 3),
            'RETRY_HTTP_CODES': retry_config.get('http_codes', [500, 502, 503, 504, 408, 429]),
        })
        
        # Domain-specific settings
        if domain:
            domain_config = self.get_domain_settings(domain)
            if domain_config:
                # Override global settings with domain-specific ones
                if 'download_delay' in domain_config:
                    settings['DOWNLOAD_DELAY'] = domain_config['download_delay']
                if 'concurrent_requests' in domain_config:
                    settings['CONCURRENT_REQUESTS'] = domain_config['concurrent_requests']
                if 'concurrent_requests_per_domain' in domain_config:
                    settings['CONCURRENT_REQUESTS_PER_DOMAIN'] = domain_config['concurrent_requests_per_domain']
        
        # User agents
        user_agents = self.get_user_agents()
        if user_agents:
            settings['USER_AGENTS'] = user_agents
        
        # Proxy settings
        proxy_config = self.get_proxy_settings()
        settings.update({
            'PROXY_ENABLED': proxy_config.get('enabled', False),
            'PROXY_SERVERS': proxy_config.get('servers', []),
        })
        
        return settings
    
    def get_max_pages_for_domain(self, domain: str) -> int:
        """
        Lấy số trang tối đa cho domain.
        
        Args:
            domain: Tên domain
            
        Returns:
            int: Số trang tối đa, hoặc giá trị mặc định từ schedule
        """
        domain_config = self.get_domain_settings(domain)
        if domain_config and 'max_pages_per_run' in domain_config:
            return domain_config['max_pages_per_run']
        
        # Fallback to schedule default
        schedule_config = self.get_schedule_settings()
        return schedule_config.get('default_max_pages', 5)
    
    def get_config(self) -> Dict[str, Any]:
        """Trả về toàn bộ configuration dictionary"""
        return self._config.copy()


# Global instance
_rate_limiting_config = RateLimitingConfig()


def get_rate_limiting_config() -> RateLimitingConfig:
    """Lấy RateLimitingConfig instance"""
    return _rate_limiting_config


def get_scrapy_settings(domain: str = None) -> Dict[str, Any]:
    """
    Lấy tất cả cấu hình Scrapy cần thiết cho rate limiting.
    
    Args:
        domain: Tên domain để áp dụng cấu hình đặc biệt (optional)
        
    Returns:
        Dict: Dictionary chứa tất cả settings cho Scrapy
    """
    return _rate_limiting_config.get_scrapy_settings(domain)


def get_domain_settings(domain: str) -> Dict[str, Any]:
    """
    Lấy cấu hình cho domain cụ thể.
    
    Args:
        domain: Tên domain (ví dụ: 'topcv.vn')
        
    Returns:
        Dict: Cấu hình cho domain đó
    """
    return _rate_limiting_config.get_domain_settings(domain)


def get_max_pages_for_domain(domain: str) -> int:
    """
    Lấy số trang tối đa cho domain.
    
    Args:
        domain: Tên domain
        
    Returns:
        int: Số trang tối đa
    """
    return _rate_limiting_config.get_max_pages_for_domain(domain)


if __name__ == "__main__":
    # Test configuration loading
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    
    try:
        print("Testing rate limiting configuration...")
        
        # Test global settings
        global_settings = get_rate_limiting_config().get_global_settings()
        print(f"✓ Global settings: {global_settings}")
        
        # Test domain settings
        topcv_settings = get_domain_settings('topcv.vn')
        print(f"✓ TopCV settings: {topcv_settings}")
        
        # Test Scrapy settings
        scrapy_settings = get_scrapy_settings('topcv.vn')
        print(f"✓ Scrapy settings for TopCV: {scrapy_settings}")
        
        # Test max pages
        max_pages = get_max_pages_for_domain('topcv.vn')
        print(f"✓ Max pages for TopCV: {max_pages}")
        
        print("\n✓ All tests passed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)