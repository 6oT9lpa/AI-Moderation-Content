from __future__ import annotations

import json
import inspect
from collections.abc import Mapping
from enum import Enum
from typing import Any

import pytest

from src.infrastructure.logging import get_logger

logger = get_logger("tests")

MAX_VALUE_LENGTH = 500
MAX_TEXT_PREVIEW_LENGTH = 160
COMPARISON_IGNORED_KEYS = {"settings"}
ORDER_INSENSITIVE_COMPARISON_KEYS = {"labels", "detected_labels"}


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
        summarized_data = _summarize_parameter(data)
        logger.info(
            "TEST %-9s source=%s:%s data=%s",
            section.upper(),
            caller.filename,
            caller.lineno,
            _safe_json(summarized_data),
        )

        if isinstance(data, Mapping):
            _log_expected_actual_comparison(section, data, caller.filename, caller.lineno)

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


def _log_expected_actual_comparison(
    section: str,
    data: Mapping[str, Any],
    source_file: str,
    source_line: int,
) -> None:
    comparison = _build_expected_actual_comparison(data)

    if comparison is None:
        return

    log_method = logger.info if comparison["status"] == "MATCH" else logger.warning
    log_method(
        "TEST COMPARISON section=%s status=%s source=%s:%s expected=%s actual=%s differences=%s",
        section.upper(),
        comparison["status"],
        source_file,
        source_line,
        _safe_json(_summarize_parameter(comparison["expected"])),
        _safe_json(_summarize_parameter(comparison["actual"])),
        _safe_json(_summarize_parameter(comparison["differences"])),
    )


def _build_expected_actual_comparison(data: Mapping[str, Any]) -> dict[str, Any] | None:
    if "expected" in data and "actual" in data:
        return _compare_values(data["expected"], data["actual"])

    expected_by_name: dict[str, Any] = {}
    actual_by_name: dict[str, Any] = {}

    for key, value in data.items():
        key_text = str(key)

        if key_text.startswith("expected_"):
            expected_by_name[key_text.removeprefix("expected_")] = value
            continue

        if key_text.startswith("actual_"):
            actual_by_name[key_text.removeprefix("actual_")] = value
            continue

        if key_text.endswith("_expected"):
            expected_by_name[key_text.removesuffix("_expected")] = value
            continue

        if key_text.endswith("_actual"):
            actual_by_name[key_text.removesuffix("_actual")] = value

    shared_pair_names = sorted(set(expected_by_name) & set(actual_by_name))
    if shared_pair_names:
        expected = {name: expected_by_name[name] for name in shared_pair_names}
        actual = {name: actual_by_name[name] for name in shared_pair_names}
        return _compare_values(expected, actual)

    expected_value = data.get("expected")
    if isinstance(expected_value, Mapping):
        actual = _extract_actual_values_for_expected(data, expected_value)

        if actual:
            expected = {key: expected_value[key] for key in actual}
            return _compare_values(expected, actual)

    return None


def _extract_actual_values_for_expected(
    data: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    actual: dict[str, Any] = {}
    aliases = {
        "labels": "detected_labels",
    }

    for expected_key in expected:
        actual_key = aliases.get(str(expected_key), str(expected_key))

        if actual_key in data:
            actual[str(expected_key)] = data[actual_key]

    return actual


def _compare_values(expected: Any, actual: Any) -> dict[str, Any]:
    visible_expected = _remove_ignored_comparison_keys(expected)
    visible_actual = _remove_ignored_comparison_keys(actual)
    normalized_expected = _normalize_for_compare(visible_expected)
    normalized_actual = _normalize_for_compare(visible_actual)
    differences = _build_differences(normalized_expected, normalized_actual)

    return {
        "status": "MATCH" if not differences else "MISMATCH",
        "expected": visible_expected,
        "actual": visible_actual,
        "differences": differences,
    }


def _build_differences(expected: Any, actual: Any, path: str = "$") -> list[dict[str, Any]]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        differences: list[dict[str, Any]] = []
        keys = sorted(set(expected) | set(actual))

        for key in keys:
            if key in COMPARISON_IGNORED_KEYS:
                continue

            child_path = f"{path}.{key}"

            if key not in expected:
                differences.append({"path": child_path, "expected": "<missing>", "actual": actual[key]})
                continue

            if key not in actual:
                differences.append({"path": child_path, "expected": expected[key], "actual": "<missing>"})
                continue

            differences.extend(_build_differences(expected[key], actual[key], child_path))

        return differences

    if expected != actual:
        return [{"path": path, "expected": expected, "actual": actual}]

    return []


def _normalize_for_compare(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if hasattr(value, "model_dump"):
        return _normalize_for_compare(value.model_dump(mode="json"))

    if isinstance(value, Mapping):
        normalized_mapping: dict[str, Any] = {}

        for key, nested_value in value.items():
            key_text = str(key)
            normalized_value = _normalize_for_compare(nested_value)

            if key_text in ORDER_INSENSITIVE_COMPARISON_KEYS and isinstance(normalized_value, list):
                normalized_value = sorted(normalized_value)

            normalized_mapping[key_text] = normalized_value

        return normalized_mapping

    if isinstance(value, (list, tuple)):
        return [_normalize_for_compare(item) for item in value]

    if isinstance(value, set):
        return sorted(_normalize_for_compare(item) for item in value)

    return value


def _remove_ignored_comparison_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _remove_ignored_comparison_keys(nested_value)
            for key, nested_value in value.items()
            if key not in COMPARISON_IGNORED_KEYS
        }

    if isinstance(value, list):
        return [_remove_ignored_comparison_keys(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_remove_ignored_comparison_keys(item) for item in value)

    return value


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
