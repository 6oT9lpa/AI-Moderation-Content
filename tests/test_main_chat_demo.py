from main import _parse_chat_line


def test_chat_demo_parser_accepts_cyrillic_channel_and_user() -> None:
    parsed = _parse_chat_line("@модерация #пользователь привет всем", "general")

    assert parsed["channel"] == "модерация"
    assert parsed["channel_changed"] is True
    assert parsed["user_id"] == "пользователь"
    assert parsed["text"] == "привет всем"

