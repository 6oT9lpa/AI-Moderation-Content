from src.training.rubert.rubert_training_config import RuBertTrainingConfig


def test_distil_conversational_config_uses_memory_safe_effective_batch() -> None:
    config = RuBertTrainingConfig.load(
        "configs/training/rubert_distil_conversational.yaml"
    )

    assert (
        config.model.base_model_name
        == "DeepPavlov/distilrubert-base-cased-conversational"
    )
    assert config.model.base_model_revision == (
        "9b4f8c20bdc51934ef2ef586ef9afee85549cccb"
    )
    assert config.training.train_batch_size == 4
    assert config.training.gradient_accumulation_steps == 16
    assert config.training.gradient_checkpointing is True
    assert config.model.use_fast_tokenizer is False
    assert (
        config.training.train_batch_size
        * config.training.gradient_accumulation_steps
        == 64
    )
