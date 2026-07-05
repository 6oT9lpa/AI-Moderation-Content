from __future__ import annotations

from datetime import datetime

import disnake

from feature_extractor import FeatureExtractor
from message_context import MessageContext
from normalizer import TextNormalizer


class MessagePreprocessor:

    async def process(
        self,
        message: disnake.Message,
    ) -> MessageContext:

        raw_text = message.content or ""

        normalized = TextNormalizer.normalize(raw_text)

        features = FeatureExtractor.extract(
            raw_text,
            mentions_count=len(message.mentions),
            role_mentions_count=len(message.role_mentions),
        )

        return MessageContext(
            guild_id=message.guild.id if message.guild else 0,
            channel_id=message.channel.id,
            author_id=message.author.id,
            message_id=message.id,

            created_at=message.created_at,

            raw_text=raw_text,
            normalized_text=normalized,

            urls=(),
            domains=(),

            has_url=False,
            has_invite=False,

            message_length=features.message_length,
            words_count=features.words_count,

            emoji_count=features.emoji_count,

            mentions_count=features.mentions_count,
            role_mentions_count=features.role_mentions_count,

            caps_ratio=features.caps_ratio,
            digits_ratio=features.digits_ratio,

            repeated_chars=features.repeated_chars,

            has_zero_width=TextNormalizer.contains_zero_width(raw_text),
            has_homoglyphs=False,

            account_age_days=(
                datetime.utcnow() - message.author.created_at.replace(tzinfo=None)
            ).days,

            recent_messages=(),

            metadata={
                "spaces_count": features.spaces_count,
                "average_word_length": features.average_word_length,
                "longest_word": features.longest_word,
                "punctuation_count": features.punctuation_count,
                "punctuation_ratio": features.punctuation_ratio,
                "newline_count": features.newline_count,
                "unique_chars": features.unique_chars,
                "has_cyrillic": features.has_cyrillic,
                "has_latin": features.has_latin,
                "mixed_alphabet": features.mixed_alphabet,
            },
        )