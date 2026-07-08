from __future__ import annotations

from src.domain.dataset.dataset_collector_repository import DatasetCollectorRepository
from src.domain.dto.dataset.dataset_collection_record import DatasetCollectionRecord
from src.domain.dto.dataset.dataset_collection_result import DatasetCollectionResult


class InMemoryDatasetCollectorRepository(DatasetCollectorRepository):
    def __init__(self) -> None:
        self.records: list[DatasetCollectionRecord] = []
        self._next_event_id = 1

    async def save_collection(
        self,
        record: DatasetCollectionRecord,
    ) -> DatasetCollectionResult:
        event_id = self._next_event_id
        self._next_event_id += 1
        self.records.append(record)

        return DatasetCollectionResult(
            event_id=event_id,
            decision_id=None,
            training_example=record.training_example.model_copy(update={"event_id": event_id}),
        )
