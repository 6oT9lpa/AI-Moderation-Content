from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.contracts.rules.moderation_rule_policy import ModerationRulePolicy
from src.domain.moderation.moderation_label import ModerationLabel
from src.domain.rules.moderation_signal import ModerationSignal
from src.domain.rules.signal_source import SignalSource
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer
from src.training.rubert.rubert_training_config import RuBertTrainingConfig


@dataclass(frozen=True)
class RuBertClassificationResult:
    model_text: str
    labels: list[ModerationLabel]
    primary_label: ModerationLabel
    scores: dict[ModerationLabel, float]
    thresholds: dict[ModerationLabel, float]
    top_labels: list[dict[str, Any]]


class RuBertModerationClassifier:
    def __init__(
        self,
        *,
        model_dir: Path = Path("models/rubert-tiny2-moderation-trained"),
        thresholds_file: Path | None = None,
        config: RuBertTrainingConfig | None = None,
        sanitizer: TrainingTextSanitizer | None = None,
    ) -> None:
        self._model_dir = model_dir
        self._thresholds_file = thresholds_file or model_dir / "thresholds.json"
        self._config = config or RuBertTrainingConfig.load()
        self._sanitizer = sanitizer or TrainingTextSanitizer()

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install training dependencies first: pip install -r requirements-training.txt") from exc

        if not self._model_dir.exists():
            raise FileNotFoundError(f"ruBERT model directory not found: {self._model_dir}")

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self._model_dir, local_files_only=True)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self._model_dir,
            local_files_only=True,
            use_safetensors=True,
        )
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(self._device)
        self._model.eval()

        self._label_order = [
            self._model.config.id2label[index]
            for index in range(self._model.config.num_labels)
        ]
        self._thresholds = self._load_thresholds()

    @property
    def device(self) -> str:
        return self._device

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def classify(self, text: str) -> RuBertClassificationResult:
        model_text = self._sanitizer.sanitize(text)
        batch = self._tokenizer(
            [model_text],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self._config.model.max_length,
        ).to(self._device)

        with self._torch.inference_mode():
            logits = self._model(**batch).logits
            probabilities = self._torch.sigmoid(logits).detach().cpu().tolist()[0]

        scores = {
            ModerationLabel(label): float(probability)
            for label, probability in zip(self._label_order, probabilities)
        }
        selected = [
            label
            for label, score in scores.items()
            if score >= self._thresholds.get(label, self._config.training.threshold)
        ]
        if any(label != ModerationLabel.SAFE for label in selected):
            selected = [label for label in selected if label != ModerationLabel.SAFE]

        primary_label = resolve_primary_label(selected, fallback=ModerationLabel.SAFE)
        top_labels = [
            {"label": label.value, "score": round(score, 6)}
            for label, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        return RuBertClassificationResult(
            model_text=model_text,
            labels=selected,
            primary_label=primary_label,
            scores=scores,
            thresholds=self._thresholds,
            top_labels=top_labels,
        )

    def to_signals(
        self,
        result: RuBertClassificationResult,
        policy: ModerationRulePolicy,
    ) -> list[ModerationSignal]:
        signals: list[ModerationSignal] = []
        for label in result.labels:
            score = result.scores[label]
            signals.append(
                ModerationSignal(
                    source=SignalSource.RUBERT,
                    label=label,
                    confidence=score,
                    severity=self._severity(label),
                    risk_weight=int(getattr(policy.label_weights, label.value, 0)),
                    evidence={
                        "threshold": result.thresholds.get(label),
                        "top_labels": result.top_labels,
                        "input_redacted": True,
                    },
                    reason="rubert_tiny2_moderation_classifier",
                    rule_id=f"rubert.{label.value.lower()}",
                    model_name="cointegrated/rubert-tiny2",
                    model_version=str(self._model_dir),
                )
            )
        return signals

    def _load_thresholds(self) -> dict[ModerationLabel, float]:
        if self._thresholds_file.exists():
            data = json.loads(self._thresholds_file.read_text(encoding="utf-8"))
            thresholds: dict[ModerationLabel, float] = {}
            for label in self._label_order:
                value = float(data.get(label, self._config.training.threshold))
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    raise ValueError(f"Invalid ruBERT threshold label={label!r}")
                thresholds[ModerationLabel(label)] = value
            return thresholds

        return {
            ModerationLabel(label): self._config.training.threshold
            for label in self._label_order
        }

    def _severity(self, label: ModerationLabel) -> int:
        return {
            ModerationLabel.SAFE: 0,
            ModerationLabel.URL: 1,
            ModerationLabel.SPAM: 2,
            ModerationLabel.ADVERTISEMENT: 2,
            ModerationLabel.EVASION: 2,
            ModerationLabel.PROFANITY: 1,
            ModerationLabel.POLITICS_IRL: 2,
            ModerationLabel.INVITE: 3,
            ModerationLabel.TOXIC: 3,
            ModerationLabel.SCAM: 4,
            ModerationLabel.NSFW: 4,
            ModerationLabel.IMAGE_SCAM: 4,
            ModerationLabel.HATE: 5,
            ModerationLabel.THREAT: 5,
            ModerationLabel.FLOOD: 2,
        }[label]
