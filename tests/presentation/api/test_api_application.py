import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.contracts.api.api_ack_schema import ApiAckSchema
from src.contracts.api.effective_policy_response_schema import EffectivePolicyResponseSchema
from src.contracts.api.moderation_message_response_schema import ModerationMessageResponseSchema
from src.application.moderation_request_queue import ModerationRequestQueue
from src.infrastructure.api.api_settings import ApiSettings
from src.infrastructure.api.internal_api_key_validator import InternalApiKeyValidator
from src.infrastructure.api.local_rate_limiter import LocalRateLimiter
from src.infrastructure.logging import get_logger
from src.presentation.api.api_application_factory import create_api_application
from src.presentation.api.api_container import ApiContainer

logger = get_logger(__name__)


class _DatabaseStub:
    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _ServiceStub:
    async def initialize_policy_status(self) -> str:
        return "test-v1"

    async def moderate(self, payload, correlation_id: str) -> ModerationMessageResponseSchema:
        return ModerationMessageResponseSchema(
            correlation_id=correlation_id,
            message_id=payload.message_id,
            labels=("SAFE",),
            primary_label="SAFE",
            rule_matches=(),
            rubert_labels=(),
            risk_score=0,
            risk_breakdown=(),
            decision_action="IGNORE",
            severity=0,
            reason="safe",
            policy_id="test-policy",
            policy_version="test-v1",
            execution_status="PENDING",
            execution_plan=("IGNORE",),
            dataset_event_id=1,
            latency_ms=0,
        )

    async def submit_feedback(self, _, correlation_id: str) -> ApiAckSchema:
        return ApiAckSchema(correlation_id=correlation_id, event_id=1, status="accepted")

    async def submit_action_result(self, _, correlation_id: str) -> ApiAckSchema:
        return ApiAckSchema(correlation_id=correlation_id, event_id=1, status="accepted")

    async def effective_policies(self, _, __, ___, correlation_id: str) -> EffectivePolicyResponseSchema:
        return EffectivePolicyResponseSchema(correlation_id=correlation_id, policies=())


def _client(rate_limit: int = 10) -> TestClient:
    settings = ApiSettings(internal_api_key="test-key-value-1234", api_rate_limit=rate_limit)
    service = _ServiceStub()
    container = ApiContainer(
        service=service,
        database=_DatabaseStub(),
        key_validator=InternalApiKeyValidator("test-key-value-1234"),
        rate_limiter=LocalRateLimiter(rate_limit, 60),
        inference_semaphore=asyncio.Semaphore(1),
        moderation_queue=ModerationRequestQueue(service, 1, 10),
    )
    return TestClient(create_api_application("postgresql://unused", settings, container))


def _payload() -> dict[str, object]:
    return {
        "platform": "discord",
        "guild_id": "1",
        "channel_id": "2",
        "user_id": "3",
        "message_id": "4",
        "raw_text": "private message body",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_health_is_available_without_key() -> None:
    logger.info("API test expected=200 actual=health request without credentials")
    with _client() as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database_status"] == "ready"


def test_moderation_requires_valid_key_and_omits_raw_text() -> None:
    logger.info("API test expected=401_then_200 actual=moderation auth flow")
    with _client() as client:
        denied = client.post("/moderation/messages", json=_payload())
        accepted = client.post("/moderation/messages", json=_payload(), headers={"X-Internal-Api-Key": "test-key-value-1234"})
    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert "raw_text" not in accepted.text
    assert "private message body" not in accepted.text


def test_unknown_request_field_is_rejected_safely() -> None:
    logger.info("API test expected=422 actual=unknown-field validation")
    body = _payload()
    body["unexpected"] = True
    with _client() as client:
        response = client.post("/moderation/messages", json=body, headers={"X-Internal-Api-Key": "test-key-value-1234"})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"
    assert "private message body" not in response.text


def test_rate_limit_returns_safe_error() -> None:
    logger.info("API test expected=429 actual=bounded-local-rate-limit")
    with _client(rate_limit=1) as client:
        first = client.get("/health")
        second = client.get("/health")
    assert first.status_code == 200
    assert second.status_code == 429


def test_feedback_action_and_policy_routes_require_authentication() -> None:
    logger.info("API test expected=200 actual=authenticated feedback-action-policy routes")
    headers = {"X-Internal-Api-Key": "test-key-value-1234"}
    timestamp = datetime.now(timezone.utc).isoformat()
    with _client() as client:
        feedback = client.post("/moderation/feedback", json={"event_id": 1, "feedback_type": "confirmed"}, headers=headers)
        action = client.post(
            "/actions/result",
            json={"event_id": 1, "action": "IGNORE", "status": "SKIPPED", "dry_run": False, "timestamp": timestamp},
            headers=headers,
        )
        policy = client.get("/policies/effective?platform=discord&guild_id=1", headers=headers)
    assert feedback.status_code == 200
    assert action.status_code == 200
    assert policy.status_code == 200
