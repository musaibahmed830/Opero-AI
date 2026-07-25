FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY opero_worker ./opero_worker
RUN pip install --no-cache-dir .

CMD ["celery", "-A", "opero_worker.celery_app", "worker", "--loglevel=INFO"]
