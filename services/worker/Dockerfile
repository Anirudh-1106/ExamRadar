FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Tesseract with English and Malayalam for scanned notices.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-mal \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY packages packages
COPY services services
COPY config config
RUN pip install --no-cache-dir ".[postgres,s3,ocr]"
# SSC is rendered in a headless browser. Comment these two lines out to keep the image small if SSC is not needed.
RUN pip install --no-cache-dir ".[browser]" && python -m playwright install --with-deps chromium
RUN useradd -m app && chown -R app /app
USER app
CMD ["celery", "-A", "examradar_worker.celery_app", "worker", "--loglevel=INFO"]
