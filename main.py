from __future__ import annotations

import asyncio
import logging
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.dto.action.action_execution_request import ActionExecutionRequest
from src.domain.dto.dataset.dataset_collection_input import DatasetCollectionInput
from src.domain.moderation.moderation_action import ModerationAction
from src.infrastructure.repository.in_memory_dataset_collector_repository import (
    InMemoryDatasetCollectorRepository,
)
from src.modules.action.action_executor import ActionExecutor
from src.modules.action.action_policy_config_loader import ActionPolicyConfigLoader
from src.modules.action.stub_platform_action_client import StubPlatformActionClient
from src.modules.dataset.dataset_collector import DatasetCollector
from src.modules.dataset.dataset_export_builder import DatasetExportBuilder
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.moderation_rule_policy_config_loader import (
    ModerationRulePolicyConfigLoader,
)
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from src.training.rubert.rubert_moderation_classifier import (
    RuBertClassificationResult,
    RuBertModerationClassifier,
)
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer

CHANNEL_PATTERN = re.compile(r"(?<!\S)@([A-Za-z\u0400-\u04FF0-9_.-]+)")
USER_PATTERN = re.compile(r"(?<!\S)#([A-Za-z\u0400-\u04FF0-9_.-]+)")
MSK = timezone(timedelta(hours=3), name="MSK")
MAX_DEMO_MESSAGES_PER_CHANNEL = 10_000


async def main() -> None:
    _configure_console_encoding()
    _reduce_demo_log_noise()

    preprocessor = TextPreprocessor()
    rule_policy = ModerationRulePolicyConfigLoader.load()
    rule_engine = ModerationRuleEngine(rule_policy)
    decision_engine = DecisionEngine()
    signal_adapter = PreprocessingSignalAdapter()
    action_policy = ActionPolicyConfigLoader.load()
    action_executor = ActionExecutor(action_policy, StubPlatformActionClient())
    dataset_repository = InMemoryDatasetCollectorRepository()
    dataset_collector = DatasetCollector(dataset_repository)
    dataset_export_builder = DatasetExportBuilder()
    rubert_classifier = _load_rubert_classifier()
    report_sanitizer = TrainingTextSanitizer()

    current_channel = "general"
    message_counter = 0
    channel_users: dict[str, set[str]] = defaultdict(set)
    channel_messages: dict[str, deque[dict[str, Any]]] = defaultdict(
        lambda: deque(maxlen=MAX_DEMO_MESSAGES_PER_CHANNEL)
    )
    recent_by_user: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=10))

    print("AI Moderator chat demo")
    print("Format: @channel #user message. Use @channel anywhere to switch channel. Type exit to finish.")
    print("Current channel: @general")
    if rubert_classifier is not None:
        print(f"ruBERT: enabled ({rubert_classifier.device}, {rubert_classifier.model_dir})")
    else:
        print("ruBERT: disabled (model/dependencies not available)")

    try:
        while True:
            raw_line = input("> ").strip()

            if raw_line.lower() == "exit":
                break

            parsed = _parse_chat_line(raw_line, current_channel)
            current_channel = parsed["channel"]

            if parsed["channel_changed"]:
                print(f"Current channel: @{current_channel}")

            if parsed["user_id"] is None:
                print("Message ignored: add user marker like #1 or #alice.")
                continue

            if not parsed["text"]:
                print("Message ignored: text is empty after channel/user markers.")
                continue

            message_counter += 1
            created_at = datetime.now(MSK)
            channel_id = current_channel
            user_id = parsed["user_id"]
            recent_key = (channel_id, user_id)
            recent_items = tuple(recent_by_user[recent_key])

            payload = MessagePreprocessInputSchema(
                platform="chat-demo",
                guild_id="local-chat",
                channel_id=channel_id,
                user_id=user_id,
                message_id=f"demo_{message_counter}",
                raw_text=parsed["text"],
                created_at=created_at,
                recent_messages=tuple(item["text"] for item in recent_items),
                recent_message_timestamps=tuple(item["created_at"] for item in recent_items),
            )

            context = await preprocessor.process(payload)
            preprocessing_matches = context.metadata.get("preprocessing_rule_matches", [])
            preprocessing_signals = []

            for match_data in preprocessing_matches:
                preprocessing_signals.extend(signal_adapter.adapt(match_data))

            baseline_rule_result = rule_engine.evaluate(context.message_id, preprocessing_signals)
            signals = list(preprocessing_signals)

            rubert_result = None
            if rubert_classifier is not None:
                rubert_result = rubert_classifier.classify(parsed["text"])
                signals.extend(rubert_classifier.to_signals(rubert_result, rule_policy))

            rule_result = rule_engine.evaluate(context.message_id, signals)
            decision = decision_engine.decide(context.message_id, rule_result)
            execution_result = await action_executor.execute(
                ActionExecutionRequest(
                    moderation_decision=decision,
                    platform=context.platform,
                    guild_id=context.guild_id,
                    channel_id=context.channel_id,
                    message_id=context.message_id,
                    user_id=context.user_id,
                    reason=decision.reason,
                )
            )
            dataset_event_id = None

            try:
                dataset_result = await dataset_collector.collect(
                    DatasetCollectionInput(
                        context=context,
                        rule_evaluation=rule_result,
                        decision=decision,
                        action_result=execution_result,
                    )
                )
                dataset_event_id = dataset_result.event_id
            except Exception:
                logging.getLogger(__name__).warning(
                    "Dataset collection failed message_id=%s",
                    context.message_id,
                    exc_info=True,
                )

            message_record = {
                "message_id": context.message_id,
                "dataset_event_id": dataset_event_id,
                "created_at": created_at,
                "user_id": user_id,
                "channel_id": channel_id,
                "text": rubert_result.model_text if rubert_result is not None else report_sanitizer.sanitize(parsed["text"]),
                "labels": [label.value for label in decision.labels],
                "primary_label": decision.primary_label.value,
                "decision_action": decision.decision_action.value,
                "reason": decision.reason,
                "risk_score": decision.risk_score,
                "action_status": execution_result.status.value,
                "rubert": _format_rubert_result(rubert_result),
                "baseline": _format_rule_result(baseline_rule_result),
                "matches": [
                    {
                        "label": item.label.value,
                        "reason": item.reason,
                        "contribution": item.contribution,
                        "evidence": item.evidence,
                    }
                    for item in rule_result.risk_breakdown
                ],
                "steps": [
                    {
                        "action": step.action.value,
                        "status": step.status.value,
                        "reason": step.reason,
                        "error": step.error,
                    }
                    for step in execution_result.steps
                ],
            }
            channel_users[channel_id].add(user_id)
            channel_messages[channel_id].append(message_record)
            recent_by_user[recent_key].append({"text": report_sanitizer.sanitize(parsed["text"]), "created_at": created_at})

            print(
                f"@{channel_id} #{user_id}: "
                f"labels={_format_list(label.value for label in decision.labels)} "
                f"primary={decision.primary_label.value} action={decision.decision_action.value} "
                f"risk={decision.risk_score:.2f} action_status={execution_result.status.value} "
                f"baseline={baseline_rule_result.primary_label.value}:{baseline_rule_result.risk_score:.2f} "
                f"rubert={_format_rubert_inline(rubert_result)}"
            )
    except (KeyboardInterrupt, EOFError):
        print("")
        print("Chat input stopped.")

    _print_report(
        channel_users,
        channel_messages,
        dataset_records_count=len(dataset_repository.records),
        export_ready_count=len(dataset_export_builder.build_training_examples(dataset_repository.records)),
    )


def _parse_chat_line(raw_line: str, current_channel: str) -> dict[str, Any]:
    channel_matches = CHANNEL_PATTERN.findall(raw_line)
    user_match = USER_PATTERN.search(raw_line)
    channel = channel_matches[-1] if channel_matches else current_channel
    text = CHANNEL_PATTERN.sub("", raw_line)
    text = USER_PATTERN.sub("", text, count=1)
    text = " ".join(text.split())

    return {
        "channel": channel,
        "channel_changed": bool(channel_matches) and channel != current_channel,
        "user_id": user_match.group(1) if user_match else None,
        "text": text,
    }


def _reduce_demo_log_noise() -> None:
    for logger_name in ("", "src", "application", "infrastructure", "modules", "shared"):
        demo_logger = logging.getLogger(logger_name)
        demo_logger.setLevel(logging.WARNING)

        for handler in demo_logger.handlers:
            handler.setLevel(logging.WARNING)


def _configure_console_encoding() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _load_rubert_classifier() -> RuBertModerationClassifier | None:
    try:
        return RuBertModerationClassifier()
    except Exception as exc:
        logging.getLogger(__name__).warning("ruBERT classifier disabled: %s", exc)
        return None


def _print_report(
    channel_users: dict[str, set[str]],
    channel_messages: dict[str, deque[dict[str, Any]]],
    *,
    dataset_records_count: int = 0,
    export_ready_count: int = 0,
) -> None:
    print("")
    print("Moderation report")
    print("=================")

    if not channel_messages:
        print("No messages were processed.")
        return

    print(f"Dataset records: {dataset_records_count}")
    print(f"ruBERT export-ready records: {export_ready_count}")

    for channel_id in sorted(channel_messages):
        print("")
        print(f"Channel @{channel_id}")
        print(f"Users: {', '.join(f'#{user_id}' for user_id in sorted(channel_users[channel_id]))}")
        print("Punishments:")
        _print_channel_punishments(channel_messages[channel_id])
        print("Messages:")

        for message in channel_messages[channel_id]:
            timestamp = message["created_at"].strftime("%Y-%m-%d %H:%M:%S %Z")
            print(
                f"- {timestamp} #{message['user_id']}: {message['text']} "
                f"[labels={_format_list(message['labels'])} primary={message['primary_label']} "
                f"action={message['decision_action']} risk={message['risk_score']:.2f} "
                f"baseline={message['baseline']['primary_label']}:{message['baseline']['risk_score']:.2f} "
                f"rubert={message['rubert']['primary_label']} "
                f"dataset_event_id={message['dataset_event_id']}]"
            )
            _print_message_matches(message)
            _print_rubert_details(message["rubert"])


def _print_channel_punishments(messages: deque[dict[str, Any]]) -> None:
    punishment_found = False
    punishment_actions = {
        ModerationAction.REVIEW.value,
        ModerationAction.WARN.value,
        ModerationAction.DELETE.value,
        ModerationAction.TIMEOUT.value,
        ModerationAction.BAN.value,
    }

    for message in messages:
        punitive_steps = [
            step
            for step in message["steps"]
            if step["action"] in punishment_actions
        ]

        if message["decision_action"] not in punishment_actions and not punitive_steps:
            continue

        punishment_found = True
        actions = ", ".join(f"{step['action']}:{step['status']}" for step in punitive_steps)
        if not actions:
            actions = message["decision_action"]

        print(
            f"- {_format_list(message['labels'])} #{message['user_id']} "
            f"({message['reason']}; action={actions}; status={message['action_status']})"
        )

    if not punishment_found:
        print("- none")


def _print_message_matches(message: dict[str, Any]) -> None:
    if not message["matches"]:
        return

    details = "; ".join(
        f"{match['label']}:{match['reason']}+{match['contribution']:.2f}"
        for match in message["matches"]
    )
    print(f"  matches: {details}")


def _print_rubert_details(rubert: dict[str, Any]) -> None:
    if not rubert["enabled"]:
        return

    top_labels = ", ".join(
        f"{item['label']}:{item['score']:.3f}"
        for item in rubert["top_labels"]
    )
    print(
        f"  rubert: labels={_format_list(rubert['labels'])} "
        f"primary={rubert['primary_label']} model_text={rubert['model_text']!r} "
        f"top={top_labels}"
    )


def _format_rubert_inline(result: RuBertClassificationResult | None) -> str:
    if result is None:
        return "disabled"

    return f"{result.primary_label.value}:{_format_list(label.value for label in result.labels)}"


def _format_rubert_result(result: RuBertClassificationResult | None) -> dict[str, Any]:
    if result is None:
        return {
            "enabled": False,
            "labels": [],
            "primary_label": "DISABLED",
            "model_text": "",
            "top_labels": [],
        }

    return {
        "enabled": True,
        "labels": [label.value for label in result.labels],
        "primary_label": result.primary_label.value,
        "model_text": result.model_text,
        "top_labels": result.top_labels,
    }


def _format_rule_result(result: Any) -> dict[str, Any]:
    return {
        "labels": [label.value for label in result.labels],
        "primary_label": result.primary_label.value,
        "risk_score": result.risk_score,
        "confidence": result.confidence,
        "severity": result.severity,
    }


def _format_list(values: Any) -> str:
    items = [str(value) for value in values]
    return "[" + ",".join(items) + "]"


if __name__ == "__main__":
    asyncio.run(main())
