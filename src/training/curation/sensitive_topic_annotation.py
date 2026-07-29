from __future__ import annotations

from dataclasses import dataclass

from src.domain.moderation.moderation_label import ModerationLabel


@dataclass(frozen=True)
class SensitiveTopicAnnotation:
    topics: tuple[str, ...] = ()
    labels: tuple[ModerationLabel, ...] = ()
    severity: int = 0
    reasons: tuple[str, ...] = ()
    requires_review: bool = False
