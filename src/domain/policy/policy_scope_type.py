from __future__ import annotations

from enum import StrEnum


class PolicyScopeType(StrEnum):
    GLOBAL = "GLOBAL"
    PLATFORM = "PLATFORM"
    GUILD = "GUILD"
    CHAT = "CHAT"
    CHANNEL = "CHANNEL"
    USER = "USER"
    ROLE = "ROLE"
