from __future__ import annotations

from enum import StrEnum


class ScamSubtype(StrEnum):
    CASINO_BONUS = "casino_bonus"
    CRYPTO_SCAM = "crypto_scam"
    FAKE_GIVEAWAY = "fake_giveaway"
    FAKE_PAYMENT_PROOF = "fake_payment_proof"
    FAKE_NEWS_AD = "fake_news_ad"
