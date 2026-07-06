from __future__ import annotations

import pytest

from src.infrastructure.logging import get_logger

logger = get_logger("tests")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(autouse=True)
def log_test_case(request: pytest.FixtureRequest):
    test_name = request.node.nodeid

    logger.info("TEST START name=%s", test_name)

    yield

    report = getattr(request.node, "rep_call", None)

    if report is None:
        logger.info("TEST FINISH name=%s status=unknown", test_name)
        return

    if report.passed:
        logger.info("TEST PASSED name=%s duration=%.4fs", test_name, report.duration)
        return

    if report.failed:
        logger.error("TEST FAILED name=%s duration=%.4fs", test_name, report.duration)
        return

    if report.skipped:
        logger.warning("TEST SKIPPED name=%s duration=%.4fs", test_name, report.duration)
        return

    logger.info("TEST FINISH name=%s status=%s duration=%.4fs", test_name, report.outcome, report.duration)
