"""
VietnamWorks Spider

Scrapy spider để thu thập dữ liệu việc làm từ VietnamWorks.com.
Hỗ trợ pagination và incremental crawling.

Usage:
    # Run spider
    scrapy crawl vietnamworks_spider
    
    # With custom settings
    scrapy crawl vietnamworks_spider -s DOWNLOAD_DELAY=3
"""

import scrapy
from datetime import datetime, timedelta
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

from .items import JobItem
from .parser import (
    parse_job_detail,
    parse_job_list_item,
    validate_job_item,
    parse_next_f_data,
    parse_job_list_from_next_f,
    map_parsed_data_to_job_item,
)
from scrapy.http import HtmlResponse

logger = logging.getLogger(__name__)


class VietnamWorksSpider(scrapy.Spider):
    """
    Spider thu thập dữ liệu từ VietnamWorks.com.
    
    Chiến lược:
    1. Crawl trang danh sách việc làm (pagination)
    2. Extract URLs của các job postings
    3. Crawl chi tiết từng job posting
    4. Incremental crawling: dừng khi gặp job đã crawl trong 24h gần nhất
    """
    
    name = 'vietnamworks_spider'
    allowed_domains = ['vietnamworks.com']
    
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS': 8,
        'ROBOTSTXT_OBEY': True,
        'COOKIES_ENABLED': True,
        'ITEM_PIPELINES': {
            'src.crawlers.common.pipelines.ValidationPipeline': 100,
            'src.crawlers.common.pipelines.MongoPipeline': 300,
            'src.crawlers.common.pipelines.QdrantPipeline': 400,
        },
        'ENABLE_QDRANT': True,  # Enable Qdrant sync
    }
    
    def __init__(
        self,
        max_pages: int = 10,
        incremental: bool = True,
        start_page: int = 2,
        start_url: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """
        Initialize spider.
        
        Args:
            max_pages: Số trang tối đa cần crawl (default: 10)
            incremental: Bật incremental crawling (default: True)
            start_page: Trang bắt đầu crawl (default: 2)
            start_url: URL danh sách job override (optional)
        """
        super().__init__(*args, **kwargs)
        
        self.max_pages = int(max_pages)
        self.incremental = incremental
        self.start_page = max(1, int(start_page))
        self.start_url = None
        
        if start_url and str(start_url).strip():
            self.start_url = str(start_url).strip()
            try:
                parsed = urlparse(self.start_url)
                query = parse_qs(parsed.query)
                if 'page' in query and query['page']:
                    self.start_page = max(1, int(query['page'][0]))
            except Exception:
                pass
        self.stop_crawling = False
        
        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'jobs_found': 0,
            'jobs_detailed': 0,
            'jobs_skipped': 0
        }
        
        # Base URLs
        if not self.start_url:
            self.start_url = f'https://www.vietnamworks.com/viec-lam?page={self.start_page}'
        
        self.start_urls = [self.start_url]
        
        logger.info(
            f"VietnamWorksSpider initialized: "
            f"max_pages={self.max_pages}, incremental={self.incremental}, "
            f"start_page={self.start_page}, start_url={self.start_url}"
        )
    
    def start_requests(self):
        """Generate initial requests."""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_job_list,
                meta={'page': self.start_page},
                errback=self.errback_httpbin,
                dont_filter=True
            )
    
    def _handle_brotli_encoding(self, response):
        """Handle brotli encoding issues."""
        try:
            import brotli  # pyright: ignore[reportMissingImports]
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
        - Danh sách job URLs từ __next_f.push data (Next.js)
        - Fallback: HTML selectors nếu không có __next_f.push data
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
        
        # Method 1: Extract từ __next_f.push data (Next.js)
        next_f_data = self._extract_next_f_data(response.text)
        jobs_from_json = None
        
        if next_f_data:
            jobs_from_json = parse_job_list_from_next_f(next_f_data)
            if jobs_from_json:
                logger.info(f"Found {len(jobs_from_json)} jobs from __next_f.push data")
        
        jobs_on_page = 0
        
        # Nếu có jobs từ JSON, dùng chúng
        if jobs_from_json:
            for job_data in jobs_from_json:
                if self.stop_crawling:
                    logger.info("Stopping crawl due to incremental logic")
                    return
                
                if not job_data.get('url'):
                    logger.warning("Job item missing URL, skipping")
                    continue
                
                # Make absolute URL
                if not job_data['url'].startswith('http'):
                    job_url = urljoin('https://www.vietnamworks.com', job_data['url'])
                else:
                    job_url = job_data['url']
                
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
        else:
            # Method 2: Fallback - Extract từ HTML selectors
            logger.info("No jobs from __next_f.push, trying HTML selectors...")
            # Ưu tiên selector cụ thể của VietnamWorks
            # Class pattern: search_list view_job_item item-0 new-job-card
            # Số tăng dần: item-0, item-1, item-2, item-3, ...
            # Selector sẽ match tất cả items bất kể số thứ tự
            job_selectors = None
            
            # Thử selector cụ thể trước - match pattern chung (bỏ qua item-X)
            selectors_to_try = [
                # Selector chính: match tất cả items có 3 class cố định (bỏ qua item-0, item-1, ...)
                '.search_list.view_job_item.new-job-card',
                # Match nếu có cả 3 class (bất kể thứ tự và có item-X)
                '[class*="search_list"][class*="view_job_item"][class*="new-job-card"]',
                # Match pattern item-* (item-0, item-1, item-2, ...)
                '[class*="search_list"][class*="view_job_item"][class*="item-"][class*="new-job-card"]',
                # Match nếu có 2 class chính
                '.view_job_item.new-job-card',
                '[class*="view_job_item"][class*="new-job-card"]',
                # Match chỉ với class chính
                '.view_job_item',
                '.new-job-card',
                '[class*="view_job_item"]',
                '[class*="new-job-card"]',
                # Fallback selectors
                '.job-item',
                '.job-list-item',
                '.job-card',
                '.job-search-result',
                '[data-job-id]',
                '.job-listing-item'
            ]
            
            for sel in selectors_to_try:
                try:
                    job_selectors = response.css(sel)
                    if job_selectors:
                        logger.info(f"Found {len(job_selectors)} jobs using selector: {sel}")
                        break
                except Exception as e:
                    logger.debug(f"Selector '{sel}' failed: {e}")
                    continue
            
            if not job_selectors:
                logger.warning(f"No jobs found on page {current_page} (neither JSON nor HTML)")
                logger.debug(f"Response HTML length: {len(response.text)}")
                # Log một phần HTML để debug
                logger.debug(f"First 2000 chars of HTML: {response.text[:2000]}")
                return
            
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
                if not job_data['url'].startswith('http'):
                    job_url = urljoin('https://www.vietnamworks.com', job_data['url'])
                else:
                    job_url = job_data['url']
                
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
    
    def _extract_next_f_data(self, html_text: str) -> str:
        """
        Extract tất cả các dòng self.__next_f.push([1,"..."]) từ HTML.
        Đây là dữ liệu JSON được Next.js serialize.
        """
        import re
        
        # Pattern để tìm tất cả các dòng self.__next_f.push([1,"..."])
        # Sử dụng non-greedy match và cho phép newlines trong string
        # Pattern: self.__next_f.push([1,"..."]), trong đó "..." có thể chứa escaped quotes và newlines
        pattern = r'self\.__next_f\.push\(\[1,"(?:[^"\\]|\\.|\\n)*"\]\)'
        
        matches = re.findall(pattern, html_text, re.DOTALL)
        
        if matches:
            # Reconstruct full matches với prefix
            full_matches = []
            for match in re.finditer(pattern, html_text, re.DOTALL):
                full_matches.append(match.group(0))
            
            # Join tất cả các matches lại với nhau
            extracted_data = '\n'.join(full_matches)
            logger.info(f"Extracted {len(full_matches)} __next_f.push entries")
            return extracted_data
        else:
            # Thử pattern đơn giản hơn nếu pattern trên không match
            simple_pattern = r'self\.__next_f\.push\(\[1,".*?"\]\)'
            simple_matches = re.findall(simple_pattern, html_text, re.DOTALL)
            
            if simple_matches:
                extracted_data = '\n'.join(simple_matches)
                logger.info(f"Extracted {len(simple_matches)} __next_f.push entries (simple pattern)")
                return extracted_data
            else:
                logger.warning("No __next_f.push([1,...]) found in HTML")
                return ""
    
    def _filter_relevant_html(self, response):
        """
        Lọc HTML để chỉ lấy các phần liên quan.
        Tùy chỉnh theo cấu trúc HTML của VietnamWorks.
        """
        try:
            # Tìm các section chứa thông tin job
            # VietnamWorks có thể có cấu trúc khác TopCV
            sections = []
            
            # Thử tìm các container phổ biến
            main_content = response.css('.job-detail, .job-content, .job-main, #job-detail').get()
            if main_content:
                sections.append(main_content)
            
            header = response.css('.job-header, .job-title-section, header.job').get()
            if header:
                sections.append(header)
            
            company_section = response.css('.company-info, .employer-info, .company-details').get()
            if company_section:
                sections.append(company_section)
            
            if not sections:
                logger.warning(f"No relevant sections found, using full HTML for {response.url}")
                return response
            
            # Create filtered HTML
            filtered_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    {' '.join(sections)}
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
        
        # Extract __next_f.push data từ HTML gốc
        next_f_data = self._extract_next_f_data(response.text)
        
        # Filter HTML before parsing (optional, có thể bỏ qua nếu không cần)
        filtered_response = self._filter_relevant_html(response)
        filtered_html = filtered_response.text if filtered_response != response else response.text
        
        # Parse detail từ HTML
        job_data = parse_job_detail(filtered_response)
        
        # Merge with list data
        for key, value in list_data.items():
            if key not in job_data or not job_data[key]:
                job_data[key] = value
        
        # Parse và transform dữ liệu từ __next_f.push sang format chuẩn
        parsed_data = None
        if next_f_data:
            parsed_data = parse_next_f_data(next_f_data)
            if parsed_data:
                # Map các trường từ parsed_data vào job_data
                job_data = map_parsed_data_to_job_item(parsed_data, job_data)
                logger.info(f"Mapped parsed data to job fields for jobId: {parsed_data.get('jobId')}")
        
        # Validate
        if not validate_job_item(job_data):
            logger.warning(f"Invalid job item, skipping: {response.url}")
            self.stats['jobs_skipped'] += 1
            return
        
        # Create item
        item = JobItem()
        for key, value in job_data.items():
            if key in item.fields:
                item[key] = value
        
        # Set required fields
        item['source'] = 'vietnamworks'
        item['crawl_timestamp'] = datetime.utcnow()
        item['url'] = response.url
        item['http_status'] = response.status
        
        # Lưu raw_data: nếu có parsed_data thì lưu dict, không thì lưu string
        if parsed_data:
            # Lưu cả raw string và parsed data
            item['raw_data'] = parsed_data  # Dữ liệu đã parse và transform
        else:
            # Nếu không parse được, lưu HTML hoặc raw string
            item['raw_data'] = next_f_data if next_f_data else filtered_html
        
        logger.info(
            f"Successfully created item: {item.get('title')} at {item.get('company')}"
        )
        
        yield item
    
    def _get_next_page_url(self, response, current_page: int) -> Optional[str]:
        """
        Extract next page URL từ pagination.
        
        VietnamWorks có thể dùng format: ?page=2, ?page=3, ...
        hoặc có link "Next" trong HTML
        """
        # Method 1: Tìm link "Next" hoặc "Trang sau"
        next_link = response.css(
            'a.next::attr(href), '
            'a.pagination-next::attr(href), '
            'li.next a::attr(href), '
            'a[aria-label*="Next"]::attr(href), '
            'a[aria-label*="next"]::attr(href)'
        ).get()
        
        if next_link:
            return urljoin(response.url, next_link)
        
        # Method 2: Construct URL với page parameter
        next_page_num = current_page + 1
        
        if 'page=' in response.url:
            next_url = response.url.replace(
                f'page={current_page}',
                f'page={next_page_num}'
            )
        else:
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


class VietnamWorksFullSpider(VietnamWorksSpider):
    """
    Spider variant để crawl toàn bộ danh sách (không incremental).
    
    Usage:
        scrapy crawl vietnamworks_full_spider -a max_pages=50
    """
    
    name = 'vietnamworks_full_spider'
    
    def __init__(self, *args, **kwargs):
        kwargs['incremental'] = False
        kwargs['max_pages'] = kwargs.get('max_pages', 100)
        super().__init__(*args, **kwargs)


if __name__ == "__main__":
    # Test spider locally
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    
    process = CrawlerProcess(get_project_settings())
    process.crawl(VietnamWorksSpider, max_pages=2)
    process.start()
