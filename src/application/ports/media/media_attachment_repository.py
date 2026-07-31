from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.media.media_attachment_record import MediaAttachmentRecord


class MediaAttachmentRepository(ABC):
    @abstractmethod
    async def save(self, record: MediaAttachmentRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_identity(self, event_id: int, attachment_id: str) -> MediaAttachmentRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def find_recent_by_hash(
        self,
        guild_id: str,
        sha256: str,
        not_before: datetime,
    ) -> MediaAttachmentRecord | None:
        raise NotImplementedError

