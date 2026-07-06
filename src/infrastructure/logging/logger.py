from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Any, Optional


class LoggerManager:
    _instance: Optional["LoggerManager"] = None

    LOGGER_NAMES = ("application", "infrastructure", "modules", "shared")
    TEST_LOGGER_NAMES = ("tests", "tests.preprocessing")

    def __new__(cls) -> "LoggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configure()
        return cls._instance

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)

    def _configure(self) -> None:
        log_level = self._get_configured_log_level()

        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        app_log_file = log_dir / "ai-moder.log"
        tests_log_file = log_dir / "tests.log"

        dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": log_format,
                        "datefmt": date_format,
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": log_level,
                        "formatter": "default",
                        "stream": "ext://sys.stdout",
                    },
                    "app_file": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "level": log_level,
                        "formatter": "default",
                        "filename": str(app_log_file),
                        "maxBytes": 10 * 1024 * 1024,
                        "backupCount": 5,
                        "encoding": "utf-8",
                    },
                    "test_file": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "level": log_level,
                        "formatter": "default",
                        "filename": str(tests_log_file),
                        "maxBytes": 10 * 1024 * 1024,
                        "backupCount": 5,
                        "encoding": "utf-8",
                    },
                },
                "loggers": {
                    **{
                        logger_name: {
                            "level": log_level,
                            "handlers": ["console", "app_file"],
                            "propagate": False,
                        }
                        for logger_name in self.LOGGER_NAMES
                    },
                    **{
                        logger_name: {
                            "level": log_level,
                            "handlers": ["test_file"],
                            "propagate": False,
                        }
                        for logger_name in self.TEST_LOGGER_NAMES
                    },
                },
                "root": {
                    "level": log_level,
                    "handlers": ["console", "app_file"],
                },
            }
        )

    @classmethod
    def _get_configured_log_level(cls) -> str:
        try:
            from src.infrastructure.config import get_config

            config = get_config()
            return cls._normalize_log_level(getattr(config, "log_level", "INFO"))
        except Exception:
            return "INFO"

    @staticmethod
    def _normalize_log_level(value: Any) -> str:
        if isinstance(value, str):
            normalized = value.upper().strip()
            if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
                return normalized

        return "INFO"


def get_logger(name: str) -> logging.Logger:
    return LoggerManager().get_logger(name)
