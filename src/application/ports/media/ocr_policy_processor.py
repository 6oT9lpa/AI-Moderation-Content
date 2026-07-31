from abc import ABC, abstractmethod

from src.domain.media.media_rule_policy import OcrRuleSettings
from src.domain.media.ocr_result import OcrResult


class OcrPolicyProcessor(ABC):
    @abstractmethod
    def apply(self, result: OcrResult, policy: OcrRuleSettings) -> OcrResult | None:
        raise NotImplementedError
