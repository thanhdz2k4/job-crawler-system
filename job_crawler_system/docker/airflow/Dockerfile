FROM apache/airflow:2.10.2-python3.11

USER root

# Cài các thư viện cần để chạy crawler
COPY docker/airflow/requirements-airflow.txt /requirements-airflow.txt
USER airflow
RUN pip install --no-cache-dir -r /requirements-airflow.txt

# Copy mã nguồn crawler vào container để DAG có thể gọi
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN mkdir -p /opt/playwright \
    && /home/airflow/.local/bin/playwright install --with-deps chromium \
    && chmod -R 755 /opt/playwright
ENV CRAWLER_HOME=/opt/airflow/jobs/job_crawler_system
WORKDIR ${CRAWLER_HOME}
COPY --chown=airflow:root . ${CRAWLER_HOME}

USER airflow
