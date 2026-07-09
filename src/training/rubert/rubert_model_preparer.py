from __future__ import annotations

from pathlib import Path

from src.infrastructure.logging.logger import get_logger
from src.training.rubert.rubert_training_config import RuBertTrainingConfig

logger = get_logger(__name__)


class RuBertModelPreparer:
    SNAPSHOT_ALLOW_PATTERNS = (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
        "pytorch_model.bin",
        "model.safetensors",
        "README.md",
    )

    def __init__(self, config: RuBertTrainingConfig | None = None) -> None:
        self._config = config or RuBertTrainingConfig()

    def download_base_model(self) -> Path:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError(
                "Install training dependencies first: pip install -r requirements-training.txt"
            ) from exc

        target_dir = self._config.model.local_base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_download(
            repo_id=self._config.model.base_model_name,
            local_dir=target_dir,
            allow_patterns=list(self.SNAPSHOT_ALLOW_PATTERNS),
        )
        logger.info(
            "ruBERT base model downloaded repo=%s path=%s",
            self._config.model.base_model_name,
            snapshot_path,
        )
        return Path(snapshot_path)

    def prepare_classifier(self) -> Path:
        try:
            from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Install training dependencies first: pip install -r requirements-training.txt"
            ) from exc

        base_dir = self._config.model.local_base_dir
        output_dir = self._config.model.classifier_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        model_config = AutoConfig.from_pretrained(
            base_dir,
            **self._config.to_transformers_metadata(),
        )
        tokenizer = AutoTokenizer.from_pretrained(base_dir, use_fast=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            base_dir,
            config=model_config,
            ignore_mismatched_sizes=True,
        )
        tokenizer.save_pretrained(output_dir)
        model.save_pretrained(output_dir)
        logger.info(
            "ruBERT classifier initialized base=%s output=%s labels=%s",
            base_dir,
            output_dir,
            self._config.label_schema.num_labels,
        )
        return output_dir
