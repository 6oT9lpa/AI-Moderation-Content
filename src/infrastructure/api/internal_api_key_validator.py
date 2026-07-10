import hmac


class InternalApiKeyValidator:
    def __init__(self, expected_key: str) -> None:
        self._expected_key = expected_key

    def is_valid(self, candidate: str | None) -> bool:
        return candidate is not None and hmac.compare_digest(candidate, self._expected_key)
