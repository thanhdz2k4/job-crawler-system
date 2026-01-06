"""
JobsGo Parser Module

Parse and clean JobsGo HTML into structured job data.
"""

import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def clean_text(text: Optional[str]) -> str:
    """Collapse whitespace and trim."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text: Optional[str]) -> str:
    """Lowercase and remove Vietnamese diacritics for matching."""
    if not text:
        return ""
    text = clean_text(text).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("đ", "d")


def extract_salary(salary_text: str) -> Dict[str, Any]:
    """Parse salary text to min/max/currency."""
    result = {
        "raw": clean_text(salary_text),
        "min": None,
        "max": None,
        "currency": "VND",
    }

    if not salary_text:
        return result

    normalized = normalize_text(salary_text)

    if any(k in normalized for k in ["thoa thuan", "thuong luong", "negotiable", "canh tranh"]):
        return result

    if "$" in salary_text or "usd" in normalized:
        result["currency"] = "USD"
    else:
        result["currency"] = "VND"

    multiplier = 1
    if re.search(r"\b\d+(?:[.,]\d+)?\s*(trieu|tr)\b", normalized):
        multiplier = 1_000_000
    elif re.search(r"\b\d+(?:[.,]\d+)?\s*(nghin|ngan|k)\b", normalized):
        multiplier = 1_000

    numbers = re.findall(r"\d+(?:[.,]\d+)?", salary_text)
    values = []
    for num in numbers:
        try:
            values.append(float(num.replace(",", ".")))
        except ValueError:
            continue

    if len(values) >= 2:
        result["min"] = values[0] * multiplier
        result["max"] = values[1] * multiplier
    elif len(values) == 1:
        val = values[0] * multiplier
        if any(k in normalized for k in ["toi da", "den", "toi", "up to", "upto", "max"]):
            result["max"] = val
        elif any(k in normalized for k in ["tu", "from", "tren", "hon"]):
            result["min"] = val
        else:
            result["min"] = val

    return result


def parse_date(date_text: str) -> Optional[datetime]:
    """Parse relative or absolute dates from text."""
    if not date_text:
        return None

    cleaned = clean_text(date_text)
    normalized = normalize_text(cleaned)
    now = datetime.now()

    if "hom nay" in normalized:
        return now
    if "hom qua" in normalized:
        return now - timedelta(days=1)

    match = re.search(r"(\d+)\s*(phut|gio|ngay|tuan|thang|nam)", normalized)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        if unit == "phut":
            return now - timedelta(minutes=value)
        if unit == "gio":
            return now - timedelta(hours=value)
        if unit == "ngay":
            return now - timedelta(days=value)
        if unit == "tuan":
            return now - timedelta(days=7 * value)
        if unit == "thang":
            return now - timedelta(days=30 * value)
        if unit == "nam":
            return now - timedelta(days=365 * value)

    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", cleaned)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    return None


def extract_skills(text: str) -> List[str]:
    """Skill extraction disabled; always returns empty list."""
    return []


def parse_job_list_item(selector: Any) -> Dict[str, Any]:
    """Parse job item from list page."""
    job: Dict[str, Any] = {}
    try:
        job["url"] = (
            selector.css('a[href*="/viec-lam/"]::attr(href)').get()
            or selector.css("a::attr(href)").get()
        )

        title_parts = selector.css("h3.job-title ::text").getall()
        title_tokens = []
        is_hot = False
        for part in title_parts:
            part_clean = clean_text(part)
            if not part_clean:
                continue
            norm_part = normalize_text(part_clean)
            if norm_part in ["hot", "gap", "urgent"]:
                is_hot = True
                continue
            title_tokens.append(part_clean)
        if title_tokens:
            job["title"] = clean_text(" ".join(title_tokens))
        else:
            job["title"] = clean_text(" ".join(title_parts))
        job["is_hot"] = is_hot

        job["company"] = clean_text(
            selector.css(".company-title::text, .job-company::text").get()
        )
        job["company_logo"] = selector.css(
            ".image-wrapper img::attr(src), img::attr(src)"
        ).get()

        meta_spans = selector.css(".text-primary span::text").getall()
        meta_spans = [
            clean_text(text)
            for text in meta_spans
            if clean_text(text) and clean_text(text) != "|"
        ]
        if meta_spans:
            job["salary_raw"] = meta_spans[0]
        if len(meta_spans) > 1:
            job["location"] = meta_spans[1]

        for badge in selector.css(".badge"):
            label = badge.attrib.get("title", "")
            value = clean_text(" ".join(badge.css("::text").getall()))
            label_norm = normalize_text(label)
            if "loai hinh" in label_norm:
                job["job_type"] = value
            elif "kinh nghiem" in label_norm:
                job["experience"] = value
            elif "cap nhat" in label_norm or "thoi gian" in label_norm:
                job["posted_date"] = parse_date(value)

        if not job.get("posted_date"):
            for badge in selector.css(".badge"):
                value = clean_text(" ".join(badge.css("::text").getall()))
                if value and parse_date(value):
                    job["posted_date"] = parse_date(value)
                    break

        link_class = selector.css("a::attr(class)").get() or ""
        link_norm = normalize_text(link_class)
        if any(k in link_norm for k in ["platinum", "gold", "silver", "diamond", "red"]):
            job["is_featured"] = True

        return job
    except Exception as e:
        logger.error(f"Error parsing list item: {e}")
        return {}


def parse_job_detail(response: Any) -> Dict[str, Any]:
    """Parse job detail page."""
    job: Dict[str, Any] = {}
    try:
        job["url"] = response.url
        job["http_status"] = response.status

        def try_selectors(selectors_list: List[str], default: str = "") -> str:
            for selector in selectors_list:
                try:
                    if selector.startswith("//") or selector.startswith(".//"):
                        texts = response.xpath(selector + "//text()").getall()
                        if texts:
                            return clean_text(" ".join(texts))
                    else:
                        text = response.css(selector + "::text").get()
                        if text:
                            return clean_text(text)
                        texts = response.css(selector + " ::text").getall()
                        if texts:
                            return clean_text(" ".join(texts))
                except Exception:
                    continue
            return default

        title = clean_text(" ".join(response.css("h1.job-title::text").getall()))
        if not title:
            title = try_selectors(["h1.job-title", "h1", ".job-title"])
        job["title"] = title

        company = try_selectors(
            [
                ".card-company h6",
                ".card-company h5",
                ".card-company .fw-semibold",
                ".job-company",
                ".company-title",
                ".company-name",
            ]
        )
        job["company"] = company

        job["company_logo"] = response.css(
            ".card-company img.company-logo::attr(src), .card-company img::attr(src)"
        ).get()

        salary_text = ""
        for item in response.css(".job-info-list li"):
            label = clean_text(" ".join(item.css("span.text-muted::text").getall()))
            value = clean_text(
                " ".join(item.css("strong::text, strong a::text").getall())
            )
            if not value:
                value = clean_text(" ".join(item.css("strong ::text").getall()))
            label_norm = normalize_text(label)
            if "muc luong" in label_norm:
                salary_text = value
            elif "dia diem" in label_norm:
                job["location"] = value
            elif "kinh nghiem" in label_norm:
                job["experience"] = value

        salary_data = extract_salary(salary_text)
        job.update(
            {
                "salary_raw": salary_data["raw"],
                "salary_min": salary_data["min"],
                "salary_max": salary_data["max"],
                "salary_currency": salary_data["currency"],
            }
        )

        if not job.get("location"):
            locations = [
                clean_text(text)
                for text in response.css("#places .list-place strong a::text").getall()
            ]
            locations = [loc for loc in locations if loc]
            if locations:
                job["location"] = ", ".join(dict.fromkeys(locations))

        deadline_text = ""
        for paragraph in response.css("p"):
            text = clean_text(" ".join(paragraph.css("::text").getall()))
            if not text:
                continue
            if "han nop ho so" in normalize_text(text):
                strong_text = clean_text(" ".join(paragraph.css("strong::text").getall()))
                deadline_text = strong_text or text
                break
        job["deadline"] = parse_date(deadline_text)

        for card in response.css(".card.job-card"):
            title_text = clean_text(" ".join(card.css("h2.card-title::text").getall()))
            if "thong tin chung" not in normalize_text(title_text):
                continue
            for row in card.css(".row .col-12"):
                label = clean_text(" ".join(row.css("span.text-muted::text").getall()))
                value = clean_text(" ".join(row.css("strong::text").getall()))
                label_norm = normalize_text(label)
                if "loai hinh" in label_norm:
                    job["job_type"] = value
                elif "cap bac" in label_norm:
                    job["level"] = value
                elif "ngay dang tuyen" in label_norm:
                    job["posted_date"] = parse_date(value)
            break

        description = ""
        requirements = ""
        benefits = ""

        section_pairs: List[str] = []
        for header in response.css(".job-detail-card h3.section-title"):
            header_text = clean_text(" ".join(header.css("::text").getall()))
            header_norm = normalize_text(header_text)
            content_node = header.xpath("following-sibling::*[1]")
            content_text = clean_text(" ".join(content_node.css("::text").getall()))

            if not content_text:
                continue

            if "mo ta" in header_norm:
                description = content_text
            elif "yeu cau" in header_norm:
                requirements = content_text
            elif "quyen loi" in header_norm or "phuc loi" in header_norm:
                benefits = content_text
            section_pairs.append(content_text)

        if section_pairs:
            if not description and len(section_pairs) >= 1:
                description = section_pairs[0]
            if not requirements and len(section_pairs) >= 2:
                requirements = section_pairs[1]
            if not benefits and len(section_pairs) >= 3:
                benefits = section_pairs[2]

        job["description"] = description or "N/A"
        job["requirements"] = requirements or "N/A"
        job["benefits"] = benefits or "N/A"

        industries: List[str] = []
        for label in response.css(".job-detail-card .text-muted"):
            label_text = clean_text(" ".join(label.css("::text").getall()))
            if "nganh nghe" not in normalize_text(label_text):
                continue
            parent = label.xpath("..")
            industries = [
                clean_text(text) for text in parent.css("strong a::text").getall()
            ]
            industries = [item for item in industries if item]
            break
        job["industries"] = industries

        logger.info(f"Skill extraction disabled for {response.url}")
        job["skills"] = []
        job["skills_extracted"] = False

        if not job.get("title") or not job.get("company"):
            logger.warning(
                f"Missing critical fields for {response.url}: "
                f"title={bool(job.get('title'))}, company={bool(job.get('company'))}"
            )

        job["source"] = "jobsgo"
        return job

    except Exception as e:
        logger.error(f"Error parsing detail page {response.url}: {e}", exc_info=True)
        return job


def validate_job_item(job: Dict[str, Any]) -> bool:
    """Validate extracted job data."""
    return bool(job.get("title") and job.get("url"))
