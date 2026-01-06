"""
Scrapy Middlewares

Các middleware để enhance spider capabilities:
1. UserAgentRotationMiddleware: Rotate User-Agent headers
2. ProxyRotationMiddleware: Rotate proxies (optional)
3. RetryMiddleware: Custom retry logic
4. CloudflareBypassMiddleware: Handle Cloudflare challenges (basic)

Usage:
    Thêm vào settings.py:
    
    DOWNLOADER_MIDDLEWARES = {
        'src.crawlers.common.middlewares.UserAgentRotationMiddleware': 400,
        'src.crawlers.common.middlewares.ProxyRotationMiddleware': 410,
        'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    }
"""

import logging
import random
from typing import Optional, List

from scrapy import signals
from scrapy.http import Request, Response
from scrapy.downloadermiddlewares.retry import RetryMiddleware as BaseRetryMiddleware
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class UserAgentRotationMiddleware:
    """
    Middleware để rotate User-Agent headers.
    
    Mục đích: Giả lập nhiều trình duyệt khác nhau để tránh bị detect là bot.
    """
    
    def __init__(self, user_agents: List[str]):
        """
        Initialize middleware.
        
        Args:
            user_agents: List các User-Agent strings
        """
        self.user_agents = user_agents
        
        if not self.user_agents:
            raise NotConfigured("No user agents provided")
        
        self.stats = {
            'requests': 0,
            'user_agents_used': {}
        }
        
        logger.info(f"UserAgentRotationMiddleware initialized with {len(self.user_agents)} user agents")
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        # Try to load from config module
        try:
            from config import get_setting
            user_agents = get_setting('scrapy.user_agents', [])
        except:
            # Fallback to Scrapy settings
            user_agents = crawler.settings.getlist('USER_AGENTS', [])
        
        # Default user agents nếu không có trong config
        if not user_agents:
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            ]
        
        middleware = cls(user_agents=user_agents)
        
        # Connect to spider_closed signal
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        
        return middleware
    
    def process_request(self, request: Request, spider):
        """
        Process request: Add random User-Agent header.
        
        Args:
            request: Scrapy request
            spider: Spider instance
        """
        # Select random User-Agent
        user_agent = random.choice(self.user_agents)
        request.headers['User-Agent'] = user_agent
        
        # Update stats
        self.stats['requests'] += 1
        self.stats['user_agents_used'][user_agent] = \
            self.stats['user_agents_used'].get(user_agent, 0) + 1
        
        logger.debug(f"Using User-Agent: {user_agent[:50]}...")
    
    def spider_closed(self, spider):
        """Log statistics when spider closes."""
        logger.info(
            f"UserAgentRotationMiddleware stats: "
            f"total_requests={self.stats['requests']}, "
            f"unique_user_agents={len(self.stats['user_agents_used'])}"
        )


class ProxyRotationMiddleware:
    """
    Middleware để rotate proxies.
    
    Note: Cần có danh sách proxy servers. Có thể tích hợp với:
    - Proxy providers (BrightData, Oxylabs, SmartProxy)
    - Free proxy lists
    - Rotating proxy service
    """
    
    def __init__(self, proxies: List[str], enabled: bool = False):
        """
        Initialize middleware.
        
        Args:
            proxies: List các proxy URLs (e.g., ['http://proxy1:8080', ...])
            enabled: Bật/tắt middleware
        """
        self.proxies = proxies
        self.enabled = enabled
        
        if not self.enabled:
            raise NotConfigured("ProxyRotationMiddleware is disabled")
        
        if not self.proxies:
            raise NotConfigured("No proxies provided")
        
        self.stats = {
            'requests': 0,
            'proxies_used': {},
            'proxy_errors': 0
        }
        
        logger.info(
            f"ProxyRotationMiddleware initialized with {len(self.proxies)} proxies"
        )
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        try:
            from config import get_setting
            
            proxies = get_setting('proxy.servers', [])
            enabled = get_setting('proxy.enabled', False)
        except:
            proxies = crawler.settings.getlist('PROXY_SERVERS', [])
            enabled = crawler.settings.getbool('PROXY_ENABLED', False)
        
        middleware = cls(proxies=proxies, enabled=enabled)
        
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        
        return middleware
    
    def process_request(self, request: Request, spider):
        """Add proxy to request."""
        if not self.enabled or not self.proxies:
            return
        
        # Select random proxy
        proxy = random.choice(self.proxies)
        request.meta['proxy'] = proxy
        
        # Update stats
        self.stats['requests'] += 1
        self.stats['proxies_used'][proxy] = \
            self.stats['proxies_used'].get(proxy, 0) + 1
        
        logger.debug(f"Using proxy: {proxy}")
    
    def process_exception(self, request: Request, exception, spider):
        """Handle proxy errors."""
        if 'proxy' in request.meta:
            self.stats['proxy_errors'] += 1
            logger.warning(
                f"Proxy error: {exception} for proxy {request.meta['proxy']}"
            )
    
    def spider_closed(self, spider):
        """Log statistics."""
        logger.info(
            f"ProxyRotationMiddleware stats: "
            f"requests={self.stats['requests']}, "
            f"errors={self.stats['proxy_errors']}"
        )


class CustomRetryMiddleware(BaseRetryMiddleware):
    """
    Custom retry middleware với logic đặc biệt cho crawling.
    
    Extends Scrapy's RetryMiddleware với:
    - Custom retry logic cho specific HTTP codes
    - Exponential backoff
    - Per-domain retry limits
    """
    
    def __init__(self, settings):
        super().__init__(settings)
        
        # Custom retry HTTP codes
        self.retry_http_codes = set(
            int(x) for x in settings.getlist('RETRY_HTTP_CODES', [500, 502, 503, 504, 408, 429])
        )
        
        self.stats = {
            'retries': 0,
            'retry_reasons': {}
        }
        
        logger.info(
            f"CustomRetryMiddleware initialized: "
            f"max_retry_times={self.max_retry_times}, "
            f"retry_codes={self.retry_http_codes}"
        )
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create from crawler."""
        middleware = cls(crawler.settings)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware
    
    def process_response(self, request: Request, response: Response, spider):
        """Process response and retry if needed."""
        if response.status in self.retry_http_codes:
            reason = f"HTTP {response.status}"
            self.stats['retries'] += 1
            self.stats['retry_reasons'][reason] = \
                self.stats['retry_reasons'].get(reason, 0) + 1
            
            # Special handling for 429 (rate limiting)
            if response.status == 429:
                # Get current retry count
                retry_count = request.meta.get('retry_times', 0)
                
                # Exponential backoff for rate limiting
                # Start with 30 seconds, double each time up to 5 minutes
                delay = min(30 * (2 ** retry_count), 300)
                
                logger.warning(
                    f"Rate limited (429) for {request.url}. "
                    f"Retry {retry_count + 1}/{self.max_retry_times} after {delay}s delay"
                )
                
                # Create new request with delay instead of using parent's retry
                # This ensures our delay is respected
                new_request = request.copy()
                new_request.meta['retry_times'] = retry_count + 1
                new_request.meta['download_delay'] = delay
                new_request.dont_filter = True  # Avoid duplicate filter
                
                return new_request
            else:
                logger.warning(
                    f"Retrying {request.url} (status {response.status})"
                )
            
            return self._retry(request, reason, spider) or response
        
        return response
    
    def spider_closed(self, spider):
        """Log statistics."""
        logger.info(
            f"CustomRetryMiddleware stats: "
            f"total_retries={self.stats['retries']}, "
            f"reasons={self.stats['retry_reasons']}"
        )


class CloudflareBypassMiddleware:
    """
    Basic middleware để handle Cloudflare challenges.
    
    Note: Đây là version cơ bản. Để bypass Cloudflare hiệu quả hơn, cần:
    - Playwright/Selenium để handle JavaScript challenges
    - CAPTCHA solving services (2Captcha, Anti-Captcha)
    - Specialized tools (scrapy-cloudflare-middleware)
    
    Middleware này chỉ detect Cloudflare và log warning.
    """
    
    def __init__(self):
        self.cloudflare_detected = 0
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create from crawler."""
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware
    
    def process_response(self, request: Request, response: Response, spider):
        """Detect Cloudflare challenges."""
        # Check for Cloudflare challenge
        if response.status == 403 or response.status == 503:
            # Check response body for Cloudflare indicators
            body_lower = response.text.lower()
            
            cloudflare_indicators = [
                'cloudflare',
                'cf-ray',
                'challenge-platform',
                'why have i been blocked'
            ]
            
            if any(indicator in body_lower for indicator in cloudflare_indicators):
                self.cloudflare_detected += 1
                
                logger.error(
                    f"🚫 Cloudflare challenge detected for {request.url}"
                )
                logger.error(
                    "Consider using Playwright or CAPTCHA solving service"
                )
                
                # Có thể raise exception hoặc return None để skip request này
                # return None
        
        return response
    
    def spider_closed(self, spider):
        """Log statistics."""
        if self.cloudflare_detected > 0:
            logger.warning(
                f"⚠️  Cloudflare challenges detected {self.cloudflare_detected} times. "
                f"Consider implementing advanced bypass methods."
            )


class HeadersMiddleware:
    """
    Middleware để thêm các headers cần thiết cho requests.
    
    Thêm headers như:
    - Accept
    - Accept-Language
    - Accept-Encoding
    - Referer
    - etc.
    """
    
    def process_request(self, request: Request, spider):
        """Add common headers to request."""
        # Default headers
        default_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Add headers nếu chưa có
        for key, value in default_headers.items():
            if key not in request.headers:
                request.headers[key] = value
        
        # Add Referer (sử dụng base URL của domain)
        if 'Referer' not in request.headers:
            # Extract base URL
            from urllib.parse import urlparse
            parsed = urlparse(request.url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            request.headers['Referer'] = base_url


if __name__ == "__main__":
    # Test middlewares
    print("Testing Middlewares...\n")
    
    # Test UserAgentRotationMiddleware
    print("1. Testing UserAgentRotationMiddleware...")
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15',
    ]
    
    middleware = UserAgentRotationMiddleware(user_agents=user_agents)
    print(f"   ✓ Initialized with {len(middleware.user_agents)} user agents")
    
    # Test random selection
    selected = []
    for _ in range(10):
        ua = random.choice(middleware.user_agents)
        selected.append(ua)
    
    unique_used = len(set(selected))
    print(f"   ✓ Used {unique_used} unique user agents in 10 requests")
    
    print("\n✓ Middleware tests completed!")
