from abc import ABC, abstractmethod

from src.domain.media.downloaded_media import DownloadedMedia
from src.domain.media.media_hashes import MediaHashes
from src.domain.media.validated_media import ValidatedMedia


class MediaHasher(ABC):
    @abstractmethod
    async def calculate(self, downloaded: DownloadedMedia, validated: ValidatedMedia) -> MediaHashes:
        raise NotImplementedError

