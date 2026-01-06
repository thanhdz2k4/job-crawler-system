"""
Maintenance DAG for crawler environment.

Tasks:
- Prune Airflow logs older than a retention window.
- Vacuum crawler logs directory if present.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "crawler",
    "depends_on_past": False,
    "retries": 0,
}

# Default values - will be overridden by Jinja templates in operators
LOG_RETENTION_DAYS = 7
CRAWLER_HOME = '/opt/airflow/jobs/job_crawler_system'

with DAG(
    dag_id="maintenance_dag",
    description="Cleanup logs and temp data for crawler",
    schedule="@weekly",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["maintenance", "crawler"],
) as dag:
    prune_airflow_logs = BashOperator(
        task_id="prune_airflow_logs",
        bash_command=(
            "find /opt/airflow/logs -type f -mtime +{{ params.retention }} -print -delete"
        ),
        params={"retention": "{{ var.value.get('CRAWLER_LOG_RETENTION_DAYS', 7) }}"},
        execution_timeout=timedelta(minutes=30),
    )

    prune_crawler_logs = BashOperator(
        task_id="prune_crawler_logs",
        bash_command=(
            "if [ -d {{ var.value.get('CRAWLER_HOME', '/opt/airflow/jobs/job_crawler_system') }}/logs ]; then "
            "find {{ var.value.get('CRAWLER_HOME', '/opt/airflow/jobs/job_crawler_system') }}/logs -type f -mtime +{{ params.retention }} -print -delete; "
            "fi"
        ),
        params={"retention": "{{ var.value.get('CRAWLER_LOG_RETENTION_DAYS', 7) }}"},
        execution_timeout=timedelta(minutes=15),
    )

    prune_airflow_logs >> prune_crawler_logs
