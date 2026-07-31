from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.moderation.moderation_label import ModerationLabel


class MediaRulePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    required: bool = False
    allow_partial_results: bool = True
    image_class_to_label: dict[str, ModerationLabel] = Field(
        default_factory=lambda: {
            "explicit": ModerationLabel.NSFW,
            "sexual": ModerationLabel.NSFW,
            "casino": ModerationLabel.SCAM,
            "gambling": ModerationLabel.SCAM,
            "scam-banner": ModerationLabel.SCAM,
            "fake-win": ModerationLabel.SCAM,
        }
    )
    image_class_thresholds: dict[str, float] = Field(default_factory=dict)

    @field_validator("image_class_to_label")
    @classmethod
    def validate_image_mapping(cls, mapping: dict[str, ModerationLabel]) -> dict[str, ModerationLabel]:
        normalized = {detector_class.strip().casefold(): label for detector_class, label in mapping.items()}
        if any(not detector_class for detector_class in normalized):
            raise ValueError("image detector class must not be empty")
        if any(label not in {ModerationLabel.SCAM, ModerationLabel.NSFW} for label in normalized.values()):
            raise ValueError("image detector classes may map only to SCAM or NSFW")
        return normalized

    @field_validator("image_class_thresholds")
    @classmethod
    def validate_image_thresholds(cls, thresholds: dict[str, float]) -> dict[str, float]:
        normalized = {detector_class.strip().casefold(): threshold for detector_class, threshold in thresholds.items()}
        if any(not 0.0 <= threshold <= 1.0 for threshold in normalized.values()):
            raise ValueError("image class thresholds must be between 0 and 1")
        return normalized

