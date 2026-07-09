from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.rubert.rubert_label_schema import RuBertLabelSchema


class RuBertModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    base_model_name: str = "cointegrated/rubert-tiny2"
    base_model_revision: str = "e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae"
    local_base_dir: Path = Path("models/rubert-tiny2")
    classifier_output_dir: Path = Path("models/rubert-tiny2-moderation-init")
    max_length: int = Field(default=256, gt=0)
    problem_type: str = "multi_label_classification"


class RuBertTrainerConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    train_batch_size: int = Field(default=8, gt=0)
    eval_batch_size: int = Field(default=16, gt=0)
    gradient_accumulation_steps: int = Field(default=2, gt=0)
    learning_rate: float = Field(default=3e-5, gt=0)
    num_train_epochs: int = Field(default=4, gt=0)
    warmup_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    weight_decay: float = Field(default=0.01, ge=0.0)
    fp16: bool = True
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class RuBertTrainingConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: RuBertModelConfig = Field(default_factory=RuBertModelConfig)
    training: RuBertTrainerConfig = Field(default_factory=RuBertTrainerConfig)
    label_schema: RuBertLabelSchema = Field(default_factory=RuBertLabelSchema)

    @classmethod
    def load(cls, path: str | Path = "configs/training/rubert_tiny2.yaml") -> "RuBertTrainingConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        labels = data.pop("labels", None)
        if labels is not None:
            data["label_schema"] = {
                "labels": [ModerationLabel(label) for label in labels],
            }

        return cls.model_validate(data)

    def to_transformers_metadata(self) -> dict[str, Any]:
        return {
            "num_labels": self.label_schema.num_labels,
            "id2label": self.label_schema.id2label,
            "label2id": self.label_schema.label2id,
            "problem_type": self.model.problem_type,
        }
