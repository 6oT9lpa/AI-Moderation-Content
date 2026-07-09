from __future__ import annotations

from src.infrastructure.database.database_url import redact_database_url


def test_database_url_redaction_hides_userinfo_and_query_password() -> None:
    redacted = redact_database_url(
        "postgresql://moderator:super-secret@db.example:5432/moderation?password=another-secret"
    )

    assert "super-secret" not in redacted
    assert "another-secret" not in redacted
    assert "moderator:***@" in redacted
    assert "password=***" in redacted
