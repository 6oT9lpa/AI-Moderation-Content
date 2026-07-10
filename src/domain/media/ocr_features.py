from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class OcrFeatures:
    text_density: float
    money_amounts: tuple[str, ...]
    domains: tuple[str, ...]
    casino_keywords: tuple[str, ...]
    money_keywords: tuple[str, ...]
    bonus_keywords: tuple[str, ...]
    payment_keywords: tuple[str, ...]
    fake_news_keywords: tuple[str, ...]
    crypto_keywords: tuple[str, ...]

    @property
    def has_casino(self) -> bool:
        return bool(self.casino_keywords)

    @property
    def has_money_amount(self) -> bool:
        return bool(self.money_amounts or self.money_keywords)

    @property
    def has_bonus_or_promo(self) -> bool:
        return bool(self.bonus_keywords)

    @property
    def has_payment_words(self) -> bool:
        return bool(self.payment_keywords)

    @property
    def has_fake_news(self) -> bool:
        return bool(self.fake_news_keywords)

    @property
    def has_crypto(self) -> bool:
        return bool(self.crypto_keywords)

    def to_dict(self) -> dict[str, object]:
        return {
            "text_density": self.text_density,
            "money_amounts": list(self.money_amounts),
            "domains": list(self.domains),
            "casino_keywords": list(self.casino_keywords),
            "money_keywords": list(self.money_keywords),
            "bonus_keywords": list(self.bonus_keywords),
            "payment_keywords": list(self.payment_keywords),
            "fake_news_keywords": list(self.fake_news_keywords),
            "crypto_keywords": list(self.crypto_keywords),
            "has_casino": self.has_casino,
            "has_money_amount": self.has_money_amount,
            "has_bonus_or_promo": self.has_bonus_or_promo,
            "has_payment_words": self.has_payment_words,
            "has_fake_news": self.has_fake_news,
            "has_crypto": self.has_crypto,
        }
