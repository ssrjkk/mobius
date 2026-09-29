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
from mobius.utils.driver_health import rethrow_if_driver_dead

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
    # Сколько строк реально прочитано и сколько дошло до проверки (после
    # фильтра по пакету). Без этого «крашей не найдено» неотличимо от
    # «логи не прочитаны вообще» — и то, и другое даёт зелёный прогон.
    lines_read: int = 0
    lines_checked: int = 0

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
            rethrow_if_driver_dead(e)
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
        Учитывай, что с фильтром проверяются только те строки, где пакет назван:
        без него зачёт шире, но в него попадают краши других приложений.
        """
        all_lines = self.get_logs_text(log_type)
        lines = [ln for ln in all_lines if app_package in ln] if app_package else all_lines

        matched = []
        for line in lines:
            for pattern in CRASH_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    matched.append(line)
                    break

        return CrashReport(
            crashed=len(matched) > 0,
            matched_lines=matched,
            log_type=log_type,
            lines_read=len(all_lines),
            lines_checked=len(lines),
        )

    def assert_no_crash(self, app_package: str | None = None, *, require_logs: bool = True) -> None:
        """
        Падает если в логах есть краш — И если ни одна строка не была проверена.
        Второй случай обязателен: 'get_logs' не поддержан драйвером или фильтр по
        пакету не нашёл ни одной строки — это не «крашей нет», а «мы ничего не
        посмотрели», и без проверки такой шаг всегда зелёный.
        """
        report = self.check_for_crash(app_package=app_package)
        if report.crashed:
            raise AssertionError(report.summary())
        if not require_logs or report.lines_checked > 0:
            return
        if report.lines_read == 0:
            detail = (
                f"0 '{report.log_type}' lines were collected — log collection failed "
                "or is unsupported by this driver"
            )
        else:
            detail = (
                f"{report.lines_read} '{report.log_type}' lines were read but none "
                f"mention app_package={app_package!r}"
            )
        raise AssertionError(
            f"Crash check is vacuous: {detail}. It would have passed having examined "
            "nothing — pass require_logs=False only if you accept that."
        )

    def find_errors(self, log_type: str = "logcat", level: str = "ERROR") -> list[str]:
        """Возвращает строки логов заданного уровня — для расследования не-краш проблем."""
        entries = self.get_logs(log_type)
        return [
            e.get("message", "")
            for e in entries
            if str(e.get("level", "")).upper() == level.upper()
        ]
