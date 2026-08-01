from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.api.stored_moderation_event import StoredModerationEvent
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel


class ModerationEventRepository(ABC):
    @abstractmethod
    async def save_request_lineage(self, event_id: int, correlation_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_event(
        self,
        event_id: int | None,
        message_id: str | None,
        guild_id: str | None,
    ) -> StoredModerationEvent | None:
        raise NotImplementedError

    @abstractmethod
    async def save_feedback(
        self,
        event: StoredModerationEvent,
        feedback_type: FeedbackType,
        labels: tuple[ModerationLabel, ...],
        primary_label: ModerationLabel | None,
        severity: int | None,
        recommended_action: ModerationAction | None,
        moderator_id: str | None,
        annotation_source: str | None,
        notes: str | None,
        idempotency_key: str | None,
        correlation_id: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def save_action_result(
        self,
        event: StoredModerationEvent,
        action: ModerationAction,
        status: ActionExecutionStatus,
        dry_run: bool,
        error: str | None,
        timestamp: datetime,
        correlation_id: str,
    ) -> None:
        raise NotImplementedError
