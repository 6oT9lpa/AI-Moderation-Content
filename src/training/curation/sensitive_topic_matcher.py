from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Pattern

import yaml

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.sensitive_topic_annotation import SensitiveTopicAnnotation


class SensitiveTopicMatcher:
    _GROUP_TOPICS = frozenset({"race", "gender"})

    def __init__(
        self,
        *,
        topic_patterns: Mapping[str, tuple[Pattern[str], ...]],
        harm_patterns: Mapping[str, tuple[Pattern[str], ...]],
        counter_patterns: tuple[Pattern[str], ...],
        group_context_patterns: tuple[Pattern[str], ...],
        proximity_chars: int,
        harm_proximity_chars: Mapping[str, int],
    ) -> None:
        self._topic_patterns = dict(topic_patterns)
        self._harm_patterns = dict(harm_patterns)
        self._counter_patterns = counter_patterns
        self._group_context_patterns = group_context_patterns
        self._proximity_chars = proximity_chars
        self._harm_proximity_chars = dict(harm_proximity_chars)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SensitiveTopicMatcher":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "SensitiveTopicMatcher":
        """Build from validated caller-owned policy data.

        Offline tooling may still load YAML, while runtime-independent tests and
        embedded workflows can supply explicit versioned policy data directly.
        """
        topics = raw.get("topics", {})
        harm = raw.get("harm", {})
        counter = raw.get("counter_context", {})
        group_context = raw.get("group_context", {})

        return cls(
            topic_patterns={
                name: cls._compile_patterns(config.get("patterns", ()))
                for name, config in topics.items()
            },
            harm_patterns={
                name: cls._compile_patterns(config.get("patterns", ()))
                for name, config in harm.items()
            },
            counter_patterns=cls._compile_patterns(counter.get("patterns", ())),
            group_context_patterns=cls._compile_patterns(group_context.get("patterns", ())),
            proximity_chars=int(raw.get("proximity_chars", 160)),
            harm_proximity_chars={
                str(name): int(distance)
                for name, distance in raw.get("harm_proximity_chars", {}).items()
            },
        )

    def detect_topics(self, text: str) -> tuple[str, ...]:
        normalized = self.normalize_text(text)
        return tuple(
            topic
            for topic, patterns in self._topic_patterns.items()
            if self._matches(patterns, normalized)
        )

    def annotate(self, text: str) -> SensitiveTopicAnnotation:
        normalized = self.normalize_text(text)
        topic_spans = {
            topic: self._find_spans(patterns, normalized)
            for topic, patterns in self._topic_patterns.items()
        }
        topic_spans = {topic: spans for topic, spans in topic_spans.items() if spans}

        if not topic_spans:
            return SensitiveTopicAnnotation()

        topics = tuple(topic_spans)
        counter_context = self._matches(self._counter_patterns, normalized)
        harm_spans = {
            name: self._find_spans(patterns, normalized)
            for name, patterns in self._harm_patterns.items()
        }
        group_context_spans = self._find_spans(self._group_context_patterns, normalized)

        if counter_context:
            return SensitiveTopicAnnotation(
                topics=topics,
                reasons=("counter_or_supportive_context",),
                requires_review=any(harm_spans.values()),
            )

        labels: set[ModerationLabel] = set()
        reasons: list[str] = []
        severity = 0

        for topic, targets in topic_spans.items():
            is_group_topic = topic in self._GROUP_TOPICS

            threat = self._has_proximate_match(
                targets,
                harm_spans.get("threat", ()),
                maximum_distance=self._harm_distance("threat"),
            )
            if threat:
                labels.update((ModerationLabel.THREAT, ModerationLabel.TOXIC))
                directly_targeted_group = self._has_proximate_match(
                    targets,
                    harm_spans.get("threat", ()),
                    maximum_distance=8,
                )
                group_context = self._has_proximate_match(
                    targets,
                    group_context_spans,
                    maximum_distance=self._harm_distance("hate_action"),
                )
                if is_group_topic and (directly_targeted_group or group_context):
                    labels.add(ModerationLabel.HATE)
                severity = max(severity, 5)
                reasons.append(f"{topic}:explicit_threat")

            if self._has_proximate_match(
                targets,
                harm_spans.get("sexual", ()),
                maximum_distance=self._harm_distance("sexual"),
            ):
                labels.add(ModerationLabel.NSFW)
                severity = max(severity, 4)
                reasons.append(f"{topic}:sexual_content")

            if self._has_proximate_match(
                targets,
                harm_spans.get("sexual_abuse", ()),
                maximum_distance=self._harm_distance("sexual_abuse"),
            ):
                labels.update((ModerationLabel.NSFW, ModerationLabel.TOXIC))
                severity = max(severity, 5)
                reasons.append(f"{topic}:sexual_abuse")

            degradation = self._has_proximate_match(
                targets,
                harm_spans.get("degradation", ()),
                maximum_distance=self._harm_distance("degradation"),
            )
            hate_action = self._has_proximate_match(
                targets,
                harm_spans.get("hate_action", ()),
                maximum_distance=self._harm_distance("hate_action"),
            )
            if not is_group_topic and hate_action:
                hate_action = self._has_proximate_match(
                    targets,
                    harm_spans.get("hate_action", ()),
                    maximum_distance=8,
                )
            group_context = self._has_proximate_match(
                targets,
                group_context_spans,
                maximum_distance=self._harm_distance("hate_action"),
            )
            if is_group_topic and degradation and not group_context:
                degradation = self._has_proximate_match(
                    targets,
                    harm_spans.get("degradation", ()),
                    maximum_distance=8,
                )
            if degradation or hate_action:
                labels.add(ModerationLabel.TOXIC)
                severity = max(severity, 4 if is_group_topic else 3)
                reasons.append(f"{topic}:targeted_degradation")
                if is_group_topic:
                    labels.add(ModerationLabel.HATE)

            if self._has_proximate_match(
                targets,
                harm_spans.get("profanity", ()),
                maximum_distance=self._harm_distance("profanity"),
            ):
                labels.add(ModerationLabel.PROFANITY)
                severity = max(severity, 1)
                reasons.append(f"{topic}:profanity")

        labels.discard(ModerationLabel.SAFE)
        ordered_labels = tuple(sorted(labels, key=lambda label: label.value))
        return SensitiveTopicAnnotation(
            topics=topics,
            labels=ordered_labels,
            severity=severity,
            reasons=tuple(dict.fromkeys(reasons)),
            requires_review=not ordered_labels and bool(topics),
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).casefold()
        return " ".join(normalized.split())

    @staticmethod
    def _compile_patterns(patterns: Iterable[str]) -> tuple[Pattern[str], ...]:
        return tuple(re.compile(pattern, flags=re.IGNORECASE | re.UNICODE) for pattern in patterns)

    @staticmethod
    def _matches(patterns: Iterable[Pattern[str]], text: str) -> bool:
        return any(pattern.search(text) for pattern in patterns)

    @staticmethod
    def _find_spans(patterns: Iterable[Pattern[str]], text: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            match.span()
            for pattern in patterns
            for match in pattern.finditer(text)
        )

    def _has_proximate_match(
        self,
        target_spans: Iterable[tuple[int, int]],
        harm_spans: Iterable[tuple[int, int]],
        *,
        maximum_distance: int | None = None,
    ) -> bool:
        allowed_distance = self._proximity_chars if maximum_distance is None else maximum_distance
        for target_start, target_end in target_spans:
            for harm_start, harm_end in harm_spans:
                distance = max(target_start - harm_end, harm_start - target_end, 0)
                if distance <= allowed_distance:
                    return True
        return False

    def _harm_distance(self, name: str) -> int:
        return self._harm_proximity_chars.get(name, self._proximity_chars)
