from enum import StrEnum


class MediaAnalysisStage(StrEnum):
    OCR = "ocr"
    IMAGE = "image"
    RULE_ENGINE = "rule_engine"

