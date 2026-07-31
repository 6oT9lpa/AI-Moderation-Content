from abc import ABC, abstractmethod

from src.domain.media.image_detection_input import ImageDetectionInput
from src.domain.media.image_detection_result import ImageDetectionResult


class ImageDetectionProvider(ABC):
    @property
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def analyze(self, input_image: ImageDetectionInput) -> ImageDetectionResult:
        raise NotImplementedError

    async def close(self) -> None:
        return None

