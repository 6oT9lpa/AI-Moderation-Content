from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.moderation.moderation_label import ModerationLabel


class RuBertLabelSchema(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    labels: list[ModerationLabel] = Field(default_factory=lambda: list(ModerationLabel))

    @model_validator(mode="after")
    def validate_unique_labels(self) -> "RuBertLabelSchema":
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("ruBERT labels must be unique")

        return self

    @property
    def label2id(self) -> dict[str, int]:
        return {label.value: index for index, label in enumerate(self.labels)}

    @property
    def id2label(self) -> dict[int, str]:
        return {index: label.value for index, label in enumerate(self.labels)}

    @property
    def num_labels(self) -> int:
        return len(self.labels)

    def encode_labels(self, labels: list[ModerationLabel]) -> list[float]:
        selected = {label.value for label in labels}
        return [
            1.0 if label.value in selected else 0.0
            for label in self.labels
        ]
