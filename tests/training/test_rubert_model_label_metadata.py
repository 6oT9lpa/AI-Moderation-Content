import json

import pytest

from src.training.rubert.rubert_moderation_classifier import RuBertModerationClassifier


def test_model_label_metadata_preserves_configured_order(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"num_labels": 3, "id2label": {"0": "SAFE", "1": "SCAM", "2": "NSFW"}}),
        encoding="utf-8",
    )

    assert RuBertModerationClassifier._read_label_order(config_path) == ["SAFE", "SCAM", "NSFW"]


def test_model_label_metadata_rejects_unsupported_label_before_loading_weights(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"num_labels": 2, "id2label": {"0": "SAFE", "1": "UNSUPPORTED_MEDIA_LABEL"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported moderation label"):
        RuBertModerationClassifier._read_label_order(config_path)
