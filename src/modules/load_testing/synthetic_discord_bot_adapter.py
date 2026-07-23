from __future__ import annotations

import re
from datetime import datetime, timezone

from src.modules.load_testing.synthetic_discord_bot_event import (
    SyntheticDiscordBotPayload,
    SyntheticDiscordMessage,
)

_USER_MENTION_RE = re.compile(r"<@!?\d+>")
_ROLE_MENTION_RE = re.compile(r"<@&\d+>")
_CHANNEL_MENTION_RE = re.compile(r"<#\d+>")


class SyntheticDiscordBotAdapter:
    """Converts synthetic Discord gateway events into API payloads.

    The benchmark intentionally does not connect to Discord's real Gateway:
    Discord rate limits and websocket scheduling would make RPS measurements
    noisy.  This adapter exercises the same payload-shaping boundary a bot
    worker owns before it calls the moderation API.
    """

    def build_moderation_payload(
        self,
        message: SyntheticDiscordMessage,
        *,
        recent_messages: tuple[str, ...] = (),
        recent_message_timestamps: tuple[datetime, ...] = (),
    ) -> dict[str, object]:
        content = message.content or ""
        return {
            "platform": "discord",
            "guild_id": message.guild_id,
            "channel_id": message.channel_id,
            "user_id": message.author.id,
            "message_id": message.id,
            "raw_text": content,
            "created_at": message.created_at.isoformat(),
            "reply_to_message_id": message.referenced_message_id,
            "mention_count": len(_USER_MENTION_RE.findall(content)),
            "role_mention_count": len(_ROLE_MENTION_RE.findall(content)),
            "channel_mention_count": len(_CHANNEL_MENTION_RE.findall(content)),
            "has_attachments": message.attachment_count > 0,
            "attachment_count": message.attachment_count,
            "recent_messages": recent_messages,
            "recent_message_timestamps": tuple(item.isoformat() for item in recent_message_timestamps),
            "metadata": {
                "event_type": "synthetic_discord_message_create",
                "author_is_bot": message.author.bot,
                "attachment_count": message.attachment_count,
                "embed_count": message.embed_count,
            },
        }

    def build_action_result_payload(
        self,
        moderation_response: dict[str, object],
        *,
        dry_run: bool,
    ) -> dict[str, object] | None:
        action = str(moderation_response.get("decision_action") or "IGNORE")
        if action == "IGNORE":
            return None

        return {
            "event_id": moderation_response.get("dataset_event_id"),
            "message_id": moderation_response.get("message_id"),
            "action": action,
            "status": "DRY_RUN" if dry_run else "SUCCESS",
            "dry_run": dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def build_payloads(
        self,
        message: SyntheticDiscordMessage,
        *,
        recent_messages: tuple[str, ...] = (),
        recent_message_timestamps: tuple[datetime, ...] = (),
    ) -> SyntheticDiscordBotPayload:
        return SyntheticDiscordBotPayload(
            moderation_payload=self.build_moderation_payload(
                message,
                recent_messages=recent_messages,
                recent_message_timestamps=recent_message_timestamps,
            ),
            action_result_payload=None,
        )
