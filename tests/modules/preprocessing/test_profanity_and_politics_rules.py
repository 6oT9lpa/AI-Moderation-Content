from datetime import datetime, timezone

import pytest

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.text_preprocessor import TextPreprocessor


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ("ты хуеглотик", "какой же ты бездарт"))
async def test_profanity_rule_covers_compounds_and_single_character_typos(text: str) -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="user", message_id="message", raw_text=text,
            created_at=datetime.now(timezone.utc),
        ),
    )

    assert ModerationLabel.PROFANITY.value in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_politics_rule_marks_real_world_political_entities() -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="user", message_id="message", raw_text="Зеленский и Верховная рада опять спорят",
            created_at=datetime.now(timezone.utc),
        ),
    )

    assert ModerationLabel.POLITICS_IRL.value in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_preprocessor_emits_separate_literary_profanity_rule() -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="user", message_id="message", raw_text="Этот дурак ошибся",
            created_at=datetime.now(timezone.utc),
        ),
    )

    assert "preprocessing.russian_profanity.literary" in {
        match["rule_id"] for match in context.metadata["preprocessing_rule_matches"]
    }
