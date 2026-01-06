"""
VietnamWorks Parser Module

Module chứa các hàm parse và clean dữ liệu từ HTML của VietnamWorks.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List


logger = logging.getLogger(__name__)


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
    
    # "Cập nhật: 29/11/2025", "2 ngày trước"
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


def extract_skills(text: str) -> List[str]:
    """
    Skill extraction disabled; always returns empty list.
    """
    return []


def parse_job_list_item(selector: Any) -> Dict[str, Any]:
    """
    Parse item từ trang danh sách VietnamWorks.
    Cấu trúc: class="search_list view_job_item item-0 new-job-card"
    """
    job = {}
    try:
        # URL & Title - VietnamWorks structure
        # Thử nhiều selector phổ biến cho VietnamWorks
        link_tag = (
            selector.css('a.job-title').get() or
            selector.css('h3 a').get() or
            selector.css('h2 a').get() or
            selector.css('a[href*="/viec-lam/"]').get() or
            selector.css('a[href*="-jv"]').get() or  # VietnamWorks URL pattern: ...-jobId-jv
            selector.css('.job-title a').get() or
            selector.css('.title a').get() or
            selector.css('a[href*="vietnamworks.com"]').get()
        )
        
        if link_tag:
            from scrapy.selector import Selector
            link_sel = Selector(text=link_tag)
            job['url'] = link_sel.css('a::attr(href)').get()
            job['title'] = clean_text(link_sel.css('a::text').get() or link_sel.css('a::attr(title)').get())
        else:
            # Fallback: tìm link trực tiếp trong selector
            job['url'] = (
                selector.css('a::attr(href)').get() or
                selector.css('a[href*="/viec-lam/"]::attr(href)').get() or
                selector.css('a[href*="-jv"]::attr(href)').get()
            )
            job['title'] = clean_text(
                selector.css('a::text').get() or
                selector.css('h3::text').get() or
                selector.css('h2::text').get() or
                selector.css('.job-title::text').get() or
                selector.css('.title::text').get() or
                selector.css('a::attr(title)').get()
            )

        # Company - VietnamWorks structure
        company_selectors = [
            '.company-name',
            '.company',
            'a.company',
            '.employer-name',
            '.company-title',
            '[data-company]',
            '.company-info',
            'a[href*="/cong-ty/"]'  # VietnamWorks company link pattern
        ]
        for sel in company_selectors:
            company = selector.css(sel + '::text').get()
            if company:
                job['company'] = clean_text(company)
                break
        # Nếu không tìm thấy, thử lấy từ link
        if not job.get('company'):
            company_link = selector.css('a[href*="/cong-ty/"]::text').get()
            if company_link:
                job['company'] = clean_text(company_link)
        
        # Salary - VietnamWorks structure
        salary_selectors = [
            '.salary',
            '.job-salary',
            '.salary-text',
            '[data-salary]',
            '.wage',
            '.salary-range'
        ]
        for sel in salary_selectors:
            salary = selector.css(sel + '::text').get()
            if salary:
                job['salary_raw'] = clean_text(salary)
                break

        # Location - VietnamWorks structure
        location_selectors = [
            '.location',
            '.job-location',
            '.address',
            '.city',
            '[data-location]',
            '.location-text'
        ]
        for sel in location_selectors:
            location = selector.css(sel + '::text').get()
            if location:
                job['location'] = clean_text(location)
                break

        # Posted Date - VietnamWorks structure
        date_selectors = [
            '.posted-date',
            '.update-date',
            '.date',
            '.post-date',
            '[data-date]',
            '.time-posted'
        ]
        for sel in date_selectors:
            date_raw = selector.css(sel + '::text').get()
            if date_raw:
                job['posted_date'] = parse_date(date_raw)
                break

        # Make URL absolute
        if job.get('url') and not job['url'].startswith('http'):
            job['url'] = f"https://www.vietnamworks.com{job['url']}"

        return job
    except Exception as e:
        logger.error(f"Error parsing list item: {e}")
        return {}


def parse_job_detail(response: Any) -> Dict[str, Any]:
    """
    Parse chi tiết từ trang Job Detail VietnamWorks.
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
        
        # Title - Thử nhiều selector phổ biến
        title_selectors = [
            'h1.job-title',
            'h1.job-name',
            '.job-title h1',
            'h1',
            '.job-header h1',
            '//h1[contains(@class, "title") or contains(@class, "job")]',
            '//h1'
        ]
        job['title'] = try_selectors(title_selectors)
        
        # Company
        company_selectors = [
            '.company-name',
            '.employer-name',
            '.company-title',
            'a.company',
            '.job-company',
            '//a[contains(@class, "company")]',
            '//div[contains(@class, "company")]'
        ]
        job['company'] = try_selectors(company_selectors)

        # Salary
        salary_selectors = [
            '.job-salary',
            '.salary',
            '.wage',
            '[data-salary]',
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
        
        # Location
        location_selectors = [
            '.job-location',
            '.location',
            '.address',
            '[data-location]',
            '//div[contains(@class, "location")]//text()',
            '//span[contains(text(), "Địa điểm")]/following-sibling::*[1]'
        ]
        job['location'] = try_selectors(location_selectors)
        
        # Experience
        experience_selectors = [
            '.experience',
            '.job-experience',
            '[data-experience]',
            '//div[contains(@class, "experience")]//text()',
            '//span[contains(text(), "Kinh nghiệm")]/following-sibling::*[1]'
        ]
        job['experience'] = try_selectors(experience_selectors)
        
        # Deadline
        deadline_selectors = [
            '.deadline',
            '.expiry-date',
            '.job-deadline',
            '[data-deadline]',
            '//div[contains(@class, "deadline")]//text()',
            '//span[contains(text(), "Hạn nộp")]/following-sibling::*[1]'
        ]
        deadline_txt = try_selectors(deadline_selectors)
        job['deadline'] = parse_date(deadline_txt)

        # Description - Tìm trong các section phổ biến
        description_selectors_css = [
            '.job-description',
            '.description',
            '.job-detail',
            '#job-description',
            '.job-content'
        ]
        description_selectors_xpath = [
            '//div[contains(@class, "description")]',
            '//div[contains(@id, "description")]'
        ]
        description_text = ""
        for sel in description_selectors_css:
            try:
                desc_elem = response.css(sel)
                if desc_elem:
                    description_text = clean_text(" ".join(desc_elem.css('::text').getall()))
                    if description_text and len(description_text) > 10:
                        break
            except Exception:
                continue
        if not description_text:
            for sel in description_selectors_xpath:
                try:
                    desc_elem = response.xpath(sel)
                    if desc_elem:
                        description_text = clean_text(" ".join(desc_elem.xpath('.//text()').getall()))
                        if description_text and len(description_text) > 10:
                            break
                except Exception:
                    continue
        
        job['description'] = description_text
        
        # Requirements
        requirement_selectors_css = [
            '.job-requirements',
            '.requirements',
            '.job-requirement',
            '#requirements'
        ]
        requirement_selectors_xpath = [
            '//div[contains(@class, "requirement")]',
            '//h3[contains(text(), "Yêu cầu")]/following-sibling::*[1]'
        ]
        requirement_text = ""
        for sel in requirement_selectors_css:
            try:
                req_elem = response.css(sel)
                if req_elem:
                    requirement_text = clean_text(" ".join(req_elem.css('::text').getall()))
                    if requirement_text and len(requirement_text) > 10:
                        break
            except Exception:
                continue
        if not requirement_text:
            for sel in requirement_selectors_xpath:
                try:
                    req_elem = response.xpath(sel)
                    if req_elem:
                        requirement_text = clean_text(" ".join(req_elem.xpath('.//text()').getall()))
                        if requirement_text and len(requirement_text) > 10:
                            break
                except Exception:
                    continue
        job['requirements'] = requirement_text
        
        # Benefits
        benefit_selectors_css = [
            '.job-benefits',
            '.benefits',
            '.job-benefit',
            '#benefits'
        ]
        benefit_selectors_xpath = [
            '//div[contains(@class, "benefit")]',
            '//h3[contains(text(), "Quyền lợi")]/following-sibling::*[1]'
        ]
        benefit_text = ""
        for sel in benefit_selectors_css:
            try:
                ben_elem = response.css(sel)
                if ben_elem:
                    benefit_text = clean_text(" ".join(ben_elem.css('::text').getall()))
                    if benefit_text and len(benefit_text) > 10:
                        break
            except Exception:
                continue
        if not benefit_text:
            for sel in benefit_selectors_xpath:
                try:
                    ben_elem = response.xpath(sel)
                    if ben_elem:
                        benefit_text = clean_text(" ".join(ben_elem.xpath('.//text()').getall()))
                        if benefit_text and len(benefit_text) > 10:
                            break
                except Exception:
                    continue
        job['benefits'] = benefit_text

        # Extract Skills - DISABLED: Just crawl data without skill extraction
        logger.info(f"⚡ Skipping skill extraction for {response.url} (disabled)")
        job['skills'] = []
        
        # try:
        #     full_text = f"{job.get('description', '')} {job.get('requirements', '')}"
        #     job['skills'] = extract_skills(full_text)
        #     logger.debug(f"Skills extracted for {response.url}: {len(job.get('skills', []))} skills found")
        # except Exception as e:
        #     logger.error(f"Skill extraction failed for {response.url}: {type(e).__name__}: {e}")
        #     logger.debug(f"Full text length: {len(full_text) if 'full_text' in locals() else 0}")
        #     job['skills'] = []  # Default to empty list instead of null
        
        # Log if critical fields are missing
        if not job.get('title') or not job.get('company'):
            logger.warning(
                f"Missing critical fields for {response.url}: "
                f"title={bool(job.get('title'))}, company={bool(job.get('company'))}"
            )
        
        # Metadata
        job['source'] = 'vietnamworks'

        return job

    except Exception as e:
        logger.error(f"Error parsing detail page {response.url}: {e}", exc_info=True)
        return job


def validate_job_item(job: Dict[str, Any]) -> bool:
    """Validate extracted job data."""
    return bool(job.get('title') and job.get('url'))


def map_parsed_data_to_job_item(parsed_data: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map các trường từ parsed_data (raw_data.parsed) vào job_data (JobItem fields).
    
    Args:
        parsed_data: Dict từ transform_to_standard_format (raw_data.parsed)
        job_data: Dict hiện tại từ HTML parsing
        
    Returns:
        Dict với các trường đã được map từ parsed_data
    """
    if not parsed_data:
        return job_data
    
    # Map các trường cơ bản
    if parsed_data.get('jobTitle'):
        job_data['title'] = parsed_data['jobTitle']
    
    # Map company info
    company_info = parsed_data.get('company', {})
    if isinstance(company_info, dict):
        if company_info.get('companyName'):
            job_data['company'] = company_info['companyName']
        if company_info.get('companyLogo'):
            job_data['company_logo'] = company_info['companyLogo']
        
        # Map contact info
        if company_info.get('contactName'):
            job_data['contact_name'] = company_info['contactName']
        if company_info.get('email'):
            job_data['contact_email'] = company_info['email']
        
        # Map location
        location_info = company_info.get('location', {})
        if isinstance(location_info, dict):
            location_parts = []
            if location_info.get('cityName'):
                location_parts.append(location_info['cityName'])
            if location_info.get('address'):
                location_parts.append(location_info['address'])
            if location_parts:
                job_data['location'] = ', '.join(location_parts)
    
    # Map salary
    salary_info = parsed_data.get('salary', {})
    if isinstance(salary_info, dict):
        if salary_info.get('prettySalary'):
            job_data['salary_raw'] = salary_info['prettySalary']
        if salary_info.get('salaryMin') is not None:
            job_data['salary_min'] = salary_info['salaryMin']
        if salary_info.get('salaryMax') is not None:
            job_data['salary_max'] = salary_info['salaryMax']
        if salary_info.get('currency'):
            job_data['salary_currency'] = salary_info['currency']
    
    # Map description và requirements
    if parsed_data.get('description'):
        job_data['description'] = parsed_data['description']
    if parsed_data.get('requirements'):
        job_data['requirements'] = parsed_data['requirements']
    
    # Map benefits
    benefits = parsed_data.get('benefits', [])
    if isinstance(benefits, list) and benefits:
        # Join list thành string hoặc giữ nguyên list
        if all(isinstance(b, str) for b in benefits):
            job_data['benefits'] = '\n'.join(benefits)
        else:
            job_data['benefits'] = benefits
    
    # Map skills
    skills = parsed_data.get('skills', [])
    if isinstance(skills, list) and skills:
        job_data['skills'] = skills
    
    # Map experience
    if parsed_data.get('experienceRequired') is not None:
        exp = parsed_data['experienceRequired']
        if isinstance(exp, (int, float)):
            job_data['experience'] = f"{int(exp)} năm"
        else:
            job_data['experience'] = str(exp)
    
    # Map dates
    if parsed_data.get('createdOn'):
        job_data['posted_date'] = parsed_data['createdOn']
    if parsed_data.get('expiredOn'):
        job_data['deadline'] = parsed_data['expiredOn']
    
    # Map job function (có thể dùng cho industries)
    if parsed_data.get('jobFunction'):
        if 'industries' not in job_data or not job_data['industries']:
            job_data['industries'] = [parsed_data['jobFunction']]
    
    return job_data


def parse_job_list_from_next_f(raw_data: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse danh sách jobs từ raw_data (các dòng self.__next_f.push([1,"..."])).
    Extract job list JSON từ Next.js payload.
    
    Args:
        raw_data: String chứa các dòng self.__next_f.push([1,"..."])
        
    Returns:
        List các dict chứa job data từ list page, hoặc None nếu không parse được
    """
    import json
    import re
    
    if not raw_data:
        return None
    
    try:
        lines = raw_data.split('\n')
        job_list_data = None
        # print(11111111111111, raw_data)

        for line in lines:
            if 'self.__next_f.push([1,"' not in line:
                continue
            
            # Extract JSON string từ line
            match = re.search(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', line, re.DOTALL)
            if not match:
                continue
                
            json_str_raw = match.group(1)
            
            # Tìm dòng chứa job list (có thể có "jobList", "jobs", "results", hoặc array of jobs)
            if ('"jobList"' in json_str_raw or 
                '"jobs"' in json_str_raw or 
                '"results"' in json_str_raw or
                'jobId' in json_str_raw):
                
                # Unescape JSON string
                try:
                    json_str = json.loads('"' + json_str_raw + '"')
                except:
                    json_str = json_str_raw.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
                
                # Tìm job list data
                # Method 1: Tìm "jobList":[...]
                if '"jobList"' in json_str:
                    match_list = re.search(r'"jobList"\s*:\s*(\[.*?\])', json_str, re.DOTALL)
                    if match_list:
                        try:
                            job_list_data = json.loads(match_list.group(1))
                            break
                        except:
                            pass
                
                # Method 2: Tìm "jobs":[...] hoặc "results":[...]
                if not job_list_data:
                    for key in ['"jobs"', '"results"', '"data"']:
                        if key in json_str:
                            match_list = re.search(rf'{key}\s*:\s*(\[.*?\])', json_str, re.DOTALL)
                            if match_list:
                                try:
                                    job_list_data = json.loads(match_list.group(1))
                                    if isinstance(job_list_data, list) and len(job_list_data) > 0:
                                        break
                                except:
                                    pass
                
                # Method 3: Tìm array chứa objects có "jobId"
                if not job_list_data and 'jobId' in json_str:
                    # Tìm vị trí của array chứa jobId
                    job_id_pos = json_str.find('"jobId"')
                    # Tìm opening bracket gần nhất trước jobId
                    start_pos = json_str.rfind('[', 0, job_id_pos)
                    if start_pos >= 0:
                        # Tìm closing bracket tương ứng
                        bracket_count = 0
                        end_pos = start_pos
                        for i in range(start_pos, len(json_str)):
                            if json_str[i] == '[':
                                bracket_count += 1
                            elif json_str[i] == ']':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    end_pos = i + 1
                                    break
                        if end_pos > start_pos:
                            try:
                                potential_list = json.loads(json_str[start_pos:end_pos])
                                if isinstance(potential_list, list) and len(potential_list) > 0:
                                    job_list_data = potential_list
                                    break
                            except:
                                pass
        
        if not job_list_data:
            logger.warning("Could not find or parse job list in __next_f.push data")
            return None
        
        # Transform job list items
        jobs = []
        for job_item in job_list_data:
            if isinstance(job_item, dict):
                job = {
                    'jobId': job_item.get('jobId') or job_item.get('job_id'),
                    'title': job_item.get('jobTitle') or job_item.get('title') or job_item.get('job_title', ''),
                    'company': job_item.get('companyName') or job_item.get('company') or job_item.get('company_name', ''),
                    'url': job_item.get('canonical') or job_item.get('url') or job_item.get('jobUrl', ''),
                    'salary_raw': job_item.get('prettySalary') or job_item.get('salary') or job_item.get('salary_raw', ''),
                    'location': job_item.get('location') or job_item.get('cityName') or '',
                    'posted_date': job_item.get('createdOn') or job_item.get('postedDate') or job_item.get('posted_date')
                }
                # Make URL absolute if needed
                if job['url'] and not job['url'].startswith('http'):
                    job['url'] = f"https://www.vietnamworks.com/{job['url']}"
                jobs.append(job)
        
        logger.info(f"Parsed {len(jobs)} jobs from __next_f.push data")
        return jobs if jobs else None
        
    except Exception as e:
        logger.error(f"Error parsing job list from __next_f.push data: {e}", exc_info=True)
        return None


def parse_next_f_data(raw_data: str) -> Optional[Dict[str, Any]]:
    """
    Parse dữ liệu từ raw_data (các dòng self.__next_f.push([1,"..."])).
    Extract job detail JSON và transform sang format chuẩn.
    
    Args:
        raw_data: String chứa các dòng self.__next_f.push([1,"..."])
        
    Returns:
        Dict chứa job data theo format chuẩn, hoặc None nếu không parse được
    """
    import json
    import re
    
    if not raw_data:
        return None
    
    try:
        # Tìm tất cả các dòng __next_f.push
        lines = raw_data.split('\n')
        job_data = None
        
        for line in lines:
            if 'self.__next_f.push([1,"' not in line:
                continue
            
            # Extract JSON string từ line
            # Pattern: self.__next_f.push([1,"JSON_STRING"])
            # Cần match cả string dài có thể chứa newlines
            match = re.search(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', line, re.DOTALL)
            if not match:
                continue
                
            json_str_raw = match.group(1)
            
            # Tìm dòng chứa job detail (thường có "25:" hoặc chứa "jobId")
            if '"25:' in json_str_raw or '"jobId"' in json_str_raw or 'jobDetail' in json_str_raw:
                # Unescape JSON string một cách cẩn thận
                # Sử dụng json.loads để unescape đúng cách
                try:
                    # Wrap trong quotes và unescape
                    json_str = json.loads('"' + json_str_raw + '"')
                except:
                    # Fallback: manual unescape
                    json_str = json_str_raw.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
                
                # Tìm phần JSON chứa job detail
                # Format có thể là: "25:{...}" hoặc "jobDetail":{...}
                job_json_str = None
                
                # Method 1: Tìm "25:{...}"
                if '"25:' in json_str:
                    match_25 = re.search(r'"25:\s*(\{.*)', json_str, re.DOTALL)
                    if match_25:
                        job_json_str = match_25.group(1)
                        # Tìm closing brace tương ứng (balance braces)
                        brace_count = 0
                        end_pos = 0
                        for i, char in enumerate(job_json_str):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_pos = i + 1
                                    break
                        if end_pos > 0:
                            job_json_str = job_json_str[:end_pos]
                        else:
                            job_json_str = None
                
                # Method 2: Tìm "jobDetail":{...}
                if not job_json_str and '"jobDetail"' in json_str:
                    match_job_detail = re.search(r'"jobDetail"\s*:\s*(\{.*)', json_str, re.DOTALL)
                    if match_job_detail:
                        job_json_str = match_job_detail.group(1)
                        # Balance braces
                        brace_count = 0
                        end_pos = 0
                        for i, char in enumerate(job_json_str):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_pos = i + 1
                                    break
                        if end_pos > 0:
                            job_json_str = job_json_str[:end_pos]
                        else:
                            job_json_str = None
                
                # Method 3: Tìm object chứa "jobId" trực tiếp
                if not job_json_str and '"jobId"' in json_str:
                    # Tìm vị trí bắt đầu của object chứa jobId
                    job_id_pos = json_str.find('"jobId"')
                    # Tìm opening brace gần nhất trước jobId
                    start_pos = json_str.rfind('{', 0, job_id_pos)
                    if start_pos >= 0:
                        # Tìm closing brace tương ứng
                        brace_count = 0
                        end_pos = start_pos
                        for i in range(start_pos, len(json_str)):
                            if json_str[i] == '{':
                                brace_count += 1
                            elif json_str[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_pos = i + 1
                                    break
                        if end_pos > start_pos:
                            job_json_str = json_str[start_pos:end_pos]
                
                # Parse JSON
                if job_json_str:
                    try:
                        job_data = json.loads(job_json_str)
                        break  # Tìm thấy, dừng lại
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON decode error: {e}, trying next line")
                        continue
        
        if not job_data:
            logger.warning("Could not find or parse job detail in __next_f.push data")
            return None
        
        # Transform sang format chuẩn
        normalized_data = transform_to_standard_format(job_data)
        return normalized_data
        
    except Exception as e:
        logger.error(f"Error parsing __next_f.push data: {e}", exc_info=True)
        return None


def transform_to_standard_format(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform job data từ VietnamWorks format sang format chuẩn.
    
    Args:
        job_data: Dict chứa job data từ VietnamWorks JSON
        
    Returns:
        Dict theo format chuẩn như ví dụ:
        {
            "jobId": 1982739,
            "jobTitle": "...",
            "company": {...},
            "salary": {...},
            ...
        }
    """
    result = {}
    
    # jobId
    result['jobId'] = job_data.get('jobId') or job_data.get('job_id')
    
    # jobTitle
    result['jobTitle'] = job_data.get('jobTitle') or job_data.get('title') or job_data.get('job_title', '')
    
    # company
    company_info = job_data.get('companyInfo') or job_data.get('company') or {}
    result['company'] = {
        'companyId': company_info.get('companyId') or company_info.get('company_id') or job_data.get('companyId'),
        'companyName': company_info.get('companyName') or company_info.get('company_name') or job_data.get('companyName', ''),
        'companyLogo': company_info.get('companyLogoURL') or company_info.get('company_logo') or job_data.get('companyLogo', ''),
        'companySize': company_info.get('companySize') or company_info.get('company_size') or job_data.get('companySize', ''),
        'contactName': company_info.get('contactName') or company_info.get('contact_name') or job_data.get('contactName', ''),
        'email': company_info.get('contactEmail') or company_info.get('email') or job_data.get('emailAddress', ''),
        'website': company_info.get('website') or '',
        'address': company_info.get('address') or '',
        'location': {}
    }
    
    # Location từ workingLocations
    working_locations = job_data.get('workingLocations') or job_data.get('working_locations') or []
    if working_locations and len(working_locations) > 0:
        loc = working_locations[0]
        geo_loc = loc.get('geoLoc') or loc.get('geo_loc') or {}
        result['company']['location'] = {
            'cityName': loc.get('cityNameVI') or loc.get('cityName') or loc.get('city_name', ''),
            'address': loc.get('address') or '',
            'lat': float(geo_loc.get('lat') or 0.0),
            'lon': float(geo_loc.get('lon') or 0.0)
        }
    
    # salary
    result['salary'] = {
        'prettySalary': job_data.get('prettySalaryVI') or job_data.get('prettySalary') or job_data.get('salary_raw', ''),
        'salaryMin': job_data.get('salaryMin') or job_data.get('salary_min'),
        'salaryMax': job_data.get('salaryMax') or job_data.get('salary_max'),
        'currency': job_data.get('salaryCurrency') or job_data.get('salary_currency', 'VND')
    }
    
    # workingTime
    result['workingTime'] = {
        'workingDays': job_data.get('workingDays') or job_data.get('working_days', ''),
        'fromHour': job_data.get('workingFromHour') or job_data.get('working_from_hour', ''),
        'toHour': job_data.get('workingToHour') or job_data.get('working_to_hour', '')
    }
    
    # description - Remove HTML tags nếu có
    desc = job_data.get('jobDescription') or job_data.get('description') or job_data.get('job_description', '')
    if desc:
        # Remove HTML tags đơn giản
        desc = re.sub(r'<[^>]+>', '', desc)
    result['description'] = clean_text(desc)
    
    # requirements - Remove HTML tags nếu có
    req = job_data.get('jobRequirement') or job_data.get('requirements') or job_data.get('job_requirement', '')
    if req:
        req = re.sub(r'<[^>]+>', '', req)
    result['requirements'] = clean_text(req)
    
    # skills
    skills = job_data.get('skills') or []
    if isinstance(skills, list):
        result['skills'] = [
            skill.get('skillName') if isinstance(skill, dict) else str(skill)
            for skill in skills
        ]
    else:
        result['skills'] = []
    
    # benefits
    benefits = job_data.get('benefits') or []
    if isinstance(benefits, list):
        result['benefits'] = [
            benefit.get('benefitValue') if isinstance(benefit, dict) else str(benefit)
            for benefit in benefits
        ]
    else:
        result['benefits'] = []
    
    # jobFunction
    job_function = job_data.get('jobFunction') or {}
    if isinstance(job_function, dict):
        result['jobFunction'] = job_function.get('parentNameVI') or job_function.get('parentName') or ''
    else:
        result['jobFunction'] = str(job_function) if job_function else ''
    
    # experienceRequired
    result['experienceRequired'] = job_data.get('yearsOfExperience') or job_data.get('experience') or 0
    
    # highestDegree
    result['highestDegree'] = job_data.get('highestDegreeId') or job_data.get('highest_degree_id') or 0
    
    # dates
    result['createdOn'] = job_data.get('createdOn') or job_data.get('created_on') or job_data.get('posted_date')
    result['expiredOn'] = job_data.get('expiredOn') or job_data.get('expired_on') or job_data.get('deadline')
    
    # stats
    result['views'] = job_data.get('numOfViews') or job_data.get('views') or 0
    result['applications'] = job_data.get('numOfApplications') or job_data.get('applications') or 0
    
    # canonical
    result['canonical'] = job_data.get('canonical') or job_data.get('alias', '')
    
    return result
