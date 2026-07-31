from datetime import datetime

from pydantic import Field

from src.contracts.api.api_model import ApiModel
from src.domain.media.media_rule_policy import MediaRulePolicy


class MediaPolicyUpdateSchema(ApiModel):
    expected_revision: int = Field(ge=0)
    media: MediaRulePolicy


class MediaRuntimeStatusSchema(ApiModel):
    ocr_enabled: bool
    ocr_ready: bool
    yolo_enabled: bool
    yolo_ready: bool


class EffectiveMediaPolicyResponseSchema(ApiModel):
    platform: str
    guild_id: str
    media: MediaRulePolicy
    source: str
    schema_version: str
    defaults_version: str
    revision: int
    updated_at: datetime | None
    updated_by: str | None
    runtime: MediaRuntimeStatusSchema
