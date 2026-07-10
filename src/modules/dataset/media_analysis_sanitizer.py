from __future__ import annotations

from typing import Any

from src.domain.media.media_analysis_result import MediaAnalysisResult
from src.infrastructure.logging import get_logger
from src.modules.dataset.dataset_text_sanitizer import DatasetTextSanitizer

logger = get_logger(__name__)


class MediaAnalysisSanitizer:
    def __init__(self, text_sanitizer: DatasetTextSanitizer | None = None) -> None:
        self._text_sanitizer = text_sanitizer or DatasetTextSanitizer()

    def sanitize(self, analysis: MediaAnalysisResult) -> dict[str, Any]:
        audit = analysis.to_dict()
        attachment_audits = audit.get("attachments", [])
        redacted_attachment_count = 0
        for attachment_audit in attachment_audits:
            if not isinstance(attachment_audit, dict):
                continue
            ocr_text = attachment_audit.get("ocr_text")
            if isinstance(ocr_text, str) and ocr_text:
                sanitized_text = self._text_sanitizer.sanitize_unstructured_text(ocr_text)
                if sanitized_text != ocr_text:
                    redacted_attachment_count += 1
                attachment_audit["ocr_text"] = sanitized_text
            ocr_error = attachment_audit.get("ocr_error")
            if isinstance(ocr_error, str) and ocr_error:
                attachment_audit["ocr_error"] = self._text_sanitizer.sanitize_unstructured_text(ocr_error)
        logger.info(
            "Media analysis audit sanitized attachment_count=%s redacted_attachment_count=%s",
            len(attachment_audits),
            redacted_attachment_count,
        )
        return audit
