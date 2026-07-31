from abc import ABC, abstractmethod

from src.domain.media.media_analysis_record import MediaAnalysisRecord
from src.domain.media.media_analysis_stage import MediaAnalysisStage


class MediaAnalysisResultRepository(ABC):
    @abstractmethod
    async def save(self, record: MediaAnalysisRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_compatible(
        self,
        event_id: int,
        attachment_id: str,
        stage: MediaAnalysisStage,
        model_name: str,
        model_version: str,
        input_version: str,
        policy_version: str,
    ) -> MediaAnalysisRecord | None:
        raise NotImplementedError

