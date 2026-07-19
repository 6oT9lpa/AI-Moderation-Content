import asyncio
from pathlib import Path

from src.application.api_moderation_service import ApiModerationService
from src.application.moderation_request_queue import ModerationRequestQueue
from src.infrastructure.api.api_settings import ApiSettings
from src.infrastructure.api.internal_api_key_validator import InternalApiKeyValidator
from src.infrastructure.api.local_rate_limiter import LocalRateLimiter
from src.infrastructure.phishing.google_safe_browsing_url_reputation_provider import (
    GoogleSafeBrowsingUrlReputationProvider,
)
from src.infrastructure.phishing.rdap_domain_age_provider import RdapDomainAgeProvider
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.repository.postgresql_dataset_collector_repository import PostgresqlDatasetCollectorRepository
from src.infrastructure.repository.postgresql_moderation_event_repository import PostgresqlModerationEventRepository
from src.infrastructure.repository.postgresql_policy_repository import PostgresqlPolicyRepository
from src.infrastructure.logging import get_logger
from src.modules.dataset.dataset_collector import DatasetCollector
from src.modules.decision.decision_engine import DecisionEngine
from src.modules.policy.policy_resolver import PolicyResolver
from src.modules.phishing.phishing_link_service import PhishingLinkService
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
        phishing_link_service = self._build_phishing_link_service()
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
            phishing_link_service=phishing_link_service,
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
        container.rubert_enabled = self._settings.api_rubert_enabled
        container.rubert_required = self._settings.api_rubert_required
        container.rubert_ready = classifier is not None
        container.model_id = str(classifier.model_dir) if classifier else None
        return container

    def _build_phishing_link_service(self) -> PhishingLinkService:
        if not self._settings.phishing_enabled:
            logger.info("Phishing URL checking is disabled")
            return PhishingLinkService(domain_age_provider=None, reputation_provider=None)

        domain_age_provider = (
            RdapDomainAgeProvider(self._settings.phishing_request_timeout_seconds)
            if self._settings.phishing_rdap_enabled
            else None
        )
        reputation_provider = (
            GoogleSafeBrowsingUrlReputationProvider(
                self._settings.phishing_google_safe_browsing_api_key,
                self._settings.phishing_request_timeout_seconds,
            )
            if self._settings.phishing_google_safe_browsing_api_key
            else None
        )
        logger.info(
            "Phishing URL checking configured domain_age_provider=%s reputation_provider=%s",
            domain_age_provider is not None,
            reputation_provider is not None,
        )
        return PhishingLinkService(
            domain_age_provider=domain_age_provider,
            reputation_provider=reputation_provider,
        )

    def _load_classifier(self) -> RuBertModerationClassifier | None:
        if not self._settings.api_rubert_enabled:
            return None
        try:
            model_dir = Path(self._settings.api_rubert_model_dir)
            classifier = RuBertModerationClassifier(model_dir=model_dir)
            logger.info("Local ruBERT loaded model_dir=%s device=%s", classifier.model_dir, classifier.device)
            return classifier
        except Exception as exc:
            logger.warning(
                "Local ruBERT is unavailable; moderation will use rule-based fallback model_dir=%s error=%s",
                self._settings.api_rubert_model_dir,
                exc,
            )
            return None
