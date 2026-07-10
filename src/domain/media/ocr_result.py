from __future__ import annotations

from dataclasses import dataclass

from src.domain.media.ocr_status import OcrStatus


@dataclass(slots=True, frozen=True)
class OcrResult:
    text: str = ""
    language: str | None = None
    confidence: float | None = None
    status: OcrStatus = OcrStatus.COMPLETED
    error: str | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
