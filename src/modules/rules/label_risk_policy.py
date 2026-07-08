from pydantic import BaseModel, ConfigDict, Field


class LabelRiskPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    SAFE: float = Field(default=0.0, ge=0.0)
    SPAM: float = Field(default=10.0, ge=0.0)
    ADVERTISEMENT: float = Field(default=10.0, ge=0.0)
    INVITE: float = Field(default=10.0, ge=0.0)
    SCAM: float = Field(default=10.0, ge=0.0)
    TOXIC: float = Field(default=10.0, ge=0.0)
    HATE: float = Field(default=10.0, ge=0.0)
    THREAT: float = Field(default=10.0, ge=0.0)
    NSFW: float = Field(default=10.0, ge=0.0)
    EVASION: float = Field(default=10.0, ge=0.0)
    FLOOD: float = Field(default=10.0, ge=0.0)
    URL: float = Field(default=10.0, ge=0.0)
    IMAGE_SCAM: float = Field(default=10.0, ge=0.0)
