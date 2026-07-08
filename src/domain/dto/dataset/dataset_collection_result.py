from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.domain.dto.dataset.training_example import TrainingExample


class DatasetCollectionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: int
    decision_id: int | None = None
    training_example: TrainingExample
