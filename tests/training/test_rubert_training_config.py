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
    assert config.training.train_batch_size == 64
    assert config.training.eval_batch_size == 256
    assert config.training.gradient_accumulation_steps == 1
    assert config.training.preprocessing_num_proc == 8
    assert config.training.gradient_checkpointing is True
    assert config.model.use_fast_tokenizer is False
    assert (
        config.training.train_batch_size
        * config.training.gradient_accumulation_steps
        == 64
    )


def test_tiny2_continued_config_uses_benchmarked_gpu_limits() -> None:
    config = RuBertTrainingConfig.load(
        "configs/training/rubert_tiny2_continued.yaml"
    )

    assert config.model.base_model_name == "cointegrated/rubert-tiny2"
    assert config.model.classifier_output_dir.name.endswith("trained-20260729")
    assert config.training.train_batch_size == 48
    assert config.training.eval_batch_size == 128
    assert config.training.gradient_accumulation_steps == 1
    assert config.training.learning_rate == 5e-6
    assert config.training.num_train_epochs == 2
    assert config.training.gradient_checkpointing is False
