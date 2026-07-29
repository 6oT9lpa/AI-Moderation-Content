from datetime import datetime, timezone

import pytest

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.text_preprocessor import TextPreprocessor


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ("\u0442\u044b \u0445\u0443\u0435\u0433\u043b\u043e\u0442\u0438\u043a", "\u043a\u0430\u043a\u043e\u0439 \u0436\u0435 \u0442\u044b \u0431\u0435\u0437\u0434\u0430\u0440\u044c"))
async def test_preprocessor_does_not_emit_profanity_for_obscene_words(text: str) -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="user", message_id="message", raw_text=text,
            created_at=datetime.now(timezone.utc),
        ),
    )

    assert ModerationLabel.PROFANITY.value not in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_preprocessor_does_not_label_political_entities() -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="user", message_id="message",
            raw_text="\u0417\u0435\u043b\u0435\u043d\u0441\u043a\u0438\u0439 \u0438 \u0412\u0435\u0440\u0445\u043e\u0432\u043d\u0430\u044f \u0440\u0430\u0434\u0430 \u043e\u043f\u044f\u0442\u044c \u0441\u043f\u043e\u0440\u044f\u0442",
            created_at=datetime.now(timezone.utc),
        ),
    )

    assert ModerationLabel.POLITICS_IRL.value not in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_preprocessor_does_not_treat_spaced_word_as_evasion_or_profanity() -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="user", message_id="message", raw_text="\u043b \u043e \u0445",
            created_at=datetime.now(timezone.utc),
        ),
    )

    labels = set(context.metadata["preprocessing_labels"])
    assert ModerationLabel.PROFANITY.value not in labels
    assert ModerationLabel.EVASION.value not in labels
