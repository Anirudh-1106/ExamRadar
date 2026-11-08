FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY packages packages
COPY services services
COPY config config
RUN pip install --no-cache-dir ".[postgres,s3]"
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8000
CMD ["sh", "-c", "cd services/api && alembic upgrade head && cd /app && examradar sync && uvicorn examradar_api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 2"]
