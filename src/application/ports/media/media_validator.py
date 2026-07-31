from abc import ABC, abstractmethod

from src.domain.media.downloaded_media import DownloadedMedia
from src.domain.media.validated_media import ValidatedMedia


class MediaValidator(ABC):
    @abstractmethod
    async def validate(self, downloaded: DownloadedMedia) -> ValidatedMedia:
        raise NotImplementedError

