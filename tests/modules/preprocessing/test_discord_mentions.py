from datetime import datetime, timezone

import pytest

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.moderation.moderation_label import ModerationLabel
from src.modules.preprocessing.detectors.mention_extractor import MentionExtractor
from src.modules.preprocessing.text_preprocessor import TextPreprocessor


def test_plain_at_word_is_not_a_discord_user_mention() -> None:
    assert MentionExtractor.count_user_mentions("напиши @support, это не тег Discord") == 0


@pytest.mark.asyncio
async def test_one_discord_tag_is_not_spam_but_insult_after_it_is_detected() -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="author", message_id="message",
            raw_text="<@123456789012345678> ты пидр",
            created_at=datetime.now(timezone.utc),
        )
    )

    assert context.features is not None
    assert context.features.mention_count == 1
    assert ModerationLabel.SPAM.value not in context.metadata["preprocessing_labels"]
    assert ModerationLabel.PROFANITY.value in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_three_mentions_raise_priority_only_with_toxicity() -> None:
    mentions = "<@123456789012345678> <@223456789012345678> <@323456789012345678>"
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="author", message_id="message",
            raw_text=f"{mentions} вы пидоры",
            created_at=datetime.now(timezone.utc),
        )
    )

    matches = context.metadata["preprocessing_rule_matches"]
    assert any(match["rule_id"] == "preprocessing.targeted.mass_mentions" for match in matches)
    assert ModerationLabel.SPAM.value not in context.metadata["preprocessing_labels"]


@pytest.mark.asyncio
async def test_three_mentions_without_toxicity_are_not_spam() -> None:
    context = await TextPreprocessor().process(
        MessagePreprocessInputSchema(
            channel_id="channel", user_id="author", message_id="message",
            raw_text="<@123456789012345678> <@223456789012345678> <@323456789012345678> встреча в восемь",
            created_at=datetime.now(timezone.utc),
        )
    )

    assert context.metadata["preprocessing_labels"] == []
