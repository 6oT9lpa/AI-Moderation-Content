from __future__ import annotations

import asyncio
from time import perf_counter

from src.application.api_conflict_error import ApiConflictError
from src.application.api_not_found_error import ApiNotFoundError
from src.application.api_resource_unavailable_error import ApiResourceUnavailableError
from src.contracts.api.action_result_request_schema import ActionResultRequestSchema
from src.contracts.api.api_ack_schema import ApiAckSchema
from src.contracts.api.effective_policy_response_schema import EffectivePolicyResponseSchema
from src.contracts.api.moderation_feedback_request_schema import ModerationFeedbackRequestSchema
from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema
from src.contracts.api.moderation_message_response_schema import ModerationMessageResponseSchema
from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.api.moderation_event_repository import ModerationEventRepository
from src.domain.dto.dataset.dataset_collection_input import DatasetCollectionInput
from src.domain.moderation.moderation_action import ModerationAction
from src.domain.policy.policy_type import PolicyType
from src.infrastructure.logging import get_logger
from src.modules.dataset.dataset_collector import DatasetCollector
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.policy.policy_resolver import PolicyResolver
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from src.training.rubert.rubert_moderation_classifier import RuBertModerationClassifier

logger = get_logger(__name__)


class ApiModerationService:
    def __init__(
        self,
        preprocessor: TextPreprocessor,
        rule_engine: ModerationRuleEngine,
        decision_engine: DecisionEngine,
        signal_adapter: PreprocessingSignalAdapter,
        dataset_collector: DatasetCollector,
        policy_resolver: PolicyResolver,
        event_repository: ModerationEventRepository,
        inference_semaphore: asyncio.Semaphore,
        rubert_classifier: RuBertModerationClassifier | None,
    ) -> None:
        self._preprocessor = preprocessor
        self._rule_engine = rule_engine
        self._decision_engine = decision_engine
        self._signal_adapter = signal_adapter
        self._dataset_collector = dataset_collector
        self._policy_resolver = policy_resolver
        self._event_repository = event_repository
        self._inference_semaphore = inference_semaphore
        self._rubert_classifier = rubert_classifier

    async def moderate(
        self,
        request: ModerationMessageRequestSchema,
        correlation_id: str,
    ) -> ModerationMessageResponseSchema:
        started_at = perf_counter()
        context = await self._preprocessor.process(self._to_preprocess_input(request))
        try:
            rule_policy_resolution = await self._policy_resolver.resolve(PolicyType.MODERATION_RULE, context)
            decision_policy_resolution = await self._policy_resolver.resolve(PolicyType.DECISION, context)
        except Exception as exc:
            logger.error("Policy resolution failed correlation_id=%s message_id=%s", correlation_id, request.message_id)
            raise ApiResourceUnavailableError("Policy is unavailable") from exc

        signals = []
        for match in context.metadata.get("preprocessing_rule_matches", []):
            signals.extend(self._signal_adapter.adapt(match))

        rubert_result = None
        warnings: list[str] = []
        if self._rubert_classifier is None:
            warnings.append("rubert_unavailable")
        else:
            try:
                async with self._inference_semaphore:
                    rubert_result = await asyncio.to_thread(self._rubert_classifier.classify, context.normalized_text)
                signals.extend(self._rubert_classifier.to_signals(rubert_result, rule_policy_resolution.policy))
            except Exception:
                logger.warning("ruBERT inference fallback correlation_id=%s message_id=%s", correlation_id, request.message_id)
                warnings.append("rubert_unavailable")

        rule_evaluation = self._rule_engine.evaluate(
            request.message_id,
            signals,
            rule_policy_resolution.policy,
        )
        decision = self._decision_engine.decide(
            request.message_id,
            rule_evaluation,
            decision_policy_resolution.policy,
        )
        try:
            collection = await self._dataset_collector.collect(
                DatasetCollectionInput(context=context, rule_evaluation=rule_evaluation, decision=decision)
            )
        except Exception as exc:
            logger.error("Dataset persistence failed correlation_id=%s message_id=%s", correlation_id, request.message_id)
            raise ApiResourceUnavailableError("Database is unavailable") from exc

        response = ModerationMessageResponseSchema(
            correlation_id=correlation_id,
            message_id=request.message_id,
            labels=tuple(label.value for label in decision.labels),
            primary_label=decision.primary_label.value,
            rule_matches=tuple(rule_evaluation.matched_rules),
            rubert_labels=tuple(label.value for label in rubert_result.labels) if rubert_result else (),
            rubert_scores={label.value: round(score, 6) for label, score in rubert_result.scores.items()} if rubert_result else {},
            rubert_thresholds={label.value: threshold for label, threshold in rubert_result.thresholds.items()} if rubert_result else {},
            rubert_top_labels=tuple(str(item["label"]) for item in rubert_result.top_labels) if rubert_result else (),
            risk_score=round(decision.risk_score, 4),
            risk_breakdown=tuple(item.label.value for item in rule_evaluation.risk_breakdown),
            decision_action=decision.decision_action.value,
            severity=decision.severity,
            reason=decision.reason[:256],
            policy_id=decision.policy_id,
            policy_version=decision.policy_version,
            execution_status=ActionExecutionStatus.PENDING.value,
            execution_plan=tuple(action.value for action in decision.action_plan.actions),
            dataset_event_id=collection.event_id,
            latency_ms=round((perf_counter() - started_at) * 1_000),
            warnings=tuple(warnings),
        )
        logger.info(
            "Moderation API completed correlation_id=%s message_id=%s action=%s latency_ms=%s",
            correlation_id,
            request.message_id,
            response.decision_action,
            response.latency_ms,
        )
        return response

    async def submit_feedback(
        self,
        request: ModerationFeedbackRequestSchema,
        correlation_id: str,
    ) -> ApiAckSchema:
        event = await self._get_event(request.event_id, request.message_id)
        try:
            await self._event_repository.save_feedback(
                event,
                request.feedback_type,
                request.labels,
                request.primary_label,
                request.severity,
                request.recommended_action,
                request.moderator_id,
                request.annotation_source,
                request.notes,
            )
        except Exception as exc:
            raise ApiResourceUnavailableError("Database is unavailable") from exc
        return ApiAckSchema(correlation_id=correlation_id, event_id=event.event_id, status="accepted")

    async def submit_action_result(
        self,
        request: ActionResultRequestSchema,
        correlation_id: str,
    ) -> ApiAckSchema:
        event = await self._get_event(request.event_id, request.message_id)
        action = request.action
        status = request.status
        if action not in self._allowed_execution_actions(event.decision_action):
            raise ApiConflictError("Action does not match the issued decision")
        error = self._safe_platform_error(request.platform_error_code, request.platform_error_message)
        try:
            await self._event_repository.save_action_result(event, action, status, request.dry_run, error, request.timestamp)
        except Exception as exc:
            raise ApiResourceUnavailableError("Database is unavailable") from exc
        return ApiAckSchema(correlation_id=correlation_id, event_id=event.event_id, status="accepted")

    async def effective_policies(
        self,
        platform: str,
        guild_id: str | None,
        channel_id: str | None,
        correlation_id: str,
    ) -> EffectivePolicyResponseSchema:
        context = {"platform": platform, "guild_id": guild_id, "channel_id": channel_id, "metadata": {}}
        try:
            results = await asyncio.gather(*(self._policy_resolver.resolve(policy_type, context) for policy_type in PolicyType))
        except Exception as exc:
            raise ApiResourceUnavailableError("Policy is unavailable") from exc
        return EffectivePolicyResponseSchema(
            correlation_id=correlation_id,
            policies=tuple(
                {
                    "type": policy_type.value,
                    "id": result.policy_id,
                    "version": result.version,
                    "enabled": True,
                    "source": result.source.value,
                }
                for policy_type, result in zip(PolicyType, results, strict=True)
            ),
        )

    async def initialize_policy_status(self) -> str:
        resolution = await self._policy_resolver.resolve(PolicyType.DECISION, {"metadata": {}})
        return resolution.version

    async def _get_event(self, event_id: int | None, message_id: str | None):
        try:
            event = await self._event_repository.find_event(event_id, message_id)
        except Exception as exc:
            raise ApiResourceUnavailableError("Database is unavailable") from exc
        if event is None:
            raise ApiNotFoundError("Moderation event was not found")
        return event

    def _to_preprocess_input(self, request: ModerationMessageRequestSchema) -> MessagePreprocessInputSchema:
        return MessagePreprocessInputSchema(**request.model_dump())

    def _safe_platform_error(self, code: str | None, message: str | None) -> str | None:
        if code is None:
            return None
        return code if message is None else f"{code}: {message}"

    def _allowed_execution_actions(self, decision_action: ModerationAction) -> tuple[ModerationAction, ...]:
        bundles = {
            ModerationAction.DELETE_WARN: (ModerationAction.WARN,),
            ModerationAction.TIMEOUT: (ModerationAction.DELETE, ModerationAction.TIMEOUT),
            ModerationAction.BAN: (ModerationAction.DELETE, ModerationAction.BAN),
        }
        return bundles.get(decision_action, (decision_action,))
