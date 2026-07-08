from __future__ import annotations

from src.domain.dto.action.action_execution_request import ActionExecutionRequest
from src.domain.dto.action.action_execution_result import ActionExecutionResult
from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.action.action_policy import ActionPolicy
from src.domain.decision.moderation_decision import ModerationDecision
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.model_agreement import ModelAgreement
from src.domain.rules.rule_evaluation_result import RuleEvaluationResult
from src.modules.action.action_executor import ActionExecutor
from src.modules.action.platform_action_client import PlatformActionClient
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.decision.decision_policy import DecisionPolicy


class RecordingActionClient(PlatformActionClient):
    def __init__(self, *, fail_actions: set[ModerationAction] | None = None) -> None:
        self.calls: list[ModerationAction] = []
        self._fail_actions = fail_actions or set()

    async def delete_message(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._record(ModerationAction.DELETE)

    async def warn_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._record(ModerationAction.WARN)

    async def timeout_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._record(ModerationAction.TIMEOUT)

    async def ban_user(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._record(ModerationAction.BAN)

    async def create_review(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._record(ModerationAction.REVIEW)

    async def log_action(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return self._record(ModerationAction.LOG)

    def _record(self, action: ModerationAction) -> ActionExecutionResult:
        self.calls.append(action)

        if action in self._fail_actions:
            return ActionExecutionResult(status=ActionExecutionStatus.FAILED, error=f"{action.value} failed")

        return ActionExecutionResult(
            status=ActionExecutionStatus.SUCCESS,
            platform_response={"action": action.value},
        )


async def test_dry_run_does_not_call_real_client(structured_test_logger):
    client = RecordingActionClient()
    executor = ActionExecutor(_action_policy(dry_run=True), client)

    result = await executor.execute(_request(_decision([ModerationAction.DELETE])))

    structured_test_logger(
        "action",
        {
            "expected_calls": [],
            "actual_calls": client.calls,
            "expected_status": ActionExecutionStatus.DRY_RUN,
            "actual_status": result.status,
        },
    )
    assert client.calls == []
    assert result.status == ActionExecutionStatus.DRY_RUN
    assert result.steps[0].status == ActionExecutionStatus.DRY_RUN


async def test_delete_and_warn_execute_in_order():
    client = RecordingActionClient()
    executor = ActionExecutor(_action_policy(), client)

    result = await executor.execute(_request(_decision([ModerationAction.DELETE, ModerationAction.WARN])))

    assert client.calls == [ModerationAction.DELETE, ModerationAction.WARN]
    assert result.status == ActionExecutionStatus.SUCCESS
    assert [step.action for step in result.steps] == [ModerationAction.DELETE, ModerationAction.WARN]


async def test_ban_with_required_review_is_not_executed_and_goes_to_review():
    client = RecordingActionClient()
    executor = ActionExecutor(_action_policy(require_review_for_actions=[ModerationAction.BAN]), client)

    result = await executor.execute(_request(_decision([ModerationAction.BAN])))

    assert client.calls == [ModerationAction.REVIEW]
    assert [step.action for step in result.steps] == [ModerationAction.REVIEW, ModerationAction.BAN]
    assert [step.status for step in result.steps] == [
        ActionExecutionStatus.SUCCESS,
        ActionExecutionStatus.SKIPPED,
    ]
    assert result.status == ActionExecutionStatus.PARTIAL_SUCCESS


async def test_forbidden_action_is_skipped():
    client = RecordingActionClient()
    policy = _action_policy(allowed_actions=[ModerationAction.LOG, ModerationAction.REVIEW])
    executor = ActionExecutor(policy, client)

    result = await executor.execute(_request(_decision([ModerationAction.DELETE])))

    assert client.calls == []
    assert result.status == ActionExecutionStatus.SKIPPED
    assert result.steps[0].status == ActionExecutionStatus.SKIPPED


async def test_one_failed_step_returns_partial_success():
    client = RecordingActionClient(fail_actions={ModerationAction.WARN})
    executor = ActionExecutor(_action_policy(), client)

    result = await executor.execute(_request(_decision([ModerationAction.DELETE, ModerationAction.WARN])))

    assert client.calls == [ModerationAction.DELETE, ModerationAction.WARN]
    assert result.status == ActionExecutionStatus.PARTIAL_SUCCESS
    assert [step.status for step in result.steps] == [
        ActionExecutionStatus.SUCCESS,
        ActionExecutionStatus.FAILED,
    ]


async def test_full_success_returns_success():
    client = RecordingActionClient()
    executor = ActionExecutor(_action_policy(), client)

    result = await executor.execute(_request(_decision([ModerationAction.LOG])))

    assert client.calls == [ModerationAction.LOG]
    assert result.status == ActionExecutionStatus.SUCCESS


async def test_decision_engine_action_plan_is_passed_to_action_executor():
    policy = DecisionPolicy.model_validate(
        {
            "policy_id": "decision-test",
            "version": "1.0",
            "action_thresholds": {
                "IGNORE": 0,
                "LOG": 10,
                "REVIEW": 40,
                "WARN": 50,
                "DELETE": 70,
                "DELETE_WARN": 80,
                "TIMEOUT": 90,
                "BAN": 95,
            },
            "action_bundles": {
                "DELETE_WARN": ["DELETE", "WARN"],
            },
            "action_priority": ["BAN", "TIMEOUT", "DELETE_WARN", "DELETE", "WARN", "REVIEW", "LOG", "IGNORE"],
        }
    )
    decision = DecisionEngine(policy=policy).decide(
        "msg_decision_plan",
        _rule_result(risk_score=85.0),
    )
    client = RecordingActionClient()
    executor = ActionExecutor(_action_policy(), client)

    result = await executor.execute(_request(decision))

    assert decision.action_plan.actions == [ModerationAction.DELETE, ModerationAction.WARN]
    assert client.calls == [ModerationAction.DELETE, ModerationAction.WARN]
    assert result.status == ActionExecutionStatus.SUCCESS


def _action_policy(
    *,
    dry_run: bool = False,
    allowed_actions: list[ModerationAction] | None = None,
    require_review_for_actions: list[ModerationAction] | None = None,
) -> ActionPolicy:
    return ActionPolicy(
        policy_id="action-test",
        version="1.0",
        enabled=True,
        dry_run=dry_run,
        allowed_actions=allowed_actions
        or [
            ModerationAction.LOG,
            ModerationAction.REVIEW,
            ModerationAction.WARN,
            ModerationAction.DELETE,
            ModerationAction.TIMEOUT,
            ModerationAction.BAN,
        ],
        destructive_actions=[ModerationAction.DELETE, ModerationAction.TIMEOUT, ModerationAction.BAN],
        require_review_for_actions=require_review_for_actions or [],
        retry_policy={"max_attempts": 1, "backoff_seconds": 0},
    )


def _request(decision: ModerationDecision) -> ActionExecutionRequest:
    return ActionExecutionRequest(
        moderation_decision=decision,
        platform="discord",
        guild_id="guild_1",
        channel_id="channel_1",
        message_id=decision.message_id,
        user_id="user_1",
        reason=decision.reason,
    )


def _decision(actions: list[ModerationAction]) -> ModerationDecision:
    rule_result = _rule_result()
    return DecisionEngine(
        policy=DecisionPolicy.model_validate(
            {
                "policy_id": "decision-test",
                "version": "1.0",
                "action_bundles": {
                    actions[0].value: [action.value for action in actions],
                },
                "label_overrides": {
                    "SPAM": actions[0].value,
                },
                "action_priority": ["BAN", "TIMEOUT", "DELETE", "WARN", "REVIEW", "LOG", "IGNORE"],
            }
        )
    ).decide("msg_action", rule_result)


def _rule_result(*, risk_score: float = 80.0) -> RuleEvaluationResult:
    return RuleEvaluationResult(
        signals=[],
        labels=[ModerationLabel.SPAM],
        primary_label=ModerationLabel.SPAM,
        confidence=0.95,
        severity=3,
        risk_score=risk_score,
        risk_breakdown=[],
        matched_rules=[],
        conflicts=[],
        model_agreement=ModelAgreement(agreeing_sources=[], disagreeing_sources=[], agreement_score=1.0),
        policy_id="rule-test",
        policy_version="1.0",
    )
