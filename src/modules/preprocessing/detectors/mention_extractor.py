from __future__ import annotations

import re

# Only Discord's canonical mention syntax is a user mention.  Treating every
# ``@word`` as a mention made ordinary text look like mention spam.
_USER_MENTION_RE = re.compile(r"<@!?\d+>")
_ROLE_MENTION_RE = re.compile(r"<@&\d+>")
_CHANNEL_MENTION_RE = re.compile(r"<#\d+>")


class MentionExtractor:
    @staticmethod
    def count_user_mentions(text: str) -> int:
        return len(_USER_MENTION_RE.findall(text or ""))

    @staticmethod
    def count_role_mentions(text: str) -> int:
        return len(_ROLE_MENTION_RE.findall(text or ""))

    @staticmethod
    def count_channel_mentions(text: str) -> int:
        return len(_CHANNEL_MENTION_RE.findall(text or ""))
