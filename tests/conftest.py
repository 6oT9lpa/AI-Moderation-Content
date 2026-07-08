from __future__ import annotations

import json
import inspect
from collections.abc import Mapping
from typing import Any

import pytest

from src.infrastructure.logging import get_logger

logger = get_logger("tests")

MAX_VALUE_LENGTH = 500
MAX_TEXT_PREVIEW_LENGTH = 160


def pytest_sessionstart(session: pytest.Session) -> None:
    logger.info("")
    logger.info("================================================================================")
    logger.info("TEST SESSION START root=%s", session.config.rootpath)
    logger.info("================================================================================")


def pytest_collection_finish(session: pytest.Session) -> None:
    logger.info("TEST COLLECTION FINISHED total_tests=%s", len(session.items))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
    _log_phase_report(item, report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    logger.info("================================================================================")
    logger.info("TEST SESSION FINISH exitstatus=%s total_tests=%s", exitstatus, len(session.items))
    logger.info("================================================================================")


@pytest.fixture(autouse=True)
def log_test_case(request: pytest.FixtureRequest):
    item = request.node
    test_name = item.nodeid
    location = _get_item_location(item)

    logger.info("")
    logger.info("--------------------------------------------------------------------------------")
    logger.info("TEST CASE START")
    logger.info("  nodeid=%s", test_name)
    logger.info("  file=%s", location["file"])
    logger.info("  line=%s", location["line"])
    logger.info("  function=%s", item.name)
    logger.info("  markers=%s", _get_marker_names(item))
    _log_structured_test_inputs(item)
    logger.info("--------------------------------------------------------------------------------")

    yield

    report = getattr(item, "rep_call", None)

    if report is None:
        logger.info("TEST CASE FINISH status=unknown nodeid=%s", test_name)
        return

    if report.passed:
        logger.info("TEST CASE PASSED duration=%.4fs nodeid=%s", report.duration, test_name)
        return

    if report.failed:
        logger.error("TEST CASE FAILED duration=%.4fs nodeid=%s", report.duration, test_name)
        return

    if report.skipped:
        logger.warning("TEST CASE SKIPPED duration=%.4fs nodeid=%s", report.duration, test_name)
        return

    logger.info("TEST CASE FINISH status=%s duration=%.4fs nodeid=%s", report.outcome, report.duration, test_name)


@pytest.fixture
def structured_test_logger(request: pytest.FixtureRequest):
    def log_section(section: str, data: Mapping[str, Any] | list[Any]) -> None:
        caller = inspect.stack()[1]
        logger.info(
            "TEST %-9s source=%s:%s data=%s",
            section.upper(),
            caller.filename,
            caller.lineno,
            _safe_json(_summarize_parameter(data)),
        )

    return log_section


def _log_phase_report(item: pytest.Item, report: pytest.TestReport) -> None:
    log_method = logger.info
    location = _get_item_location(item)

    if report.failed:
        log_method = logger.error
    elif report.skipped:
        log_method = logger.warning

    log_method(
        "TEST PHASE %-8s outcome=%s duration=%.4fs file=%s line=%s nodeid=%s",
        report.when.upper(),
        report.outcome,
        report.duration,
        location["file"],
        location["line"],
        item.nodeid,
    )

    if report.failed:
        logger.error("TEST FAILURE DETAIL nodeid=%s details=%s", item.nodeid, report.longreprtext)


def _get_marker_names(item: pytest.Item) -> list[str]:
    return sorted(marker.name for marker in item.iter_markers())


def _get_item_location(item: pytest.Item) -> dict[str, object]:
    file_path, line_number, _test_name = item.location
    return {
        "file": str(item.config.rootpath / file_path),
        "line": line_number + 1,
    }


def _log_structured_test_inputs(item: pytest.Item) -> None:
    callspec = getattr(item, "callspec", None)

    if callspec is None:
        logger.info("TEST INPUT    data={}")
        return

    for name, value in callspec.params.items():
        if isinstance(value, Mapping) and "input" in value and "expected" in value:
            logger.info("TEST INPUT    param=%s data=%s", name, _safe_json(_summarize_parameter(value["input"])))
            logger.info("TEST EXPECTED param=%s data=%s", name, _safe_json(_summarize_parameter(value["expected"])))
            logger.info("TEST CASE META param=%s data=%s", name, _safe_json(_summarize_parameter(value)))
            continue

        logger.info("TEST INPUT    param=%s data=%s", name, _safe_json(_summarize_parameter(value)))


def _summarize_parameter(value: object) -> object:
    if isinstance(value, Mapping):
        if "input" in value and "id" in value:
            input_payload = value.get("input")
            expected = value.get("expected")

            if isinstance(input_payload, Mapping):
                return {
                    "id": value.get("id"),
                    "primary_label": value.get("primary_label"),
                    "message_id": input_payload.get("message_id"),
                    "platform": input_payload.get("platform"),
                    "channel_id": input_payload.get("channel_id"),
                    "raw_text_preview": _shorten(input_payload.get("raw_text")),
                    "dataset_expected": expected,
                    "preprocessing_expected": value.get("expected_preprocessing"),
                }

        if "label" in value and "cases" in value:
            return {
                "label": value.get("label"),
                "case_count": len(value.get("cases", [])),
                "path": value.get("_path"),
            }

        return {
            str(key): _summarize_parameter(nested_value)
            for key, nested_value in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if len(items) > 10:
            return {
                "count": len(items),
                "first_items": [_summarize_parameter(item) for item in items[:10]],
            }
        return [_summarize_parameter(item) for item in items]

    return _shorten(value)


def _safe_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return _shorten(value)


def _shorten(value: object, max_length: int = MAX_VALUE_LENGTH) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value

    text = str(value)
    limit = min(max_length, MAX_TEXT_PREVIEW_LENGTH) if "\n" in text else max_length

    if len(text) <= limit:
        return text

    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"
