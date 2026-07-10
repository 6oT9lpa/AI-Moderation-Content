from __future__ import annotations

import asyncio
import json
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from src.contracts.load_testing.moderation_load_test_config import ModerationLoadTestConfig
from src.contracts.load_testing.moderation_load_test_result import ModerationLoadTestResult
from src.infrastructure.logging import get_logger
from src.modules.load_testing.moderation_load_test_planner import build_message_plan, build_moderation_payload
from src.modules.load_testing.moderation_load_test_report_builder import build_result

logger = get_logger(__name__)


class ModerationApiLoadTestRunner:
    def __init__(self, config: ModerationLoadTestConfig, *, internal_api_key: str) -> None:
        if not internal_api_key:
            raise ValueError("internal_api_key must not be empty")
        self._config = config
        self._internal_api_key = internal_api_key
        self._request_semaphore = asyncio.Semaphore(config.max_in_flight)

    async def run(self) -> ModerationLoadTestResult:
        plan = build_message_plan(self._config)
        started_at = time.perf_counter()
        logger.info(
            "Moderation API load test started total_messages=%s channels=%s users=%s target_rps=%.3f max_in_flight=%s",
            self._config.total_messages,
            self._config.channel_count,
            self._config.user_count,
            self._config.target_messages_per_second,
            self._config.max_in_flight,
        )
        request_results = await asyncio.gather(
            *(self._send_planned_message(item, started_at) for item in plan),
        )
        elapsed_seconds = time.perf_counter() - started_at
        result = build_result(self._config, request_results, elapsed_seconds=elapsed_seconds)
        logger.info(
            "Moderation API load test completed total=%s succeeded=%s failed=%s success_rate=%.4f p95_ms=%.3f targets_met=%s",
            result.total_messages,
            result.succeeded_messages,
            result.failed_messages,
            result.success_rate,
            result.latency_p95_ms,
            result.targets_met,
        )
        return result

    async def _send_planned_message(
        self,
        plan_item: dict[str, int | float],
        started_at: float,
    ) -> dict[str, int | float | str | None]:
        scheduled_at = started_at + float(plan_item["scheduled_offset_seconds"])
        await asyncio.sleep(max(0.0, scheduled_at - time.perf_counter()))
        payload = build_moderation_payload(plan_item, created_at=datetime.now(timezone.utc))
        request_started_at = time.perf_counter()
        async with self._request_semaphore:
            status_code, error_kind = await asyncio.to_thread(
                self._post_moderation_message,
                payload,
                str(plan_item["sequence"]),
            )
        return {
            "status_code": status_code,
            "error_kind": error_kind,
            "latency_ms": (time.perf_counter() - request_started_at) * 1_000,
        }

    def _post_moderation_message(self, payload: dict[str, Any], sequence: str) -> tuple[int | None, str | None]:
        request = urllib.request.Request(
            f"{self._config.base_url}/moderation/messages",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Internal-Api-Key": self._internal_api_key,
                "X-Correlation-Id": f"load-{sequence}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                return response.status, None
        except urllib.error.HTTPError as exc:
            return exc.code, "http_error"
        except (TimeoutError, socket.timeout):
            return None, "timeout"
        except urllib.error.URLError:
            return None, "connection_error"
