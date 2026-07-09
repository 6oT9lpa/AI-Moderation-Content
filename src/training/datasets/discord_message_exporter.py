from __future__ import annotations

import hashlib
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer


@dataclass(frozen=True, slots=True)
class DiscordChannelExport:
    guild_id: str
    channel_id: str
    label: ModerationLabel = ModerationLabel.SAFE
    source_tag: str = "discord_hard_safe"


class DiscordMessageConverter:
    def __init__(self, *, hash_salt: str, sanitizer: TrainingTextSanitizer | None = None) -> None:
        self._hash_salt = hash_salt
        self._sanitizer = sanitizer or TrainingTextSanitizer()

    def to_raw_record(
        self,
        message: dict[str, Any],
        channel: DiscordChannelExport,
    ) -> dict[str, Any]:
        author = message.get("author") if isinstance(message.get("author"), dict) else {}
        return {
            "platform": "discord",
            "guild_id_hash": self._hash_value(channel.guild_id),
            "channel_id_hash": self._hash_value(channel.channel_id),
            "user_id_hash": self._hash_value(str(author.get("id", ""))),
            "message_id": str(message.get("id", "")),
            "created_at": message.get("timestamp"),
            "edited_at": message.get("edited_timestamp"),
            "content": str(message.get("content") or ""),
            "attachments_count": len(message.get("attachments") or []),
            "embeds_count": len(message.get("embeds") or []),
            "source_tag": channel.source_tag,
        }

    def to_project_training_row(
        self,
        message: dict[str, Any],
        channel: DiscordChannelExport,
    ) -> dict[str, Any] | None:
        content = str(message.get("content") or "")
        model_text = self._sanitizer.sanitize(content)
        if not model_text:
            return None

        primary_label = channel.label
        return {
            "message_id": str(message.get("id", "")),
            "model_text": model_text,
            "labels": [primary_label.value],
            "primary_label": primary_label.value,
            "severity": 0 if primary_label == ModerationLabel.SAFE else 2,
            "source": "real_safe" if primary_label == ModerationLabel.SAFE else "real_moderated",
            "feedback_type": "confirmed",
            "annotation_source": "discord_export",
            "created_at": message.get("timestamp"),
            "metadata": {
                "source_bucket": "project",
                "source_tag": channel.source_tag,
                "guild_id_hash": self._hash_value(channel.guild_id),
                "channel_id_hash": self._hash_value(channel.channel_id),
                "user_id_hash": self._hash_author(message),
                "attachments_count": len(message.get("attachments") or []),
                "embeds_count": len(message.get("embeds") or []),
            },
        }

    def _hash_author(self, message: dict[str, Any]) -> str:
        author = message.get("author") if isinstance(message.get("author"), dict) else {}
        return self._hash_value(str(author.get("id", "")))

    def _hash_value(self, value: str) -> str:
        return hashlib.sha256(f"{self._hash_salt}:{value}".encode("utf-8")).hexdigest()


class DiscordRestMessageExporter:
    API_BASE = "https://discord.com/api/v10"

    def __init__(self, *, bot_token: str) -> None:
        if not bot_token or bot_token == "PASTE_DISCORD_BOT_TOKEN_HERE":
            raise ValueError("Paste your Discord bot token into DISCORD_BOT_TOKEN first")

        self._bot_token = bot_token

    def iter_channel_messages(
        self,
        channel_id: str,
        *,
        limit: int,
        page_size: int = 100,
    ):
        before: str | None = None
        fetched = 0

        while fetched < limit:
            params = {"limit": min(page_size, limit - fetched)}
            if before is not None:
                params["before"] = before

            messages = self._request_json(f"/channels/{channel_id}/messages", params)
            if not messages:
                break

            for message in messages:
                fetched += 1
                before = str(message["id"])
                yield message

                if fetched >= limit:
                    break

            if len(messages) < page_size:
                break

    def _request_json(self, path: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{self.API_BASE}{path}?{query}",
            headers={
                "Authorization": f"Bot {self._bot_token}",
                "User-Agent": "AI-Moderator-DatasetExporter/1.0",
            },
        )

        attempts = 0
        while True:
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429:
                    payload = json.loads(body)
                    time.sleep(float(payload.get("retry_after", 1.0)) + 0.25)
                    continue

                raise RuntimeError(f"Discord API failed status={exc.code} body={body}") from exc
            except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
                attempts += 1
                if attempts >= 5:
                    raise RuntimeError(f"Discord API request timed out after retries path={path}") from exc

                time.sleep(min(2**attempts, 30))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
