import asyncio

from src.application.api_moderation_service import ApiModerationService
from src.application.moderation_request_queue import ModerationRequestQueue
from src.infrastructure.api.api_settings import ApiSettings
from src.infrastructure.api.internal_api_key_validator import InternalApiKeyValidator
from src.infrastructure.api.local_rate_limiter import LocalRateLimiter
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.repository.postgresql_dataset_collector_repository import PostgresqlDatasetCollectorRepository
from src.infrastructure.repository.postgresql_moderation_event_repository import PostgresqlModerationEventRepository
from src.infrastructure.repository.postgresql_policy_repository import PostgresqlPolicyRepository
from src.infrastructure.logging import get_logger
from src.modules.dataset.dataset_collector import DatasetCollector
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.policy.policy_resolver import PolicyResolver
from src.modules.preprocessing.text_preprocessor import TextPreprocessor
from src.modules.rules.moderation_rule_engine import ModerationRuleEngine
from src.modules.rules.preprocessing_signal_adapter import PreprocessingSignalAdapter
from src.presentation.api.api_container import ApiContainer
from src.training.rubert.rubert_moderation_classifier import RuBertModerationClassifier

logger = get_logger(__name__)


class ApiCompositionRoot:
    def __init__(self, database_url: str, settings: ApiSettings) -> None:
        self._database_url = database_url
        self._settings = settings

    def build(self) -> ApiContainer:
        database = DatabaseConnection(self._database_url)
        policy_repository = PostgresqlPolicyRepository(database)
        policy_resolver = PolicyResolver(policy_repository)
        inference_semaphore = asyncio.Semaphore(self._settings.api_inference_concurrency)
        classifier = self._load_classifier()
        service = ApiModerationService(
            preprocessor=TextPreprocessor(),
            rule_engine=ModerationRuleEngine(),
            decision_engine=DecisionEngine(),
            signal_adapter=PreprocessingSignalAdapter(),
            dataset_collector=DatasetCollector(PostgresqlDatasetCollectorRepository(database)),
            policy_resolver=policy_resolver,
            event_repository=PostgresqlModerationEventRepository(database),
            inference_semaphore=inference_semaphore,
            rubert_classifier=classifier,
        )
        moderation_queue = ModerationRequestQueue(service, self._settings.api_queue_workers, self._settings.api_queue_size)
        container = ApiContainer(
            service=service,
            database=database,
            key_validator=InternalApiKeyValidator(self._settings.internal_api_key or ""),
            rate_limiter=LocalRateLimiter(self._settings.api_rate_limit, self._settings.api_rate_window_seconds),
            inference_semaphore=inference_semaphore,
            moderation_queue=moderation_queue,
        )
        container.rubert_ready = classifier is not None
        container.model_id = str(classifier.model_dir) if classifier else None
        return container

    def _load_classifier(self) -> RuBertModerationClassifier | None:
        if not self._settings.api_rubert_enabled:
            return None
        try:
            return RuBertModerationClassifier()
        except Exception:
            logger.warning("Local ruBERT is unavailable; moderation will use rule-based fallback")
            return None
