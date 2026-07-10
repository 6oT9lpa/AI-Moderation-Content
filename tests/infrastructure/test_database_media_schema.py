from __future__ import annotations

from src.infrastructure.database.connection import DatabaseConnection


def test_database_media_schema_contains_audit_fields_and_idempotent_upgrades(structured_test_logger) -> None:
    connection = DatabaseConnection("postgresql://localhost:5432/moderation")
    table_statements = connection._get_create_table_statements()
    index_statements = connection._get_create_index_statements()
    upgrade_statements = connection._get_schema_upgrade_statements()
    media_table = next(statement for statement in table_statements if "ai_media_attachments" in statement)
    actual = {
        "has_ocr_text_density": "ocr_text_density" in media_table,
        "has_ocr_status": "ocr_status" in media_table,
        "has_ocr_error": "ocr_error" in media_table,
        "has_money_amounts": "ocr_money_amounts_json" in media_table,
        "has_domains": "ocr_domains_json" in media_table,
        "has_keyword_evidence": "ocr_keywords_json" in media_table,
        "has_fake_news": "ocr_has_fake_news" in media_table,
        "has_scam_subtype": "scam_subtype" in media_table,
        "has_subtype_index": any("idx_ai_media_attachments_scam_subtype" in statement for statement in index_statements),
        "all_upgrades_idempotent": all("ADD COLUMN IF NOT EXISTS" in statement for statement in upgrade_statements),
    }
    expected = {key: True for key in actual}
    structured_test_logger(
        "input",
        {
            "table_count": len(table_statements),
            "index_count": len(index_statements),
            "upgrade_count": len(upgrade_statements),
        },
    )
    structured_test_logger("detection", {"expected": expected, "actual": actual})

    assert actual == expected
