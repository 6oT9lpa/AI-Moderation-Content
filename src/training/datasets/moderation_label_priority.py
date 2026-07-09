from __future__ import annotations

from collections.abc import Iterable

from src.domain.moderation.moderation_label import ModerationLabel


DEFAULT_PRIMARY_LABEL_PRIORITY: tuple[ModerationLabel, ...] = (
    ModerationLabel.THREAT,
    ModerationLabel.HATE,
    ModerationLabel.SCAM,
    ModerationLabel.NSFW,
    ModerationLabel.TOXIC,
    ModerationLabel.INVITE,
    ModerationLabel.FLOOD,
    ModerationLabel.SPAM,
    ModerationLabel.ADVERTISEMENT,
    ModerationLabel.URL,
    ModerationLabel.EVASION,
    ModerationLabel.SAFE,
)


def resolve_primary_label(
    labels: Iterable[ModerationLabel],
    *,
    fallback: ModerationLabel = ModerationLabel.SAFE,
) -> ModerationLabel:
    selected = list(labels)
    if not selected:
        return fallback

    priority_map = {label: index for index, label in enumerate(DEFAULT_PRIMARY_LABEL_PRIORITY)}
    return min(selected, key=lambda label: priority_map.get(label, len(priority_map)))
