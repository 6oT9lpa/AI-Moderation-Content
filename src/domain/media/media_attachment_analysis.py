from __future__ import annotations

from dataclasses import dataclass

from src.domain.media.image_hashes import ImageHashes
from src.domain.media.image_metadata import ImageMetadata
from src.domain.media.known_scam_image_match import KnownScamImageMatch
from src.domain.media.ocr_features import OcrFeatures
from src.domain.media.ocr_result import OcrResult


@dataclass(slots=True, frozen=True)
class MediaAttachmentAnalysis:
    attachment_id: str
    metadata: ImageMetadata
    hashes: ImageHashes
    ocr_result: OcrResult
    ocr_features: OcrFeatures
    known_scam_match: KnownScamImageMatch | None = None

    @property
    def known_scam_hash_match(self) -> bool:
        return self.known_scam_match is not None

    def to_dict(self, *, include_ocr_text: bool = True) -> dict[str, object]:
        return {
            "attachment_id": self.attachment_id,
            "metadata": self.metadata.to_dict(),
            "hashes": self.hashes.to_dict(),
            "ocr_text": self.ocr_result.text if include_ocr_text else None,
            "ocr_language": self.ocr_result.language,
            "ocr_confidence": self.ocr_result.confidence,
            "ocr_status": self.ocr_result.status.value,
            "ocr_error": self.ocr_result.error,
            "ocr_features": self.ocr_features.to_dict(),
            "known_scam_hash_match": self.known_scam_hash_match,
            "known_scam_match": self.known_scam_match.to_dict() if self.known_scam_match else None,
        }
