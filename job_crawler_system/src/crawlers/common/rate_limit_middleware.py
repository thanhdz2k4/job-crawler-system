"""
Rate Limit Middleware

Middleware chuyên xử lý rate limiting (HTTP 429) với exponential backoff.
Thay thế cho Scrapy's default retry để có control tốt hơn.
"""

import time
import logging
from typing import Optional

from scrapy import signals
from scrapy.http import Request, Response
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """
    Middleware để xử lý rate limiting với exponential backoff.
    
    Khi nhận 429, middleware sẽ:
    1. Tăng delay theo công thức: base_delay * (2 ^ retry_count)
    2. Set max delay để không quá lâu
    3. Log chi tiết để debug
    """
    
    def __init__(self, base_delay: int = 60, max_delay: int = 600):
        """
        Initialize middleware.
        
        Args:
            base_delay: Delay ban đầu (giây) - increased to 60s
            max_delay: Delay tối đa (giây) - increased to 600s (10 minutes)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # Track rate limiting per domain
        self.domain_stats = {}
        
        self.stats = {
            'rate_limited': 0,
            'retries_after_backoff': 0,
            'total_delay_added': 0
        }
        
        logger.info(
            f"RateLimitMiddleware initialized: "
            f"base_delay={base_delay}s, max_delay={max_delay}s"
        )
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create from crawler settings."""
        base_delay = crawler.settings.getint('RATE_LIMIT_BASE_DELAY', 60)  # Increased to 60s
        max_delay = crawler.settings.getint('RATE_LIMIT_MAX_DELAY', 600)  # Increased to 600s
        
        middleware = cls(base_delay=base_delay, max_delay=max_delay)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware
    
    def process_response(self, request: Request, response: Response, spider):
        """Process response và handle rate limiting."""
        if response.status == 429:
            self.stats['rate_limited'] += 1
            
            # Extract domain for tracking
            from urllib.parse import urlparse
            domain = urlparse(request.url).netloc
            
            # Initialize domain stats if needed
            if domain not in self.domain_stats:
                self.domain_stats[domain] = {
                    'rate_limited': 0,
                    'last_rate_limit': None
                }
            
            self.domain_stats[domain]['rate_limited'] += 1
            self.domain_stats[domain]['last_rate_limit'] = time.time()
            
            # Get current retry count
            retry_count = request.meta.get('retry_times', 0)
            
            # More aggressive exponential backoff for repeated rate limiting
            # Start with base_delay, double each time, with jitter
            base_multiplier = 2 ** retry_count
            
            # Add domain-specific penalty if this domain has been rate limited recently
            if self.domain_stats[domain]['rate_limited'] > 3:
                base_multiplier *= 1.5  # 50% extra delay for problematic domains
            
            delay = min(self.base_delay * base_multiplier, self.max_delay)
            
            # Add jitter (±20% randomness) to avoid synchronized retries
            import random
            jitter = random.uniform(0.8, 1.2)
            delay = int(delay * jitter)
            
            self.stats['total_delay_added'] += delay
            
            logger.warning(
                f"🚫 Rate limited (429) for {request.url}. "
                f"Domain {domain} has been rate limited {self.domain_stats[domain]['rate_limited']} times. "
                f"Applying {delay}s delay (retry {retry_count + 1}/{spider.settings.getint('RETRY_TIMES', 3)})"
            )
            
            # Create new request with delay
            new_request = request.copy()
            new_request.meta['retry_times'] = retry_count + 1
            new_request.meta['download_delay'] = delay
            new_request.meta['rate_limited'] = True
            new_request.dont_filter = True  # Avoid duplicate filter
            
            # Lower priority for rate-limited requests
            new_request.priority = request.priority - 100
            
            self.stats['retries_after_backoff'] += 1
            
            return new_request
        
        return response
    
    def spider_closed(self, spider):
        """Log statistics khi spider đóng."""
        logger.info(
            f"RateLimitMiddleware stats: "
            f"rate_limited={self.stats['rate_limited']}, "
            f"retries_after_backoff={self.stats['retries_after_backoff']}, "
            f"total_delay_added={self.stats['total_delay_added']}s"
        )
        
        # Log domain-specific stats
        if self.domain_stats:
            logger.info("Domain-specific rate limiting stats:")
            for domain, stats in self.domain_stats.items():
                logger.info(
                    f"  {domain}: rate_limited={stats['rate_limited']}, "
                    f"last_rate_limit={stats['last_rate_limit']}"
                )


if __name__ == "__main__":
    # Test middleware
    print("Testing RateLimitMiddleware...\n")
    
    middleware = RateLimitMiddleware(base_delay=10, max_delay=120)
    print(f"✓ Initialized with base_delay={middleware.base_delay}s, max_delay={middleware.max_delay}s")
    
    # Test exponential backoff calculation
    for retry in range(5):
        delay = min(middleware.base_delay * (2 ** retry), middleware.max_delay)
        print(f"  Retry {retry + 1}: {delay}s delay")
    
    print("\n✓ RateLimitMiddleware test completed!")