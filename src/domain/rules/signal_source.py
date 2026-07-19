from enum import Enum


class SignalSource(str, Enum):
    PREPROCESSING = "PREPROCESSING"
    RUBERT = "RUBERT"
    QWEN = "QWEN"
    OCR = "OCR"
    IMAGE = "IMAGE"
    HISTORY = "HISTORY"
    MANUAL = "MANUAL"
    PHISHING = "PHISHING"
