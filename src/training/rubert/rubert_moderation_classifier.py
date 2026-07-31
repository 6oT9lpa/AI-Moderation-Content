from __future__ import annotations

import json
import math
import os
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
    context_adjustments: tuple[str, ...] = ()


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

        expected_label_order = self._read_label_order(self._model_dir / "config.json")

        if torch_threads := os.environ.get("RUBERT_TORCH_NUM_THREADS"):
            torch.set_num_threads(max(1, int(torch_threads)))
        if interop_threads := os.environ.get("RUBERT_TORCH_NUM_INTEROP_THREADS"):
            torch.set_num_interop_threads(max(1, int(interop_threads)))

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
        if self._label_order != expected_label_order:
            raise ValueError("ruBERT runtime label order differs from model metadata")
        self._thresholds = self._load_thresholds()

    @staticmethod
    def _read_label_order(config_path: Path) -> list[str]:
        """Reject stale or malformed label metadata before model weights load."""
        if not config_path.is_file():
            raise FileNotFoundError(f"ruBERT model config not found: {config_path}")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        id2label = data.get("id2label")
        configured_num_labels = data.get("num_labels")
        if not isinstance(id2label, dict) or not id2label:
            raise ValueError("ruBERT model config has invalid label metadata")
        num_labels = len(id2label)
        if configured_num_labels is not None and configured_num_labels != num_labels:
            raise ValueError("ruBERT model config has inconsistent label metadata")
        try:
            labels = [id2label[str(index)] for index in range(num_labels)]
        except KeyError as exc:
            raise ValueError("ruBERT model config has incomplete label metadata") from exc
        if any(not isinstance(label, str) for label in labels) or len(set(labels)) != len(labels):
            raise ValueError("ruBERT model labels must be unique strings")
        try:
            for label in labels:
                ModerationLabel(label)
        except ValueError as exc:
            raise ValueError("ruBERT model config contains an unsupported moderation label") from exc
        return labels

    @property
    def device(self) -> str:
        return self._device

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def classify(self, text: str) -> RuBertClassificationResult:
        return self.classify_batch([text])[0]

    def classify_batch(self, texts: list[str] | tuple[str, ...]) -> list[RuBertClassificationResult]:
        if not texts:
            return []
        model_texts = [self._sanitizer.sanitize(text) for text in texts]
        batch = self._tokenizer(
            model_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self._config.model.max_length,
        ).to(self._device)

        with self._torch.inference_mode():
            logits = self._model(**batch).logits
            probabilities_batch = self._torch.sigmoid(logits).detach().cpu().tolist()

        return [
            self._build_result(model_text, probabilities)
            for model_text, probabilities in zip(model_texts, probabilities_batch, strict=True)
        ]

    def _build_result(self, model_text: str, probabilities: list[float]) -> RuBertClassificationResult:
        scores = {ModerationLabel(label): float(probability) for label, probability in zip(self._label_order, probabilities)}
        selected = [
            label
            for label, score in scores.items()
            if score >= self._thresholds.get(label, self._config.training.threshold)
        ]
        if any(label != ModerationLabel.SAFE for label in selected):
            selected = [label for label in selected if label != ModerationLabel.SAFE]
        if not selected:
            selected = [ModerationLabel.SAFE]

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
            context_adjustments=(),
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
                        "context_adjustments": result.context_adjustments,
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
            ModerationLabel.HATE: 5,
            ModerationLabel.THREAT: 5,
            ModerationLabel.FLOOD: 2,
        }[label]
