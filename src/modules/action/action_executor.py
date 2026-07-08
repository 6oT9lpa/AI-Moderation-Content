from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable

from src.domain.action.action_execution_log_repository import ActionExecutionLogRepository
from src.domain.dto.action.action_execution_plan_result import ActionExecutionPlanResult
from src.domain.dto.action.action_execution_request import ActionExecutionRequest
from src.domain.dto.action.action_execution_result import ActionExecutionResult
from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.dto.action.action_execution_step import ActionExecutionStep
from src.domain.action.action_policy import ActionPolicy
from src.domain.moderation.moderation_action import ModerationAction
from src.infrastructure.logging.logger import get_logger
from src.modules.action.dry_run_action_client import DryRunActionClient
from src.modules.action.platform_action_client import PlatformActionClient

logger = get_logger(__name__)


class ActionExecutor:
    def __init__(
        self,
        action_policy: ActionPolicy,
        platform_client: PlatformActionClient,
        *,
        dry_run_client: PlatformActionClient | None = None,
        log_repository: ActionExecutionLogRepository | None = None,
    ) -> None:
        self._action_policy = action_policy
        self._platform_client = platform_client
        self._dry_run_client = dry_run_client or DryRunActionClient()
        self._log_repository = log_repository

    async def execute(self, request: ActionExecutionRequest) -> ActionExecutionPlanResult:
        decision = request.moderation_decision
        logger.info(
            "Action execution started message_id=%s decision_action=%s dry_run=%s enabled=%s",
            request.message_id,
            decision.decision_action,
            self._action_policy.dry_run,
            self._action_policy.enabled,
        )

        steps: list[ActionExecutionStep] = []

        if not self._action_policy.enabled:
            steps = [
                self._build_step(action, ActionExecutionStatus.SKIPPED, "Action policy disabled")
                for action in decision.action_plan.actions
            ]
        else:
            for action in decision.action_plan.actions:
                action_steps = await self._execute_action(action, request)
                steps.extend(action_steps)

        result = ActionExecutionPlanResult(
            message_id=request.message_id,
            decision_action=decision.decision_action,
            executed_actions=self._extract_executed_actions(steps),
            status=self._resolve_plan_status(steps),
            dry_run=self._action_policy.dry_run,
            steps=steps,
        )

        await self._save_execution_log(request, result)

        logger.info(
            "Action execution finished message_id=%s status=%s executed_actions=%s",
            result.message_id,
            result.status,
            [action.value for action in result.executed_actions],
        )
        return result

    async def _execute_action(
        self,
        action: ModerationAction,
        request: ActionExecutionRequest,
    ) -> list[ActionExecutionStep]:
        if action == ModerationAction.IGNORE:
            return [self._build_step(action, ActionExecutionStatus.SKIPPED, "IGNORE is a no-op")]

        if not self._action_policy.is_allowed(action):
            logger.warning("Action skipped by policy action=%s message_id=%s", action, request.message_id)
            return [self._build_step(action, ActionExecutionStatus.SKIPPED, "Action is not allowed by ActionPolicy")]

        if self._action_policy.requires_review(action):
            return await self._route_to_review(action, request)

        if self._action_policy.dry_run:
            logger.info("Action dry-run step action=%s message_id=%s", action, request.message_id)
            return [await self._call_dry_run(action, request)]

        return [await self._call_platform(action, request)]

    async def _route_to_review(
        self,
        action: ModerationAction,
        request: ActionExecutionRequest,
    ) -> list[ActionExecutionStep]:
        if not self._action_policy.is_allowed(ModerationAction.REVIEW):
            return [self._build_step(
                action,
                ActionExecutionStatus.SKIPPED,
                "Action requires review, but REVIEW is not allowed",
            )]

        review_step = await self._execute_review(request, f"{action.value} requires manual review")
        logger.warning(
            "Destructive action routed to review action=%s message_id=%s review_status=%s",
            action,
            request.message_id,
            review_step.status,
        )

        if review_step.status in {ActionExecutionStatus.SUCCESS, ActionExecutionStatus.DRY_RUN}:
            skipped_step = self._build_step(
                action,
                ActionExecutionStatus.SKIPPED,
                f"{action.value} requires manual review",
                platform_response=review_step.platform_response,
            )
            return [review_step, skipped_step]

        failed_step = self._build_step(
            action,
            ActionExecutionStatus.FAILED,
            f"{action.value} review routing failed",
            error=review_step.error,
        )
        return [review_step, failed_step]

    async def _execute_review(self, request: ActionExecutionRequest, reason: str) -> ActionExecutionStep:
        if self._action_policy.dry_run:
            return await self._call_dry_run(ModerationAction.REVIEW, request, reason=reason)

        return await self._call_platform(ModerationAction.REVIEW, request, reason=reason)

    async def _call_dry_run(
        self,
        action: ModerationAction,
        request: ActionExecutionRequest,
        *,
        reason: str | None = None,
    ) -> ActionExecutionStep:
        action_call = self._get_action_call(action, self._dry_run_client)
        result = await action_call(request)
        return self._build_step(
            action,
            ActionExecutionStatus.DRY_RUN,
            reason or "ActionPolicy dry_run enabled",
            platform_response=result.platform_response,
            error=result.error,
        )

    async def _call_platform(
        self,
        action: ModerationAction,
        request: ActionExecutionRequest,
        *,
        reason: str | None = None,
    ) -> ActionExecutionStep:
        started_at = datetime.now(timezone.utc)
        action_call = self._get_action_call(action, self._platform_client)
        timeout_seconds = self._action_policy.action_timeouts.get(action)
        attempts = self._action_policy.retry_policy.max_attempts
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "Executing platform action action=%s attempt=%s/%s message_id=%s",
                    action,
                    attempt,
                    attempts,
                    request.message_id,
                )
                result = await self._call_with_timeout(action_call(request), timeout_seconds)
                return self._build_step(
                    action,
                    result.status,
                    reason or request.reason,
                    started_at=started_at,
                    platform_response=result.platform_response,
                    error=result.error,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Platform action failed action=%s attempt=%s/%s message_id=%s error=%s",
                    action,
                    attempt,
                    attempts,
                    request.message_id,
                    exc,
                    exc_info=True,
                )

                if attempt < attempts and self._action_policy.retry_policy.backoff_seconds:
                    await asyncio.sleep(self._action_policy.retry_policy.backoff_seconds)

        return self._build_step(
            action,
            ActionExecutionStatus.FAILED,
            reason or request.reason,
            started_at=started_at,
            error=last_error or "Action failed",
        )

    async def _call_with_timeout(
        self,
        operation: Awaitable[ActionExecutionResult],
        timeout_seconds: float | None,
    ) -> ActionExecutionResult:
        if timeout_seconds is None:
            return await operation

        return await asyncio.wait_for(operation, timeout=timeout_seconds)

    def _get_action_call(
        self,
        action: ModerationAction,
        client: PlatformActionClient,
    ) -> Callable[[ActionExecutionRequest], Awaitable[ActionExecutionResult]]:
        action_calls = {
            ModerationAction.DELETE: client.delete_message,
            ModerationAction.WARN: client.warn_user,
            ModerationAction.TIMEOUT: client.timeout_user,
            ModerationAction.BAN: client.ban_user,
            ModerationAction.REVIEW: client.create_review,
            ModerationAction.LOG: client.log_action,
        }

        if action not in action_calls:
            raise ValueError(f"Unsupported executable action: {action}")

        return action_calls[action]

    def _build_step(
        self,
        action: ModerationAction,
        status: ActionExecutionStatus,
        reason: str,
        *,
        started_at: datetime | None = None,
        platform_response: dict[str, object] | None = None,
        error: str | None = None,
    ) -> ActionExecutionStep:
        return ActionExecutionStep(
            action=action,
            status=status,
            reason=reason,
            started_at=started_at or datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            platform_response=dict(platform_response or {}),
            error=error,
        )

    def _extract_executed_actions(self, steps: list[ActionExecutionStep]) -> list[ModerationAction]:
        return [
            step.action
            for step in steps
            if step.status in {ActionExecutionStatus.SUCCESS, ActionExecutionStatus.DRY_RUN}
        ]

    def _resolve_plan_status(self, steps: list[ActionExecutionStep]) -> ActionExecutionStatus:
        if not steps:
            return ActionExecutionStatus.SKIPPED

        statuses = {step.status for step in steps}

        if statuses == {ActionExecutionStatus.DRY_RUN}:
            return ActionExecutionStatus.DRY_RUN

        if ActionExecutionStatus.FAILED in statuses:
            if any(status in statuses for status in {ActionExecutionStatus.SUCCESS, ActionExecutionStatus.DRY_RUN}):
                return ActionExecutionStatus.PARTIAL_SUCCESS
            return ActionExecutionStatus.FAILED

        if statuses == {ActionExecutionStatus.SUCCESS}:
            return ActionExecutionStatus.SUCCESS

        if statuses == {ActionExecutionStatus.SKIPPED}:
            return ActionExecutionStatus.SKIPPED

        return ActionExecutionStatus.PARTIAL_SUCCESS

    async def _save_execution_log(
        self,
        request: ActionExecutionRequest,
        result: ActionExecutionPlanResult,
    ) -> None:
        if self._log_repository is None:
            return

        try:
            await self._log_repository.save_plan_result(request, result)
        except Exception as exc:
            logger.error(
                "Failed to save action execution log message_id=%s error=%s",
                request.message_id,
                exc,
                exc_info=True,
            )
            raise
