"""
Airflow DAG to run the VietnamWorks crawler.

- Picks base directory from Airflow Variable `CRAWLER_HOME` (default: /opt/airflow/jobs/job_crawler_system).
- Picks Mongo settings from Airflow Variables `MONGO_URI` and `MONGO_DATABASE`.
- Uses rate limiting configuration from rate_limiting_config.py.
- Allows overriding max_pages via dag_run.conf (default from config).
"""

import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models.param import Param

# Add project root to Python path to import config modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


default_args = {
    "owner": "crawler",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Default values - will be overridden by Jinja templates in operators
BASE_DIR = '/opt/airflow/jobs/job_crawler_system'
MONGO_URI = 'mongodb://mongo:27017'
MONGO_DB = 'job_crawler_db'

with DAG(
    dag_id="vietnamworks_crawler_dag",
    description="Run VietnamWorks crawler via Scrapy",
    schedule="0 7 * * *",  # daily 7am
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["crawler", "vietnamworks"],
    params={
        "max_pages": Param(
            default=10,
            type="integer",
            minimum=1,
            maximum=200,
            description="Maximum pages to crawl for VietnamWorks"
        ),
        "start_page": Param(
            default=2,
            type="integer",
            minimum=1,
            maximum=200,
            description="Starting page for VietnamWorks crawl"
        ),
        "start_url": Param(
            default="",
            type="string",
            description="Optional list URL override (e.g. https://www.vietnamworks.com/viec-lam?page=2)"
        ),
    },
) as dag:
    # Import rate limiting configuration
    try:
        from config.rate_limiting_config import get_scrapy_settings, get_max_pages_for_domain

        # Get rate limiting settings for VietnamWorks
        rate_limiting_settings = get_scrapy_settings('vietnamworks.com')

        # Build Scrapy command with rate limiting settings
        scrapy_settings = []
        for key, value in rate_limiting_settings.items():
            # Skip USER_AGENTS - will be handled by Scrapy settings.py instead
            if key == 'USER_AGENTS':
                continue
            if isinstance(value, bool):
                scrapy_settings.append(f"-s {key}={'true' if value else 'false'}")
            elif isinstance(value, list):
                # Properly join list values with comma
                scrapy_settings.append(f"-s {key}={','.join(map(str, value))}")
            else:
                scrapy_settings.append(f"-s {key}={value}")

        scrapy_settings_str = " ".join(scrapy_settings)

        # Get default max pages from config
        default_max_pages = get_max_pages_for_domain('vietnamworks.com')

    except ImportError:
        # Fallback if config modules not available
        scrapy_settings_str = (
            "-s DOWNLOAD_DELAY=20 "
            "-s CONCURRENT_REQUESTS=1 "
            "-s AUTOTHROTTLE_ENABLED=true "
            "-s AUTOTHROTTLE_START_DELAY=20 "
            "-s AUTOTHROTTLE_MAX_DELAY=240 "
            "-s RANDOMIZE_DOWNLOAD_DELAY=true "
        )
        default_max_pages = 10

    crawl_vietnamworks = BashOperator(
        task_id="crawl_vietnamworks",
        bash_command=(
            "export MONGO_URI=\"{{ var.value.get('MONGO_URI', 'mongodb://admin:admin123@mongo:6868/?authSource=admin') }}\" && "
            "export MONGO_DATABASE=\"{{ var.value.get('MONGO_DATABASE', 'job_crawler_db') }}\" && "
            "cd {{ var.value.get('CRAWLER_HOME', '/opt/airflow/jobs/job_crawler_system') }} && "
            "/home/airflow/.local/bin/scrapy crawl vietnamworks_spider "
            "-a max_pages={{ params.max_pages | default('" + str(default_max_pages) + "') }} "
            "-a start_page={{ params.start_page | default('1') }} "
            "-a start_url=\"{{ params.start_url | default('') }}\" "
            f"{scrapy_settings_str} "
        ),
        execution_timeout=timedelta(hours=12),
    )
