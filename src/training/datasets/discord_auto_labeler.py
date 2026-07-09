from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Pattern, Protocol

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer


class ToxicityScorer(Protocol):
    def score(self, texts: list[str]) -> list[float]:
        raise NotImplementedError


def _word_pattern(*words: str) -> Pattern[str]:
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(word) for word in words) + r")(?![\w])")


def _regex(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DiscordAutoLabelerConfig:
    recent_messages_for_toxicity: int = 5
    recent_messages_for_flood: int = 10
    toxicity_threshold: float = 0.82
    toxicity_context_threshold: float = 0.92
    toxicity_current_floor_for_context: float = 0.35
    min_model_text_length: int = 3
    semantic_silver_confidence: float = 0.72


class DiscordAutoLabeler:
    _SEMANTIC_PATTERNS: dict[ModerationLabel, tuple[Pattern[str], ...]] = {
        ModerationLabel.TOXIC: (
            _word_pattern(
                "\u0438\u0434\u0438\u043e\u0442",
                "\u0434\u0435\u0431\u0438\u043b",
                "\u0434\u0443\u0440\u0430\u043a",
                "\u043b\u043e\u0445",
                "\u043c\u0440\u0430\u0437\u044c",
                "\u0442\u0432\u0430\u0440\u044c",
                "\u0443\u0440\u043e\u0434",
                "\u0447\u043c\u043e",
                "\u0443\u0431\u043b\u044e\u0434\u043e\u043a",
                "\u0441\u0443\u043a\u0430",
                "\u0431\u043b\u044f\u0442\u044c",
                "\u043d\u0430\u0445\u0443\u0439",
            ),
            _regex(
                r"(?<![\w])(?:\u0442\u0443\u043f(?:\u043e\u0439|\u0430\u044f|\u044b\u0435|\u043e\u0433\u043e|\u044b\u043c)|"
                r"\u0431\u043b\u044f\u0434\w*|\u0445\u0443\u0439\w*|\u043f\u0438\u0437\u0434\w*|\u0435\u0431\u0430\w*|"
                r"\u0433\u043e\u0432\u043d\w*)(?![\w])"
            ),
        ),
        ModerationLabel.ADVERTISEMENT: (
            re.compile(r"\b(?:куп(?:и|ить|лю)|продам|скидк\w*|промокод\w*|прайс\w*|магазин\w*)\b"),
            re.compile(r"\b(?:заказ(?:ать)?|доставка|акци[яи]|реклам\w*)\b"),
        ),
        ModerationLabel.SCAM: (
            re.compile(r"\b(?:бесплатн\w+\s+nitro|free\s+nitro|steam\s+gift|airdrop|crypto|wallet)\b"),
            re.compile(r"\b(?:выиграл\w*|забери\s+приз|получи\s+\d+\s*(?:руб|₽)|удво(?:ю|ение)\s+баланс)\b"),
            re.compile(r"\b(?:казино|ставк\w+|быстр(?:ый|ые)\s+деньг\w+)\b"),
        ),
        ModerationLabel.THREAT: (
            re.compile(r"\b(?:убью|зарежу|покалечу|сломаю\s+(?:лицо|ноги|руки)|найду\s+(?:тебя|адрес))\b"),
            re.compile(r"\b(?:докс(?:ну|ить)?|деанон(?:ю|ить)?|солью\s+(?:адрес|данные))\b"),
        ),
        ModerationLabel.HATE: (
            re.compile(r"\b(?:ненавижу|уничтожить|изгнать)\s+(?:всех\s+)?(?:русских|украинцев|евреев|мусульман|мигрантов|женщин|мужчин)\b"),
        ),
        ModerationLabel.NSFW: (
            re.compile(r"\b(?:18\+|nsfw|порно|эротик\w*|интим|секс(?:\b|уальн\w*))\b"),
        ),
    }

    def __init__(
        self,
        *,
        toxicity_scorer: ToxicityScorer | None = None,
        config: DiscordAutoLabelerConfig | None = None,
    ) -> None:
        self._toxicity_scorer = toxicity_scorer
        self._config = config or DiscordAutoLabelerConfig()
        self._preprocessor = TextPreprocessor()
        self._signal_adapter = PreprocessingSignalAdapter()
        self._rule_engine = ModerationRuleEngine()
        self._decision_engine = DecisionEngine()
        self._sanitizer = TrainingTextSanitizer()

    async def label_raw_rows(self, raw_rows: list[dict]) -> list[dict]:
        sorted_rows = sorted(raw_rows, key=lambda row: self._parse_datetime(row.get("created_at")))
        context_texts = self._build_toxicity_contexts(sorted_rows)
        current_texts = [self._sanitizer.sanitize(str(row.get("content") or "")) for row in sorted_rows]
        if self._toxicity_scorer is not None:
            current_toxicity_scores = self._toxicity_scorer.score(current_texts)
            context_toxicity_scores = self._toxicity_scorer.score(context_texts)
        else:
            current_toxicity_scores = [0.0 for _ in context_texts]
            context_toxicity_scores = [0.0 for _ in context_texts]

        recent_by_user: dict[str, list[dict]] = defaultdict(list)
        labeled_rows: list[dict] = []

        for row, toxicity_context, current_toxicity_score, context_toxicity_score in zip(
            sorted_rows,
            context_texts,
            current_toxicity_scores,
            context_toxicity_scores,
        ):
            content = str(row.get("content") or "")
            model_text = self._sanitizer.sanitize(content)
            if len(model_text) < self._config.min_model_text_length:
                continue

            user_id = str(row.get("user_id_hash") or "unknown")
            recent = recent_by_user[user_id][-self._config.recent_messages_for_flood :]
            payload = MessagePreprocessInputSchema(
                platform="discord",
                guild_id=str(row.get("guild_id_hash") or "unknown"),
                channel_id=str(row.get("channel_id_hash") or "unknown"),
                user_id=user_id,
                message_id=str(row.get("message_id") or ""),
                raw_text=content,
                created_at=self._parse_datetime(row.get("created_at")),
                recent_messages=tuple(str(item.get("content") or "") for item in recent),
                recent_message_timestamps=tuple(self._parse_datetime(item.get("created_at")) for item in recent),
                has_attachments=int(row.get("attachments_count") or 0) > 0,
                attachment_count=int(row.get("attachments_count") or 0),
                metadata={
                    "source": "discord_auto_label",
                    "source_tag": row.get("source_tag"),
                },
            )
            context = await self._preprocessor.process(payload)
            signals: list[ModerationSignal] = []
            for match_data in context.metadata.get("preprocessing_rule_matches", []):
                signals.extend(self._signal_adapter.adapt(match_data))
            signals.extend(self._build_semantic_silver_signals(content, model_text))

            toxicity_score, toxicity_gate = self._resolve_toxicity_gate(
                current_toxicity_score,
                context_toxicity_score,
            )
            if toxicity_gate:
                signals.append(
                    ModerationSignal(
                        source=SignalSource.RUBERT,
                        label=ModerationLabel.TOXIC,
                        confidence=min(max(toxicity_score, 0.0), 1.0),
                        severity=3,
                        risk_weight=40,
                        reason="rubert_toxicity_context_threshold",
                        model_name="sismetanin/rubert-toxic-pikabu-2ch",
                        model_version="external_toxicity_silver_label",
                        evidence={
                            "toxicity_score": toxicity_score,
                            "current_toxicity_score": current_toxicity_score,
                            "context_toxicity_score": context_toxicity_score,
                            "context_messages": self._config.recent_messages_for_toxicity,
                        },
                    )
                )

            rule_result = self._rule_engine.evaluate(context.message_id, signals)
            decision = self._decision_engine.decide(context.message_id, rule_result)
            primary_label = resolve_primary_label(rule_result.labels)
            labels = [label.value for label in rule_result.labels]

            labeled_rows.append(
                {
                    "message_id": context.message_id,
                    "model_text": model_text,
                    "labels": labels,
                    "primary_label": primary_label.value,
                    "severity": rule_result.severity,
                    "source": "real_safe" if primary_label == ModerationLabel.SAFE else "real_moderated",
                    "feedback_type": "silver_auto_labeled",
                    "annotation_source": "discord_auto_label_rules_toxicity",
                    "created_at": row.get("created_at"),
                    "risk_score": rule_result.risk_score,
                    "decision_action": decision.decision_action.value,
                    "metadata": {
                        "source_bucket": "project",
                        "source_tag": row.get("source_tag"),
                        "guild_id_hash": row.get("guild_id_hash"),
                        "channel_id_hash": row.get("channel_id_hash"),
                        "user_id_hash": user_id,
                        "attachments_count": row.get("attachments_count"),
                        "embeds_count": row.get("embeds_count"),
                        "matched_rules": rule_result.matched_rules,
                        "toxicity_score": toxicity_score,
                        "current_toxicity_score": current_toxicity_score,
                        "context_toxicity_score": context_toxicity_score,
                        "toxicity_gate": toxicity_gate,
                        "toxicity_context_text": toxicity_context,
                        "toxicity_context_messages": self._config.recent_messages_for_toxicity,
                    },
                }
            )
            recent_by_user[user_id].append(row)

        return sorted(labeled_rows, key=lambda row: row["created_at"] or "")

    def _resolve_toxicity_gate(self, current_score: float, context_score: float) -> tuple[float, bool]:
        if current_score >= self._config.toxicity_threshold:
            return current_score, True

        if (
            context_score >= self._config.toxicity_context_threshold
            and current_score >= self._config.toxicity_current_floor_for_context
        ):
            return context_score, True

        return max(current_score, context_score), False

    def _build_toxicity_contexts(self, rows: list[dict]) -> list[str]:
        recent_by_user: dict[str, list[str]] = defaultdict(list)
        contexts: list[str] = []
        for row in rows:
            user_id = str(row.get("user_id_hash") or "unknown")
            content = str(row.get("content") or "")
            recent = recent_by_user[user_id][-self._config.recent_messages_for_toxicity :]
            context_text = "\n".join([*recent, content])
            contexts.append(self._sanitizer.sanitize(context_text))
            recent_by_user[user_id].append(content)
        return contexts

    def _build_semantic_silver_signals(self, content: str, model_text: str) -> list[ModerationSignal]:
        haystack = f"{content.casefold()}\n{model_text}"
        signals: list[ModerationSignal] = []

        for label, patterns in self._SEMANTIC_PATTERNS.items():
            matched_pattern = next((pattern.pattern for pattern in patterns if pattern.search(haystack)), None)
            if not matched_pattern:
                continue

            severity = 4 if label in {ModerationLabel.SCAM, ModerationLabel.THREAT, ModerationLabel.NSFW} else 3
            risk_weight = {
                ModerationLabel.ADVERTISEMENT: 25,
                ModerationLabel.SCAM: 55,
                ModerationLabel.TOXIC: 40,
                ModerationLabel.THREAT: 70,
                ModerationLabel.HATE: 55,
                ModerationLabel.NSFW: 50,
            }.get(label, 35)
            signals.append(
                ModerationSignal(
                    source=SignalSource.MANUAL,
                    label=label,
                    confidence=self._config.semantic_silver_confidence,
                    severity=severity,
                    risk_weight=risk_weight,
                    reason="discord_dataset_semantic_silver_pattern",
                    rule_id=f"dataset_silver_{label.value.lower()}",
                    evidence={"pattern": matched_pattern},
                )
            )

        return signals

    def _parse_datetime(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        return datetime.now(timezone.utc)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
