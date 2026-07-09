from __future__ import annotations

import re


def redact_database_url(value: str) -> str:
    value = re.sub(r"(?i)(password=)[^\s&]+", r"\1***", value)
    return re.sub(r"(://[^:/?#]+:)[^@\s]+", r"\1***", value)
