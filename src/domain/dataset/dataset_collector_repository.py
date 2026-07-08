from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.dataset.dataset_collection_record import DatasetCollectionRecord
from src.domain.dto.dataset.dataset_collection_result import DatasetCollectionResult


class DatasetCollectorRepository(ABC):
    @abstractmethod
    async def save_collection(
        self,
        record: DatasetCollectionRecord,
    ) -> DatasetCollectionResult:
        raise NotImplementedError
