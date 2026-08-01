from dataclasses import dataclass

from src.domain.moderation.moderation_action import ModerationAction


@dataclass(frozen=True, slots=True)
class StoredModerationEvent:
    event_id: int
    decision_id: int
    guild_id: str
    message_id: str
    decision_action: ModerationAction
