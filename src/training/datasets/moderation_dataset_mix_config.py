from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.domain.moderation.moderation_label import ModerationLabel


class ModerationDatasetSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "rubert_moderation_v1"
    output_dir: Path = Path("data/exports/rubert_moderation_v1")
    total_examples: int = Field(default=10000, gt=0)
    negative_examples: int = Field(default=6000, gt=0)
    safe_examples: int = Field(default=4000, gt=0)
    random_seed: int = 42
    strict: bool = True

    @model_validator(mode="after")
    def validate_total(self) -> "ModerationDatasetSpec":
        if self.negative_examples + self.safe_examples != self.total_examples:
            raise ValueError("negative_examples + safe_examples must equal total_examples")

        return self


class DatasetSourceSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    enabled: bool = True


class DatasetQualitySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    deduplicate_by_text: bool = True
    min_text_length: int = Field(default=3, ge=0)
    max_text_length: int = Field(default=512, gt=0)
    test_allowed_sources: set[str] = Field(default_factory=set)


class ModerationDatasetMixConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset: ModerationDatasetSpec = Field(default_factory=ModerationDatasetSpec)
    splits: dict[str, float]
    negative_class_distribution: dict[ModerationLabel, float]
    source_distribution: dict[str, float]
    sources: dict[str, DatasetSourceSpec]
    quality: DatasetQualitySpec = Field(default_factory=DatasetQualitySpec)

    @classmethod
    def load(cls, path: str | Path = "configs/training/dataset_mix_v1.yaml") -> "ModerationDatasetMixConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    @model_validator(mode="after")
    def validate_ratios(self) -> "ModerationDatasetMixConfig":
        self._assert_sum("splits", self.splits)
        self._assert_sum("negative_class_distribution", self.negative_class_distribution)
        self._assert_sum("source_distribution", self.source_distribution)

        if ModerationLabel.SAFE in self.negative_class_distribution:
            raise ValueError("negative_class_distribution must not include SAFE")

        return self

    def negative_class_quotas(self) -> dict[ModerationLabel, int]:
        return self._quotas(self.negative_class_distribution, self.dataset.negative_examples)

    def source_quotas(self) -> dict[str, int]:
        return self._quotas(self.source_distribution, self.dataset.total_examples)

    def split_quotas(self) -> dict[str, int]:
        return self._quotas(self.splits, self.dataset.total_examples)

    def _quotas(self, ratios: dict, total: int) -> dict:
        raw = {key: value * total for key, value in ratios.items()}
        quotas = {key: int(value) for key, value in raw.items()}
        remainder = total - sum(quotas.values())

        for key, _ in sorted(raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True):
            if remainder <= 0:
                break
            quotas[key] += 1
            remainder -= 1

        return quotas

    def _assert_sum(self, name: str, ratios: dict) -> None:
        total = sum(ratios.values())
        if abs(total - 1.0) > 0.0001:
            raise ValueError(f"{name} ratios must sum to 1.0, got {total}")
