"""
JobsGo Spider

Scrapy spider to collect job postings from JobsGo.vn.
Supports pagination and incremental crawling.

Usage:
    scrapy crawl jobsgo_spider
    scrapy crawl jobsgo_spider -a max_pages=5
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin

import scrapy  # pyright: ignore[reportMissingImports]
from scrapy.http import HtmlResponse  # pyright: ignore[reportMissingImports]
from scrapy_playwright.page import PageMethod

from .items import JobItem
from .parser import parse_job_detail, parse_job_list_item, validate_job_item

logger = logging.getLogger(__name__)


class JobsGoSpider(scrapy.Spider):
    """Spider for JobsGo.vn job listings."""

    name = "jobsgo_spider"
    allowed_domains = ["jobsgo.vn"]
    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--no-sandbox"],
        },
    }

    def __init__(self, max_pages: int = 10, incremental: bool = True, *args, **kwargs):
        """Initialize spider.

        Args:
            max_pages: Max list pages to crawl (default: 10).
            incremental: Enable incremental crawling (default: True).
        """
        super().__init__(*args, **kwargs)

        self.max_pages = int(max_pages)
        self.incremental = incremental
        self.stop_crawling = False

        self.stats = {
            "pages_crawled": 0,
            "jobs_found": 0,
            "jobs_detailed": 0,
            "jobs_skipped": 0,
        }

        self.start_urls = [
            "https://jobsgo.vn/viec-lam.html?sort=created&page=1",
        ]

        logger.info(
            "JobsGoSpider initialized: "
            "max_pages=%s, incremental=%s",
            self.max_pages,
            self.incremental,
        )

    def _playwright_meta(self, base_meta: Optional[dict] = None) -> dict:
        meta = dict(base_meta or {})
        meta.update(
            {
                "playwright": True,
                "playwright_context": "default",
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "domcontentloaded"),
                    PageMethod("wait_for_timeout", 5000),
                ],
            }
        )
        return meta

    def start_requests(self):
        """Generate initial requests."""
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_job_list,
                meta=self._playwright_meta({"page": 1}),
                errback=self.errback_httpbin,
                dont_filter=True,
            )

    def _handle_brotli_encoding(self, response):
        """Handle brotli encoding issues."""
        try:
            import brotli

            content_encoding = response.headers.get("Content-Encoding", b"").decode(
                "utf-8"
            ).lower()

            if "br" in content_encoding or content_encoding == "":
                try:
                    body = brotli.decompress(response.body)
                    return HtmlResponse(
                        url=response.url,
                        body=body,
                        encoding="utf-8",
                        request=response.request,
                    )
                except Exception as br_error:
                    logger.error("Brotli decompression failed: %s", br_error)
                    return HtmlResponse(
                        url=response.url,
                        body=response.body,
                        encoding="utf-8",
                        request=response.request,
                    )
        except ImportError:
            logger.error("brotli module not available, install with: pip install brotli")
        except Exception as decode_error:
            logger.error("Failed to decode response: %s", decode_error)

        return response

    def parse_job_list(self, response):
        """Parse job list page and enqueue detail requests."""
        current_page = response.meta.get("page", 1)
        self.stats["pages_crawled"] += 1

        logger.info("Parsing job list page %s: %s", current_page, response.url)

        try:
            if not response.text:
                logger.error("Empty response body for %s", response.url)
                return
        except (AttributeError, Exception) as exc:
            logger.warning("Cannot decode response body: %s", exc)
            response = self._handle_brotli_encoding(response)
            if not response.text:
                return

        selectors_to_try = [
            ".card.job-card",
            ".job-card",
            ".job-item",
            ".job-list-item",
            "[class*=\"job-item\"]",
            "[data-id]",
        ]

        job_selectors = []
        for selector in selectors_to_try:
            try:
                job_selectors = response.css(selector)
                if job_selectors:
                    logger.info(
                        "Found %s jobs using selector: %s",
                        len(job_selectors),
                        selector,
                    )
                    break
            except Exception as exc:
                logger.debug("Selector '%s' failed: %s", selector, exc)

        if not job_selectors:
            logger.warning("No jobs found on page %s", current_page)
            logger.debug("Response URL: %s", response.url)
            logger.debug("Response HTML length: %s", len(response.text))
            return

        jobs_on_page = 0

        for job_selector in job_selectors:
            if self.stop_crawling:
                logger.info("Stopping crawl due to incremental logic")
                return

            job_data = parse_job_list_item(job_selector)

            if not job_data.get("url"):
                logger.warning("Job item missing URL, skipping")
                continue

            job_url = urljoin(response.url, job_data["url"])
            jobs_on_page += 1
            self.stats["jobs_found"] += 1

            if self.incremental and job_data.get("posted_date"):
                if isinstance(job_data["posted_date"], datetime):
                    age = datetime.now() - job_data["posted_date"]
                    if age > timedelta(hours=24):
                        logger.info("Job older than 24h, considering stop: %s", job_url)

            yield scrapy.Request(
                url=job_url,
                callback=self.parse_job_detail,
                meta=self._playwright_meta({"list_data": job_data}),
                errback=self.errback_httpbin,
                priority=10,
            )

        logger.info("Found %s jobs on page %s", jobs_on_page, current_page)

        if current_page < self.max_pages and not self.stop_crawling:
            next_page = self._get_next_page_url(response, current_page)

            if next_page:
                logger.info("Following to page %s", current_page + 1)
                yield scrapy.Request(
                    url=next_page,
                    callback=self.parse_job_list,
                    meta=self._playwright_meta({"page": current_page + 1}),
                    errback=self.errback_httpbin,
                )
            else:
                logger.info("No more pages found")

    def _filter_relevant_html(self, response):
        """Filter HTML to core JobsGo detail section when available."""
        try:
            section = response.css("section.job-detail").get()
            if not section:
                logger.warning("No relevant sections found, using full HTML for %s", response.url)
                return response

            filtered_html = (
                "<!DOCTYPE html>\n"
                "<html>\n"
                "<head><meta charset=\"utf-8\"></head>\n"
                "<body>\n"
                f"{section}"
                "\n</body>\n"
                "</html>"
            )

            filtered_response = HtmlResponse(
                url=response.url,
                body=filtered_html.encode("utf-8"),
                encoding="utf-8",
                request=response.request,
            )

            logger.info(
                "Filtered HTML: %s chars (original: %s chars)",
                len(filtered_html),
                len(response.text),
            )
            return filtered_response

        except Exception as exc:
            logger.error("Error filtering HTML: %s, using original response", exc)
            return response

    def parse_job_detail(self, response):
        """Parse job detail page."""
        self.stats["jobs_detailed"] += 1
        logger.info("Parsing job detail: %s", response.url)

        list_data = response.meta.get("list_data", {})

        filtered_response = self._filter_relevant_html(response)
        filtered_html = (
            filtered_response.text if filtered_response != response else response.text
        )

        job_data = parse_job_detail(filtered_response)

        if job_data is None:
            logger.warning("Job data is None, skipping: %s", response.url)
            self.stats["jobs_skipped"] += 1
            return

        for key, value in list_data.items():
            if key not in job_data or not job_data[key]:
                job_data[key] = value

        if not validate_job_item(job_data):
            logger.warning("Invalid job item, skipping: %s", response.url)
            self.stats["jobs_skipped"] += 1
            return

        item = JobItem()
        for key, value in job_data.items():
            if key in item.fields:
                item[key] = value

        item["source"] = "jobsgo"
        item["crawl_timestamp"] = datetime.utcnow()
        item["url"] = response.url
        item["http_status"] = response.status
        item["raw_data"] = filtered_html

        logger.info(
            "Created item: %s at %s with %s skills",
            item.get("title"),
            item.get("company"),
            len(item.get("skills", [])),
        )

        yield item

    def _get_next_page_url(self, response, current_page: int) -> Optional[str]:
        """Extract next page URL from pagination or by incrementing page parameter."""
        next_link = response.css(
            "#pagination li.next a::attr(href), "
            ".pagination li.next a::attr(href), "
            "a.next::attr(href)"
        ).get()

        if next_link:
            return urljoin(response.url, next_link)

        next_page_num = current_page + 1

        if "page=" in response.url:
            import re

            return re.sub(r"page=\d+", f"page={next_page_num}", response.url)

        separator = "&" if "?" in response.url else "?"
        return f"{response.url}{separator}page={next_page_num}"

    def errback_httpbin(self, failure):
        """Handle request failures."""
        logger.error("Request failed: %s", failure.request.url)
        logger.error("Error: %s", failure.value)

    def closed(self, reason):
        """Called when spider closes."""
        logger.info("Spider closed: %s", reason)
        logger.info(
            "Summary: Pages=%s, Jobs Found=%s, Jobs Detailed=%s, Jobs Skipped=%s",
            self.stats["pages_crawled"],
            self.stats["jobs_found"],
            self.stats["jobs_detailed"],
            self.stats["jobs_skipped"],
        )
