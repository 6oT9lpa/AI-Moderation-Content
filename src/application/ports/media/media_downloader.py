from abc import ABC, abstractmethod

from src.domain.media.downloaded_media import DownloadedMedia
from src.domain.media.media_attachment import MediaAttachment


class MediaDownloader(ABC):
    @abstractmethod
    async def download(self, attachment: MediaAttachment) -> DownloadedMedia:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

