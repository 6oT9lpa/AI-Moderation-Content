from abc import ABC, abstractmethod

from src.domain.media.ocr_input import OcrInput
from src.domain.media.ocr_result import OcrResult


class OcrProvider(ABC):
    @property
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def analyze(self, input_image: OcrInput) -> OcrResult:
        raise NotImplementedError

    async def close(self) -> None:
        return None

