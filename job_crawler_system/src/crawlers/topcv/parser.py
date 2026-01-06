"""
TopCV Parser Module

Module chứa các hàm parse và clean dữ liệu từ HTML của TopCV.
Updated selectors for TopCV structure (Nov 2025).
"""

import re
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Use /tmp for debug output to avoid permission issues in Docker
_DEBUG_OUTPUT_DIR = Path("/tmp/debug_jobs")
try:
    _DEBUG_OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
except PermissionError:
    logger.warning(f"Cannot create debug directory at {_DEBUG_OUTPUT_DIR}, debug output disabled")
    _DEBUG_OUTPUT_DIR = None
except Exception as e:
    logger.warning(f"Error creating debug directory: {e}")
    _DEBUG_OUTPUT_DIR = None

# Skill extraction disabled
api_extract_skills = None


def clean_text(text: Optional[str]) -> str:
    """Clean text: remove extra whitespace, newlines."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_salary(salary_text: str) -> Dict[str, Any]:
    """Parse salary text và extract min, max, currency."""
    result = {
        'raw': clean_text(salary_text),
        'min': None,
        'max': None,
        'currency': 'VND'
    }
    
    if not salary_text:
        return result
    
    salary_text_lower = salary_text.lower()
    
    # Check negotiable
    if any(k in salary_text_lower for k in ['thỏa thuận', 'thương lượng', 'negotiable', 'cạnh tranh']):
        return result
    
    # Detect currency
    multiplier = 1
    if '$' in salary_text or 'usd' in salary_text_lower:
        result['currency'] = 'USD'
    else:
        result['currency'] = 'VND'
        if 'triệu' in salary_text_lower:
            multiplier = 1000000
        elif 'trăm' in salary_text_lower and 'nghìn' in salary_text_lower:
            multiplier = 100000
    
    # Extract numbers
    numbers = re.findall(r'(\d+(?:\.\d+)?)', salary_text)
    
    if len(numbers) >= 2:
        result['min'] = float(numbers[0]) * multiplier
        result['max'] = float(numbers[1]) * multiplier
    elif len(numbers) == 1:
        val = float(numbers[0]) * multiplier
        if any(k in salary_text_lower for k in ['tới', 'đến', 'up to', 'dưới']):
            result['max'] = val
        else:
            result['min'] = val
            
    return result


def parse_date(date_text: str) -> Optional[datetime]:
    """Parse date text usually found in lists or details."""
    if not date_text:
        return None
    
    date_text = clean_text(date_text.lower())
    now = datetime.now()
    
    # Relative dates
    if 'hôm nay' in date_text:
        return now
    if 'hôm qua' in date_text:
        return now - timedelta(days=1)
    
    # "Cập nhật 1 giờ trước", "2 ngày trước"
    match = re.search(r'(\d+)\s*(giờ|ngày|phút)', date_text)
    if match:
        val, unit = int(match.group(1)), match.group(2)
        delta_map = {
            'ngày': timedelta(days=val),
            'giờ': timedelta(hours=val),
            'phút': timedelta(minutes=val)
        }
        return now - delta_map.get(unit, timedelta())

    # Absolute dates DD/MM/YYYY
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass
            
    return None



def extract_skills(text: str, timeout: int = 60) -> List[str]:
    """
    Skill extraction disabled; always returns empty list.
    """
    return []

    


def parse_job_list_item(selector: Any) -> Dict[str, Any]:
    """
    Parse item từ trang danh sách (Search Page).
    Selector input là div class="job-item-search-result"
    """
    job = {}
    try:
        # URL & Title (TopCV Structure: h3.title > a)
        link_tag = selector.css('h3.title a')
        job['url'] = link_tag.css('::attr(href)').get()
        title_raw = link_tag.css('span::text').get() or link_tag.css('::text').get()
        job['title'] = clean_text(title_raw)

        # Company
        job['company'] = clean_text(selector.css('a.company::text').get())
        job['company_logo'] = selector.css('a.logo img::attr(src)').get()

        # Salary, Location, Date
        job['salary_raw'] = clean_text(selector.css('.title-salary::text').get())
        job['location'] = clean_text(selector.css('.address::text').get())
        date_raw = selector.css('.time::text').get() or selector.css('.up-date::text').get()
        job['posted_date'] = parse_date(date_raw)
        job['is_hot'] = bool(selector.css('.avatar-hot').get())

        return job
    except Exception as e:
        logger.error(f"Error parsing list item: {e}")
        return {}


def parse_job_detail(response: Any) -> Dict[str, Any]:
    """
    Parse chi tiết từ trang Job Detail.
    """
    job = {}
    try:
        job['url'] = response.url
        job['http_status'] = response.status
        
        # Helper function to try multiple selectors
        def try_selectors(selectors_list, default=""):
            """Try multiple CSS/XPath selectors, return first match."""
            for selector in selectors_list:
                try:
                    if selector.startswith('//') or selector.startswith('.//'):
                        # XPath
                        result = response.xpath(selector).get()
                        if result:
                            return clean_text(result)
                        texts = response.xpath(selector + '//text()').getall()
                        if texts:
                            return clean_text(' '.join(texts))
                    else:
                        # CSS selector
                        result = response.css(selector + '::text').get()
                        if result:
                            return clean_text(result)
                        texts = response.css(selector + ' ::text').getall()
                        if texts:
                            return clean_text(' '.join(texts))
                except Exception:
                    continue
            return default
        
        # Title (ưu tiên class mới) - lấy text trực tiếp từ class
        title_element = response.css('.job-detail__info--title')
        if title_element:
            job['title'] = clean_text(" ".join(title_element.css('::text').getall()))
        else:
            title_selectors = [
                '#header-job-info h1',
                '#header-job-info .title',
                'h1.job-detail-title',
                'h1.title',
                '.job-title h1',
                'h1',
                '//h1[contains(@class, "title") or contains(@class, "job")]',
                '//h1'
            ]
            job['title'] = try_selectors(title_selectors)
        
        # Company (ưu tiên class mới) - lấy text trực tiếp từ class
        company_element = response.css('.job-detail__company--information')
        if company_element:
            job['company'] = clean_text(" ".join(company_element.css('::text').getall()))
        else:
            company_selectors = [
                '.job-detail__box--right.job-detail__company .company-title',
                '.job-detail__box--right.job-detail__company .company-name',
                '#header-job-info .company-title',
                '.job-detail__company .company-title',
                '.company-title',
                '.company-name',
                '.job-company',
                'a.company',
                '//a[contains(@class, "company")]',
                '//div[contains(@class, "company")]'
            ]
            job['company'] = try_selectors(company_selectors)

        # Salary
        salary_selectors = [
            '.box-info-job .job-detail-info-salary .job-detail-info-value',
            '.job-detail-info-salary .job-detail-info-value',
            '.box-info-job .salary',
            '.salary',
            '//div[contains(@class, "salary")]//text()',
            '//span[contains(text(), "Lương")]/following-sibling::*[1]'
        ]
        salary_txt = try_selectors(salary_selectors)
        salary_data = extract_salary(salary_txt)
        job.update({
            'salary_raw': salary_data['raw'],
            'salary_min': salary_data['min'],
            'salary_max': salary_data['max'],
            'salary_currency': salary_data['currency']
        })
        
        # Experience
        experience_selectors = [
            '.box-info-job .job-detail-info-experience .job-detail-info-value',
            '.job-detail-info-experience .job-detail-info-value',
            '.experience',
            '//div[contains(@class, "experience")]//text()',
            '//span[contains(text(), "Kinh nghiệm")]/following-sibling::*[1]'
        ]
        job['experience'] = try_selectors(experience_selectors)
        
        # Deadline (ưu tiên class mới) - lấy text trực tiếp từ class
        deadline_element = response.css('.job-detail__info--deadline-date')
        if deadline_element:
            deadline_txt = clean_text(" ".join(deadline_element.css('::text').getall()))
            job['deadline'] = parse_date(deadline_txt)
        else:
            deadline_selectors = [
                '.job-detail-info-deadline',
                '.deadline',
                '.expiry-date',
                '//div[contains(@class, "deadline")]//text()',
                '//span[contains(text(), "Hạn nộp")]/following-sibling::*[1]'
            ]
            deadline_txt = try_selectors(deadline_selectors)
            job['deadline'] = parse_date(deadline_txt)

        # Content Sections - Updated selectors based on actual HTML structure
        # Description: Look for "Mô tả công việc" heading and get content
        description_text = ""
        description_selectors = [
            '.job-description__item h3:contains("Mô tả công việc") + .job-description__item--content',
            '.job-description__item:has(h3:contains("Mô tả công việc")) .job-description__item--content',
            '//h3[contains(text(), "Mô tả công việc")]/following-sibling::div[contains(@class, "job-description__item--content")]',
            '//div[contains(@class, "job-description__item")]//h3[contains(text(), "Mô tả công việc")]/following-sibling::div[contains(@class, "job-description__item--content")]'
        ]
        
        for selector in description_selectors:
            if selector.startswith('//'):
                # XPath selector
                elements = response.xpath(selector)
                if elements:
                    description_text = clean_text(" ".join(elements.css('::text').getall()))
                    break
            else:
                # CSS selector
                elements = response.css(selector)
                if elements:
                    description_text = clean_text(" ".join(elements.css('::text').getall()))
                    break
        
        # Fallback: get first .job-description__item that's not requirement/benefit
        if not description_text:
            description_items = response.css('.job-description__item')
            for item in description_items:
                item_classes = item.css('::attr(class)').get() or ""
                heading = item.css('h3::text').get()
                # Skip requirement và benefit
                if 'requirement' not in item_classes and 'benefit' not in item_classes and heading and 'Mô tả công việc' in heading:
                    # Lấy toàn bộ text trong content div
                    content = item.css('.job-description__item--content')
                    if content:
                        description_text = clean_text(" ".join(content.css('::text').getall()))
                        break
        
        job['description'] = description_text if description_text else "N/A"
        
        # Requirements: Look for "Yêu cầu ứng viên" heading
        requirement_text = ""
        requirement_selectors = [
            '.job-description__item.job-detail-section.requirement .job-description__item--content',
            '.job-description__item:has(h3:contains("Yêu cầu ứng viên")) .job-description__item--content',
            '//h3[contains(text(), "Yêu cầu ứng viên")]/following-sibling::div[contains(@class, "job-description__item--content")]',
            '//div[contains(@class, "job-description__item")]//h3[contains(text(), "Yêu cầu ứng viên")]/following-sibling::div[contains(@class, "job-description__item--content")]'
        ]
        
        for selector in requirement_selectors:
            if selector.startswith('//'):
                # XPath selector
                elements = response.xpath(selector)
                if elements:
                    requirement_text = clean_text(" ".join(elements.css('::text').getall()))
                    break
            else:
                # CSS selector
                elements = response.css(selector)
                if elements:
                    requirement_text = clean_text(" ".join(elements.css('::text').getall()))
                    break
        
        job['requirements'] = requirement_text if requirement_text else "N/A"
        
        # Benefits: Look for "Quyền lợi" heading
        benefit_text = ""
        benefit_selectors = [
            '.job-description__item.job-detail-section.benefit .job-description__item--content',
            '.job-description__item:has(h3:contains("Quyền lợi")) .job-description__item--content',
            '//h3[contains(text(), "Quyền lợi")]/following-sibling::div[contains(@class, "job-description__item--content")]',
            '//div[contains(@class, "job-description__item")]//h3[contains(text(), "Quyền lợi")]/following-sibling::div[contains(@class, "job-description__item--content")]'
        ]
        
        for selector in benefit_selectors:
            if selector.startswith('//'):
                # XPath selector
                elements = response.xpath(selector)
                if elements:
                    benefit_text = clean_text(" ".join(elements.css('::text').getall()))
                    break
            else:
                # CSS selector
                elements = response.css(selector)
                if elements:
                    benefit_text = clean_text(" ".join(elements.css('::text').getall()))
                    break
        
        job['benefits'] = benefit_text if benefit_text else "N/A"
        
        # Location: .job-description__item (phân biệt với description/requirement/benefit)
        location_text = ""
        location_items = response.css('.job-description__item')
        for item in location_items:
            item_classes = item.css('::attr(class)').get() or ""
            # Skip requirement và benefit, và cần phân biệt với description
            if 'requirement' not in item_classes and 'benefit' not in item_classes:
                text = clean_text(" ".join(item.css('::text').getall()))
                # Location khác với description (nếu đã có description)
                if text and len(text) > 5 and text != job.get('description', ''):
                    location_text = text
                    break
        
        # Fallback nếu không tìm thấy bằng class mới
        if not location_text:
            location_selectors = [
                '.box-info-job .job-detail-info-address .job-detail-info-value',
                '.job-detail-info-address .job-detail-info-value',
                '.box-info-job .address',
                '.address',
                '.location',
                '//div[contains(@class, "address") or contains(@class, "location")]//text()',
                '//span[contains(text(), "Địa điểm") or contains(text(), "Location")]/following-sibling::*[1]'
            ]
            location_text = try_selectors(location_selectors)
        job['location'] = location_text if location_text else "N/A"

        # Extract Skills - DISABLED: Just crawl data without skill extraction
        # full_text = f"{job.get('description', '')} {job.get('requirements', '')}"
        
        # Skip skill extraction to speed up crawling
        logger.info(f"⚡ Skipping skill extraction for {response.url} (disabled)")
        job['skills'] = []
        job['skills_extracted'] = False
        
        # # Only extract skills if we have meaningful content
        # if len(full_text.strip()) >= 50:
        #     logger.info(f"Extracting skills for {response.url} (text length: {len(full_text)})")
        #     skills = extract_skills(full_text, timeout=60)  # 60 second timeout
        #     
        #     # Set skills even if empty (could be non-technical job or API failure)
        #     if skills:
        #         job['skills'] = skills
        #         job['skills_extracted'] = True
        #         logger.info(f"✓ Skills extracted for {response.url}: {len(skills)} skills")
        #     else:
        #         logger.warning(f"⚠ No skills extracted for {response.url} - saving job anyway (may be non-technical)")
        #         job['skills'] = []
        #         job['skills_extracted'] = False
        #         # Continue processing - don't return None
        # else:
        #     logger.warning(f"Insufficient text for skill extraction ({len(full_text)} chars) for {response.url}")
        #     job['skills'] = []
        #     job['skills_extracted'] = False
            # For jobs with very short text, we can still save them but mark as no skills
        
        # Log if critical fields are missing
        if not job.get('title') or not job.get('company'):
            logger.warning(
                f"Missing critical fields for {response.url}: "
                f"title={bool(job.get('title'))}, company={bool(job.get('company'))}"
            )
        
        # Metadata
        job['source'] = 'topcv'
        
        # Save debug data
        # _save_debug_job(job, response.text)

        return job

    except Exception as e:
        logger.error(f"Error parsing detail page {response.url}: {e}", exc_info=True)
        # job['raw_html'] = response.text
        # _save_debug_job(job, response.text)
        return job


def validate_job_item(job: Dict[str, Any]) -> bool:
    """Validate extracted job data."""
    return bool(job.get('title') and job.get('url'))


if __name__ == "__main__":
    # Quick Test
    print("Testing parser with dummy data...")
    print(f"Salary Test: {extract_salary('Tới 20 triệu')}")
    print(f"Date Test: {parse_date('Cập nhật 2 giờ trước')}")
