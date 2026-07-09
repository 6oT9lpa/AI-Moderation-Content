from __future__ import annotations

from src.training.datasets.training_text_sanitizer import TrainingTextSanitizer


def test_training_text_sanitizer_keeps_discord_mentions_as_tags() -> None:
    sanitizer = TrainingTextSanitizer()

    text = sanitizer.sanitize("<@123456789012345678> <@&123456789012345678> <#123456789012345678>")

    assert text == "<DISCORD_USER_MENTION> <DISCORD_ROLE_MENTION> <DISCORD_CHANNEL_MENTION>"
    assert "<PHONE>" not in text


def test_training_text_sanitizer_is_idempotent_for_placeholders() -> None:
    sanitizer = TrainingTextSanitizer()
    text = "<URL_DOMAIN:cdn.discordapp.com> <DISCORD_INVITE> <EMAIL>"

    assert sanitizer.sanitize(text) == text
    assert sanitizer.sanitize(sanitizer.sanitize(text)) == text


def test_training_text_sanitizer_does_not_nest_url_domain_tokens() -> None:
    sanitizer = TrainingTextSanitizer()

    text = sanitizer.sanitize(
        "file https://cdn.discordapp.com/attachments/1129934674425294899/1155614824257040434/image.png"
    )

    assert text == "file <URL_DOMAIN:cdn.discordapp.com>"
    assert "<url_domain:<URL_DOMAIN:" not in text
    assert "<PHONE>" not in text


def test_training_text_sanitizer_handles_angle_wrapped_urls() -> None:
    sanitizer = TrainingTextSanitizer()

    text = sanitizer.sanitize("<https://cdn.discordapp.com/attachments/1129934674425294899/1/image.gif>")

    assert text == "<URL_DOMAIN:cdn.discordapp.com>"


def test_training_text_sanitizer_redacts_credentials_without_corrupting_discord_mentions() -> None:
    sanitized = TrainingTextSanitizer().sanitize(
        "<@123456789012345678> 4111 1111 1111 1111 "
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signaturevalue"
    )

    assert sanitized.startswith("<DISCORD_USER_MENTION>")
    assert "4111 1111 1111 1111" not in sanitized
    assert "eyJhbGciOiJIUzI1NiJ9" not in sanitized
    assert "<CARD>" in sanitized
    assert "<ACCESS_TOKEN>" in sanitized
