from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MediaRuleSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = "media_analyzer_v1"
    max_phash_distance: int = Field(default=6, ge=0, le=64)
    max_image_attachments: int = Field(default=4, ge=1, le=32)
    max_image_bytes: int = Field(default=8 * 1024 * 1024, ge=1_024, le=8 * 1024 * 1024)
    max_image_pixels: int = Field(default=20_000_000, ge=1_024, le=100_000_000)
    max_ocr_text_length: int = Field(default=20_000, ge=256, le=100_000)
    short_text_length: int = Field(default=12, ge=0, le=256)
    new_account_days: int = Field(default=30, ge=0, le=3650)
    medium_risk_threshold: int = Field(default=35, ge=1, le=100)
    high_risk_threshold: int = Field(default=70, ge=1, le=100)
    casino_keywords: tuple[str, ...] = ()
    money_keywords: tuple[str, ...] = ()
    bonus_keywords: tuple[str, ...] = ()
    payment_keywords: tuple[str, ...] = ()
    fake_news_keywords: tuple[str, ...] = ()
    crypto_keywords: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_thresholds(self) -> "MediaRuleSettings":
        if self.medium_risk_threshold > self.high_risk_threshold:
            raise ValueError("medium_risk_threshold must not exceed high_risk_threshold")
        return self
