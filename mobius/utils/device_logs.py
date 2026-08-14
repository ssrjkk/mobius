"""
Device logs + crash detection — если приложение падает во время теста,
без этого framework просто получит NoSuchElementException и непонятно
почему. Сбор logcat/syslog и определение краша — обязательная часть
любого серьёзного мобильного CI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)

# Паттерны краша в logcat — фатальные исключения Android
CRASH_PATTERNS = [
    r"FATAL EXCEPTION",
    r"AndroidRuntime:\s*FATAL",
    r"Process:.*has died",
    r"ANR in",  # Application Not Responding
]


@dataclass
class CrashReport:
    crashed: bool
    matched_lines: list[str] = field(default_factory=list)
    log_type: str = "logcat"

    def summary(self) -> str:
        if not self.crashed:
            return "No crash detected"
        lines = "\n".join(f"  {line}" for line in self.matched_lines[:5])
        return f"CRASH DETECTED ({len(self.matched_lines)} matches):\n{lines}"


class DeviceLogCollector:
    """Сбор device логов (Android logcat) и определение крашей приложения."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def get_available_log_types(self) -> list[str]:
        try:
            return list(self._driver.log_types)
        except Exception as e:
            logger.warning("get_available_log_types failed: %s", e)
            return []

    def get_logs(self, log_type: str = "logcat") -> list[dict[str, Any]]:
        """Возвращает сырые записи лога. Каждая — dict с ключами timestamp/level/message."""
        try:
            return list(self._driver.get_log(log_type))
        except Exception as e:
            logger.warning(
                "get_logs(log_type='%s') failed — check get_available_log_types() "
                "for supported types on this driver: %s",
                log_type,
                e,
            )
            return []

    def get_logs_text(self, log_type: str = "logcat") -> list[str]:
        return [entry.get("message", "") for entry in self.get_logs(log_type)]

    def check_for_crash(
        self, log_type: str = "logcat", app_package: str | None = None
    ) -> CrashReport:
        """
        Проверяет логи на признаки краша приложения.
        Если указан app_package — фильтрует только строки с упоминанием пакета.
        """
        lines = self.get_logs_text(log_type)
        if app_package:
            lines = [ln for ln in lines if app_package in ln]

        matched = []
        for line in lines:
            for pattern in CRASH_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    matched.append(line)
                    break

        return CrashReport(crashed=len(matched) > 0, matched_lines=matched, log_type=log_type)

    def assert_no_crash(self, app_package: str | None = None) -> None:
        report = self.check_for_crash(app_package=app_package)
        assert not report.crashed, report.summary()

    def find_errors(self, log_type: str = "logcat", level: str = "ERROR") -> list[str]:
        """Возвращает строки логов заданного уровня — для расследования не-краш проблем."""
        entries = self.get_logs(log_type)
        return [
            e.get("message", "")
            for e in entries
            if str(e.get("level", "")).upper() == level.upper()
        ]
