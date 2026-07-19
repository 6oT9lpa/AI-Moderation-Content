from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_MODERATOR_",
        case_sensitive=False,
        extra="ignore",
    )

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    internal_api_key: str | None = Field(default=None, min_length=16)
    api_docs_enabled: bool = False
    api_max_body_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    api_rate_limit: int = Field(default=120, ge=1, le=10_000)
    api_rate_window_seconds: int = Field(default=60, ge=1, le=3_600)
    api_inference_concurrency: int = Field(default=1, ge=1, le=8)
    api_queue_workers: int = Field(default=2, ge=1, le=8)
    api_queue_size: int = Field(default=500, ge=1, le=10_000)
    api_rubert_enabled: bool = True
    api_rubert_required: bool = True
    api_rubert_model_dir: str = "models/rubert-tiny2-moderation-trained"
    phishing_enabled: bool = False
    phishing_google_safe_browsing_api_key: str | None = Field(default=None, min_length=16)
    phishing_rdap_enabled: bool = False
    phishing_request_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
