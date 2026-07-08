from enum import Enum


class ModerationMode(str, Enum):
    PASSIVE = "PASSIVE"
    ACTIVE = "ACTIVE"
    STRICT = "STRICT"
