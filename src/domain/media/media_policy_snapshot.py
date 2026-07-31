from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.media.media_rule_policy import MediaRulePolicy


class MediaPolicySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    platform: Literal["discord"]
    guild_id: str = Field(pattern=r"^[0-9]{1,32}$")
    schema_version: Literal["media-policy-v1"]
    defaults_version: str = Field(min_length=1, max_length=260)
    revision: int = Field(ge=1)
    policy: MediaRulePolicy
    created_at: datetime
    updated_at: datetime
    updated_by: str = Field(min_length=1, max_length=64)


class EffectiveMediaPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    platform: Literal["discord"]
    guild_id: str = Field(pattern=r"^[0-9]{1,32}$")
    media: MediaRulePolicy
    source: Literal["YAML_DEFAULT", "DATABASE"]
    schema_version: Literal["media-policy-v1"] = "media-policy-v1"
    defaults_version: str
    revision: int = Field(ge=0)
    updated_at: datetime | None = None
    updated_by: str | None = None
