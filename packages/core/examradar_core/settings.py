from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ExamRadar"
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"
    secret_key: str = "dev-insecure-change-me"

    # SQLite works for local development and tests; production uses PostgreSQL.
    database_url: str = f"sqlite:///{(REPO_ROOT / 'storage' / 'examradar.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: str = "local"  # local | s3
    local_storage_dir: str = str(REPO_ROOT / "storage" / "objects")
    s3_endpoint_url: str | None = None
    s3_bucket: str = "examradar-documents"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "ap-south-1"

    crawler_user_agent: str = "ExamRadarBot/0.1 (+https://github.com/Anirudh-1106/ExamRadar)"
    crawler_default_min_delay_seconds: float = 5.0
    crawler_timeout_seconds: float = 30.0
    crawler_max_bytes: int = 25_000_000

    llm_provider: str = "none"  # groq | none
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    admin_bootstrap_email: str | None = None
    admin_bootstrap_password: str | None = None

    firebase_project_id: str | None = None
    firebase_credentials_file: str | None = None

    # News mentions are shown publicly only as unverified headlines with a link.
    news_mentions_public: bool = True
    google_news_enabled: bool = False

    # Changed dates on already-published events go to human review unless this is switched on.
    auto_publish_revisions: bool = False

    log_level: str = "INFO"
    sources_file: str = str(REPO_ROOT / "config" / "sources.yaml")
    scam_text_retention_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
