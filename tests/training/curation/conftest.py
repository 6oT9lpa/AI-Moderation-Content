import pytest

from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


@pytest.fixture(scope="session")
def sensitive_topic_matcher() -> SensitiveTopicMatcher:
    """Small explicit policy for curation behavior tests; no production file dependency."""
    return SensitiveTopicMatcher.from_mapping(
        {
            "proximity_chars": 96,
            "harm_proximity_chars": {
                "degradation": 24,
                "hate_action": 64,
                "threat": 16,
                "sexual": 48,
                "sexual_abuse": 96,
                "profanity": 32,
            },
            "group_context": {
                "patterns": (
                    r"\b(?:все|эти|те|такие|любые|каждая|каждый|большинство|поголовно|всегда)\b",
                    r"\b(?:all|these|those|every|most|always)\b",
                )
            },
            "topics": {
                "race": {"patterns": (r"\b(?:чернокож\w*|темнокож\w*|африканц\w*|азиат\w*|евре\w*)\b",)},
                "gender": {"patterns": (r"\b(?:женщин\w*|мужчин\w*|women|woman|men|man)\b",)},
                "family": {
                    "patterns": (
                        r"\b(?:семь[яеиюёй]|семьи|семью|семей\w*|родн(?:я|и|ю)|родствен\w*|близк(?:ие|их|им|ими)|мам\w*|матер(?:и|ью)|мать|пап\w*|отц\w*|отец|родител\w*|брат(?:а|у|ом|е|ья|ьев|ьям|ьями|ьях)?|сестр\w*|сын\w*|доч(?:ь|ери|ерью)|дед\w*|бабушк\w*|жен[аеуы]|муж(?:а|у|ем|ья|ей)?)\b",
                        r"\b(?:моих|твоих|своих|наших|ваших|его|её|их)\s+родных\b",
                        r"\b(?:family|families|relatives?|mother|father|parents?|brothers?|sisters?)\b",
                    )
                },
            },
            "harm": {
                "degradation": {"patterns": (r"\b(?:туп\w*|грязн\w*|животн\w*|stupid|inferior|animals?)\b",)},
                "hate_action": {"patterns": (r"\b(?:ненавиж\w*|уничтож\w*|истреб\w*|hate|exterminate)\b",)},
                "threat": {
                    "patterns": (
                        r"\b(?:убью|зарежу|сожгу|пристрелю|застрелю|изобью|покалечу|изнасилую|повешу|утоплю)\b",
                        r"\b(?:надо|нужно|следует|хочу|пора)\s+(?:убить|зарезать|сжечь|пристрелить|избить|покалечить|повесить|утопить)\b",
                        r"\b(?:найду\s+(?:тво\w*|ваш\w*)|доберусь\s+до\s+(?:тво\w*|ваш\w*))\b",
                        r"\b(?:i\s+will|i'll)\s+(?:find\s+\w+\s+and\s+)?(?:kill|murder|hurt|rape)\b",
                    )
                },
                "sexual": {"patterns": (r"\b(?:изнасил\w*|секс\w*|rape|sex|sexual)\b",)},
                "sexual_abuse": {"patterns": (r"\b(?:изнасилую|rape\s+(?:your|his|her|their))\b",)},
                "profanity": {"patterns": (r"\b(?:хуй\w*|бляд\w*|fuck|shit)\b",)},
            },
            "counter_context": {
                "patterns": (
                    r"\b(?:нельзя|недопустимо|против\s+расизма|равные\s+права|не\s+все)\b",
                    r"\b(?:condemn|against\s+racism|equal\s+rights|not\s+all)\b",
                )
            },
        }
    )
