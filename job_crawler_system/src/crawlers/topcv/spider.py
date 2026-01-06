"""
TopCV Spider

Scrapy spider để thu thập dữ liệu việc làm từ TopCV.vn.
Hỗ trợ pagination và incremental crawling.

Usage:
    # Run spider
    scrapy crawl topcv_spider
    
    # With custom settings
    scrapy crawl topcv_spider -s DOWNLOAD_DELAY=3
"""

import scrapy  # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

from .items import JobItem
from .parser import (
    parse_job_detail,
    parse_job_list_item,
    validate_job_item,
)
from scrapy.http import HtmlResponse  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)


class TopCVSpider(scrapy.Spider):
    """
    Spider thu thập dữ liệu từ TopCV.vn.
    
    Chiến lược:
    1. Crawl trang danh sách việc làm (pagination)
    2. Extract URLs của các job postings
    3. Crawl chi tiết từng job posting
    4. Incremental crawling: dừng khi gặp job đã crawl trong 24h gần nhất
    """
    
    name = 'topcv_spider'
    allowed_domains = ['topcv.vn']
    
    # Remove custom_settings to use global settings from settings.py
    # This ensures consistent rate limiting across all spiders
    # custom_settings = {
    #     'DOWNLOAD_DELAY': 2,
    #     'CONCURRENT_REQUESTS': 8,
    #     'ROBOTSTXT_OBEY': True,
    #     'COOKIES_ENABLED': True,
    #     'ITEM_PIPELINES': {
    #         'src.crawlers.common.pipelines.ValidationPipeline': 100,
    #         'src.crawlers.common.pipelines.MongoPipeline': 300,
    #     },
    #     'ENABLE_QDRANT': True,  # Enable Qdrant sync
    # }
    
    def __init__(self, max_pages: int = 10, incremental: bool = True, *args, **kwargs):
        """
        Initialize spider.
        
        Args:
            max_pages: Số trang tối đa cần crawl (default: 10)
            incremental: Bật incremental crawling (default: True)
        """
        super().__init__(*args, **kwargs)
        
        self.max_pages = int(max_pages)
        self.incremental = incremental
        self.stop_crawling = False
        
        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'jobs_found': 0,
            'jobs_detailed': 0,
            'jobs_skipped': 0
        }
        
        # Base URLs with parameters
        self.start_urls = [
            'https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&page=1&saturday_status=0',
        ]
        
        logger.info(
            f"TopCVSpider initialized: "
            f"max_pages={self.max_pages}, incremental={self.incremental}"
        )
    
    def start_requests(self):
        """Generate initial requests."""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_job_list,
                meta={'page': 1},
                errback=self.errback_httpbin,
                dont_filter=True
            )
    
    def _handle_brotli_encoding(self, response):
        """Handle brotli encoding issues."""
        try:
            import brotli
            content_encoding = response.headers.get('Content-Encoding', b'').decode('utf-8').lower()
            
            if 'br' in content_encoding or content_encoding == '':
                try:
                    body = brotli.decompress(response.body)
                    return HtmlResponse(
                        url=response.url,
                        body=body,
                        encoding='utf-8',
                        request=response.request
                    )
                except Exception as br_error:
                    logger.error(f"Brotli decompression failed: {br_error}")
                    return HtmlResponse(
                        url=response.url,
                        body=response.body,
                        encoding='utf-8',
                        request=response.request
                    )
        except ImportError:
            logger.error("brotli module not available, install with: pip install brotli")
        except Exception as decode_error:
            logger.error(f"Failed to decode response: {decode_error}")
        
        return response
    
    def parse_job_list(self, response):
        """
        Parse trang danh sách việc làm.
        
        Extract:
        - Danh sách job URLs
        - Pagination links
        """
        current_page = response.meta.get('page', 1)
        self.stats['pages_crawled'] += 1
        
        logger.info(f"Parsing job list page {current_page}: {response.url}")
        
        # Handle encoding issues
        try:
            if not response.text:
                logger.error(f"Empty response body for {response.url}")
                return
        except (AttributeError, Exception) as e:
            logger.warning(f"Cannot decode response body: {e}")
            response = self._handle_brotli_encoding(response)
            if not response.text:
                return
        
        # Extract job items
        job_selectors = response.css('.job-item, .job-list-item, .job-item-search-result')
        
        if not job_selectors:
            logger.warning(f"No jobs found on page {current_page}")
            return
        
        jobs_on_page = 0
        
        for job_selector in job_selectors:
            if self.stop_crawling:
                logger.info("Stopping crawl due to incremental logic")
                return
            
            # Parse basic info
            job_data = parse_job_list_item(job_selector)
            
            if not job_data.get('url'):
                logger.warning("Job item missing URL, skipping")
                continue
            
            # Make absolute URL
            job_url = urljoin(response.url, job_data['url'])
            jobs_on_page += 1
            self.stats['jobs_found'] += 1
            
            # Check for incremental crawling
            if self.incremental and job_data.get('posted_date'):
                if isinstance(job_data['posted_date'], datetime):
                    age = datetime.now() - job_data['posted_date']
                    if age > timedelta(hours=24):
                        logger.info(f"Job older than 24h, considering stop: {job_url}")
            
            # Request job detail page
            yield scrapy.Request(
                url=job_url,
                callback=self.parse_job_detail,
                meta={'list_data': job_data},
                errback=self.errback_httpbin,
                priority=10
            )
        
        logger.info(f"Found {jobs_on_page} jobs on page {current_page}")
        
        # Pagination
        if current_page < self.max_pages and not self.stop_crawling:
            next_page = self._get_next_page_url(response, current_page)
            
            if next_page:
                logger.info(f"Following to page {current_page + 1}")
                yield scrapy.Request(
                    url=next_page,
                    callback=self.parse_job_list,
                    meta={'page': current_page + 1},
                    errback=self.errback_httpbin
                )
            else:
                logger.info("No more pages found")
    
    def _filter_relevant_html(self, response):
        """
        Lọc HTML để chỉ lấy các phần liên quan:
        - id="header-job-info" - chứa title
        - id="box-job-information-detail" - chứa nội dung tuyển dụng
        - class="job-detail__box--right job-detail__company" - thông tin công ty
        
        Returns:
            HtmlResponse mới chỉ chứa các phần HTML liên quan
        """
        try:
            sections = {
                'header': response.css('#header-job-info').get(),
                'detail': response.css('#box-job-information-detail').get(),
                'company': response.css('.job-detail__box--right.job-detail__company').get()
            }
            
            filtered_parts = [v for v in sections.values() if v]
            
            if not filtered_parts:
                logger.warning(f"No relevant sections found, using full HTML for {response.url}")
                return response
            
            # Create filtered HTML
            filtered_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    {' '.join(filtered_parts)}
</body>
</html>"""
            
            filtered_response = HtmlResponse(
                url=response.url,
                body=filtered_html.encode('utf-8'),
                encoding='utf-8',
                request=response.request
            )
            
            logger.info(
                f"Filtered HTML: {len(filtered_html)} chars "
                f"(original: {len(response.text)} chars)"
            )
            return filtered_response
            
        except Exception as e:
            logger.error(f"Error filtering HTML: {e}, using original response")
            return response
    
    def parse_job_detail(self, response):
        """Parse chi tiết job posting."""
        self.stats['jobs_detailed'] += 1
        logger.info(f"Parsing job detail: {response.url}")
        
        list_data = response.meta.get('list_data', {})
        
        # Filter HTML before parsing
        filtered_response = self._filter_relevant_html(response)
        filtered_html = filtered_response.text if filtered_response != response else response.text
        
        # Parse detail
        job_data = parse_job_detail(filtered_response)
        
        # Check if job_data is None (skill extraction failed)
        if job_data is None:
            logger.warning(f"Job data is None (skill extraction failed), skipping: {response.url}")
            self.stats['jobs_skipped'] += 1
            return
        
        # Merge with list data
        for key, value in list_data.items():
            if key not in job_data or not job_data[key]:
                job_data[key] = value
        
        # Validate
        if not validate_job_item(job_data):
            logger.warning(f"Invalid job item, skipping: {response.url}")
            self.stats['jobs_skipped'] += 1
            return
        
        # REMOVED: Don't skip items without skills - they'll be processed later
        # We want to save the data first, then process skills separately
        # if not job_data.get('skills_extracted', True) and len(job_data.get('description', '') + job_data.get('requirements', '')) >= 50:
        #     logger.warning(f"Skills extraction failed for job with sufficient content, skipping: {response.url}")
        #     self.stats['jobs_skipped'] += 1
        #     return
        
        # Create item
        item = JobItem()
        for key, value in job_data.items():
            if key in item.fields:
                item[key] = value
        
        # Set required fields
        item['source'] = 'topcv'
        item['crawl_timestamp'] = datetime.utcnow()
        item['url'] = response.url
        item['http_status'] = response.status
        
        # Create raw_data dict
        item['raw_data'] = filtered_html
        
        logger.info(
            f"Successfully created item: {item.get('title')} at {item.get('company')} "
            f"with {len(item.get('skills', []))} skills"
        )
        
        yield item
    
    def _get_next_page_url(self, response, current_page: int) -> Optional[str]:
        """
        Extract next page URL từ pagination.
        
        TopCV dùng format: ?type_keyword=1&page=1&saturday_status=0
        Cần update page parameter trong URL có nhiều parameters.
        """
        # Method 1: Tìm link "Next"
        next_link = response.css(
            'a.next::attr(href), '
            'a.pagination-next::attr(href), '
            'li.next a::attr(href)'
        ).get()
        
        if next_link:
            return urljoin(response.url, next_link)
        
        # Method 2: Construct URL với page parameter
        next_page_num = current_page + 1
        
        # Handle URL with multiple parameters
        if 'page=' in response.url:
            # Replace existing page parameter
            import re
            next_url = re.sub(r'page=\d+', f'page={next_page_num}', response.url)
        else:
            # Add page parameter to existing URL
            separator = '&' if '?' in response.url else '?'
            next_url = f"{response.url}{separator}page={next_page_num}"
        
        return next_url
    
    def errback_httpbin(self, failure):
        """Handle request failures."""
        logger.error(f"Request failed: {failure.request.url}")
        logger.error(f"Error: {failure.value}")
    
    def closed(self, reason):
        """Called when spider closes."""
        logger.info(f"Spider closed: {reason}")
        logger.info(
            f"Summary: "
            f"Pages={self.stats['pages_crawled']}, "
            f"Jobs Found={self.stats['jobs_found']}, "
            f"Jobs Detailed={self.stats['jobs_detailed']}, "
            f"Jobs Skipped={self.stats['jobs_skipped']}"
        )


class TopCVFullSpider(TopCVSpider):
    """
    Spider variant để crawl toàn bộ danh sách (không incremental).
    
    Usage:
        scrapy crawl topcv_full_spider -a max_pages=50
    """
    
    name = 'topcv_full_spider'
    
    def __init__(self, *args, **kwargs):
        kwargs['incremental'] = False
        kwargs['max_pages'] = kwargs.get('max_pages', 100)
        super().__init__(*args, **kwargs)


if __name__ == "__main__":
    # Test spider locally
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    
    process = CrawlerProcess(get_project_settings())
    process.crawl(TopCVSpider, max_pages=2)
    process.start()
