from abc import ABC, abstractmethod

from src.domain.media.media_rule_policy import MediaRulePolicy


class MediaPolicyDefaultsProvider(ABC):
    @abstractmethod
    def get_defaults(self) -> MediaRulePolicy:
        raise NotImplementedError
