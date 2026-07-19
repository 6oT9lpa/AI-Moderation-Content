from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhishingPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    domain_max_age_days: int = Field(default=7, ge=0, le=365)
    max_urls_per_message: int = Field(default=5, ge=1, le=20)
    minimum_bad_indicators: int = Field(default=1, ge=1, le=10)
    max_domain_labels: int = Field(default=4, ge=2, le=10)
    severity: int = Field(default=5, ge=0, le=5)
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    risk_weight: int = Field(default=85, ge=0, le=100)
    reason: str = Field(default="phishing_new_unlisted_scam_url", min_length=1, max_length=128)
    suspicious_keywords: tuple[str, ...] = (
        "airdrop",
        "bonus",
        "claim",
        "crypto",
        "gift",
        "login",
        "promo",
        "verify",
        "wallet",
    )

    @field_validator("suspicious_keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value: object) -> tuple[str, ...] | object:
        if isinstance(value, str):
            value = value.split(",")

        if not isinstance(value, (list, tuple, set, frozenset)):
            return value

        return tuple(dict.fromkeys(str(item).strip().lower() for item in value if str(item).strip()))
