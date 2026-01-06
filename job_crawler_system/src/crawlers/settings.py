# Scrapy settings for job_crawler_system project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

BOT_NAME = "job_crawler_system"

SPIDER_MODULES = [
    "src.crawlers.topcv",
    "src.crawlers.vietnamworks",
    "src.crawlers.JobsGo",
    "src.crawlers.common",
]
NEWSPIDER_MODULE = "src.crawlers.topcv"

# Load configuration from config modules
try:
    from config import get_setting, get_section
    from config.rate_limiting_config import get_scrapy_settings
    
    # MongoDB settings
    MONGO_URI = get_setting('mongodb.uri', 'mongodb://localhost:27017')
    MONGO_DATABASE = get_setting('mongodb.database', 'job_crawler_db')
    
    # Load rate limiting settings from rate_limiting_config
    rate_limiting_settings = get_scrapy_settings()
    
    # Apply rate limiting settings
    CONCURRENT_REQUESTS = rate_limiting_settings.get('CONCURRENT_REQUESTS', 1)
    DOWNLOAD_DELAY = rate_limiting_settings.get('DOWNLOAD_DELAY', 20)
    DOWNLOAD_TIMEOUT = rate_limiting_settings.get('DOWNLOAD_TIMEOUT', 30)
    RANDOMIZE_DOWNLOAD_DELAY = rate_limiting_settings.get('RANDOMIZE_DOWNLOAD_DELAY', True)
    
    # AutoThrottle settings
    AUTOTHROTTLE_ENABLED = rate_limiting_settings.get('AUTOTHROTTLE_ENABLED', True)
    AUTOTHROTTLE_START_DELAY = rate_limiting_settings.get('AUTOTHROTTLE_START_DELAY', 20)
    AUTOTHROTTLE_MAX_DELAY = rate_limiting_settings.get('AUTOTHROTTLE_MAX_DELAY', 180)
    AUTOTHROTTLE_TARGET_CONCURRENCY = rate_limiting_settings.get('AUTOTHROTTLE_TARGET_CONCURRENCY', 0.2)
    AUTOTHROTTLE_DEBUG = rate_limiting_settings.get('AUTOTHROTTLE_DEBUG', True)
    
    # RateLimitMiddleware settings
    RATE_LIMIT_BASE_DELAY = rate_limiting_settings.get('RATE_LIMIT_BASE_DELAY', 60)
    RATE_LIMIT_MAX_DELAY = rate_limiting_settings.get('RATE_LIMIT_MAX_DELAY', 600)
    
    # User agents from rate limiting config
    USER_AGENTS = rate_limiting_settings.get('USER_AGENTS', [])
    
    # Retry settings
    RETRY_ENABLED = rate_limiting_settings.get('RETRY_ENABLED', True)
    RETRY_TIMES = rate_limiting_settings.get('RETRY_TIMES', 3)
    RETRY_HTTP_CODES = rate_limiting_settings.get('RETRY_HTTP_CODES', [500, 502, 503, 504, 408, 429])
    
    # Proxy settings
    PROXY_ENABLED = rate_limiting_settings.get('PROXY_ENABLED', False)
    PROXY_SERVERS = rate_limiting_settings.get('PROXY_SERVERS', [])

except ImportError:
    # Fallback to default values if config modules not available
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017')
    MONGO_DATABASE = os.environ.get('MONGO_DATABASE', 'job_crawler_db')
    
    # Very conservative to avoid rate limiting
    CONCURRENT_REQUESTS = 1
    DOWNLOAD_DELAY = 20
    DOWNLOAD_TIMEOUT = 30
    RANDOMIZE_DOWNLOAD_DELAY = True
    
    # AutoThrottle settings
    AUTOTHROTTLE_ENABLED = True
    AUTOTHROTTLE_START_DELAY = 20
    AUTOTHROTTLE_MAX_DELAY = 180
    AUTOTHROTTLE_TARGET_CONCURRENCY = 0.2
    AUTOTHROTTLE_DEBUG = True
    
    # RateLimitMiddleware settings
    RATE_LIMIT_BASE_DELAY = 60
    RATE_LIMIT_MAX_DELAY = 600
    
    USER_AGENTS = []
    RETRY_ENABLED = True
    RETRY_TIMES = 3
    RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
    PROXY_ENABLED = False
    PROXY_SERVERS = []

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# USER_AGENT = 'job_crawler_system (+http://www.yourdomain.com)'
# User-Agent will be set by UserAgentRotationMiddleware

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = CONCURRENT_REQUESTS

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = DOWNLOAD_DELAY

# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 1  # Only 1 concurrent request per domain (most conservative)
# CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en,vi',
}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    'src.crawlers.common.middlewares.MySpiderMiddleware': 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    # Disable default UserAgentMiddleware
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    
    # Enable custom middlewares
    'src.crawlers.common.middlewares.UserAgentRotationMiddleware': 400,
    'src.crawlers.common.middlewares.HeadersMiddleware': 410,
    'src.crawlers.common.middlewares.CloudflareBypassMiddleware': 420,
    
    # Rate limiting middleware (high priority to handle 429 before retry)
    'src.crawlers.common.rate_limit_middleware.RateLimitMiddleware': 430,
    
    # Retry middleware
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
    'src.crawlers.common.middlewares.CustomRetryMiddleware': 550,
    
    # Proxy middleware (disabled by default)
    # 'src.crawlers.common.middlewares.ProxyRotationMiddleware': 410,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
EXTENSIONS = {
    'scrapy.extensions.telnet.TelnetConsole': None,
}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    'src.crawlers.common.pipelines.ValidationPipeline': 100,
    'src.crawlers.common.pipelines.DuplicatesPipeline': 200,
    'src.crawlers.common.pipelines.CleaningPipeline': 250,
    'src.crawlers.common.pipelines.MongoPipeline': 300,
    'src.crawlers.common.pipelines.QdrantPipeline': 400,  # Auto-sync to Qdrant
    # 'src.crawlers.common.pipelines.LoggingPipeline': 500,  # Optional
}

# Qdrant Integration Settings
ENABLE_QDRANT = True  # Enable/disable Qdrant sync

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
# These settings are now loaded from rate_limiting_config.py
# AUTOTHROTTLE_ENABLED = AUTOTHROTTLE_ENABLED
# The initial download delay
# AUTOTHROTTLE_START_DELAY = AUTOTHROTTLE_START_DELAY
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = AUTOTHROTTLE_MAX_DELAY
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = AUTOTHROTTLE_TARGET_CONCURRENCY
# Enable showing throttle stats for every response received:
# AUTOTHROTTLE_DEBUG = AUTOTHROTTLE_DEBUG

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
HTTPCACHE_ENABLED = False
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = 'httpcache'
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Retry settings
RETRY_ENABLED = RETRY_ENABLED
RETRY_TIMES = RETRY_TIMES
RETRY_HTTP_CODES = RETRY_HTTP_CODES

# Download timeout
DOWNLOAD_TIMEOUT = DOWNLOAD_TIMEOUT

# Log settings
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

# Feed exports (optional - export to file)
# FEEDS = {
#     'output/jobs_%(time)s.json': {
#         'format': 'json',
#         'encoding': 'utf8',
#         'store_empty': False,
#         'fields': ['url', 'title', 'company', 'salary_raw', 'location'],
#     },
# }

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
