from pydantic import BaseModel, ConfigDict, Field


class UserRiskPolicy(BaseModel):
    """Contextual multiplier for harmful signals; never creates a violation alone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    new_account_days: int = Field(default=7, ge=0)
    new_member_days: int = Field(default=7, ge=0)
    recent_violation_count_key: str = Field(default="recent_violation_count", min_length=1)
    violation_threshold: int = Field(default=3, ge=1)
    new_account_multiplier: float = Field(default=1.15, ge=1.0)
    new_member_multiplier: float = Field(default=1.1, ge=1.0)
    repeat_violation_multiplier: float = Field(default=1.35, ge=1.0)
    max_multiplier: float = Field(default=1.75, ge=1.0)
