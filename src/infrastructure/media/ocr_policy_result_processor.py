from src.application.ports.media.ocr_policy_processor import OcrPolicyProcessor
from src.domain.media.media_rule_policy import OcrRuleSettings
from src.domain.media.ocr_result import OcrResult
from src.infrastructure.media.ocr_text_processor import OcrTextProcessor


class OcrPolicyResultProcessor(OcrPolicyProcessor):
    def __init__(self, text_processor: OcrTextProcessor) -> None:
        self._text_processor = text_processor

    def apply(self, result: OcrResult, policy: OcrRuleSettings) -> OcrResult | None:
        lines = list(result.lines)
        if policy.processing.discard_low_confidence_lines:
            lines = [line for line in lines if line.confidence >= policy.processing.min_line_confidence]
        lines = lines[: policy.processing.max_lines]
        if not lines and not policy.processing.process_empty_result:
            return None
        separator = "\n" if policy.processing.preserve_line_breaks else " "
        raw_text = separator.join(line.text for line in lines)[: policy.processing.max_text_length]
        mean_confidence = sum(line.confidence for line in lines) / len(lines) if lines else None
        if mean_confidence is not None and mean_confidence < policy.processing.min_mean_confidence:
            return None
        processed = self._text_processor.process(raw_text)
        if len(processed.normalized_text) < policy.processing.min_text_length:
            return None
        return result.model_copy(
            update={
                "lines": tuple(lines),
                "text": processed.normalized_text,
                "redacted_text": processed.redacted_text,
                "text_hash": processed.text_hash,
                "language": processed.language,
                "confidence": mean_confidence,
                "flags": processed.flags,
            }
        )
