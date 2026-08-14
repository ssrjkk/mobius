"""
Диагностика окружения — реальные проверки, не декоративные.

Отделено от cli.py намеренно: run_diagnostics() возвращает структурированный
список CheckResult, который можно unit-тестировать (моками shutil.which /
subprocess) без реального запуска CLI процесса.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess  # nosec B404 — используется только для adb version (см. check_adb)
import sys
from dataclasses import dataclass
from enum import Enum

from mobius.driver.appium_driver import is_appium_available
from mobius.logging_config import get_logger

logger = get_logger(__name__)


class Status(str, Enum):
    OK = "ok"
    WARNING = "warning"
    MISSING = "missing"
    NOT_APPLICABLE = "n/a"


@dataclass
class CheckResult:
    name: str
    status: Status
    detail: str

    @property
    def is_blocking(self) -> bool:
        """MISSING на обязательном компоненте — блокирует запуск UI тестов."""
        return self.status == Status.MISSING


def check_python_version() -> CheckResult:
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 12):
        return CheckResult("Python version", Status.OK, f"{major}.{minor}.{sys.version_info[2]}")
    return CheckResult(
        "Python version",
        Status.WARNING,
        f"{major}.{minor} — mobius requires >=3.12, some features may not work",
    )


def check_mobius_version() -> CheckResult:
    try:
        import mobius

        return CheckResult("mobius package", Status.OK, mobius.__version__)
    except Exception as e:  # pragma: no cover — self-import, effectively unreachable
        return CheckResult("mobius package", Status.MISSING, str(e))


def check_core_dependencies() -> CheckResult:
    missing = []
    for module_name in ("appium", "selenium", "allure", "PIL", "yaml", "requests"):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    if not missing:
        return CheckResult("Core dependencies", Status.OK, "all importable")
    return CheckResult(
        "Core dependencies",
        Status.MISSING,
        f"missing: {', '.join(missing)} — run: pip install mobius",
    )


def check_appium_server(url: str = "http://localhost:4723") -> CheckResult:
    if is_appium_available(url):
        return CheckResult("Appium server", Status.OK, f"reachable at {url}")
    return CheckResult(
        "Appium server",
        Status.WARNING,
        f"not reachable at {url} — UI tests will auto-skip. Start with: appium --base-path /wd/hub",
    )


def check_adb() -> CheckResult:
    adb_path = shutil.which("adb")
    if not adb_path:
        return CheckResult(
            "adb (Android Debug Bridge)",
            Status.MISSING,
            "not on PATH — required for Android UI tests. Install Android SDK Platform-Tools.",
        )
    try:
        # nosec B603: adb_path приходит ИСКЛЮЧИТЕЛЬНО из shutil.which("adb")
        # выше — это либо None (обработано раньше), либо путь к бинарнику,
        # найденному по литеральному имени "adb" в системном PATH. Не
        # пользовательский ввод, не сетевые данные. shell=True не используется
        # (аргументы передаются списком) — инъекция через shell невозможна.
        result = subprocess.run(  # nosec B603
            [adb_path, "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else "unknown version"
        return CheckResult("adb (Android Debug Bridge)", Status.OK, f"{adb_path} — {first_line}")
    except Exception as e:
        return CheckResult(
            "adb (Android Debug Bridge)",
            Status.WARNING,
            f"found at {adb_path} but 'adb version' failed: {e}",
        )


def check_ios_simctl() -> CheckResult:
    if platform.system() != "Darwin":
        return CheckResult(
            "iOS Simulator (simctl)",
            Status.NOT_APPLICABLE,
            f"only relevant on macOS (current OS: {platform.system()})",
        )
    simctl_path = shutil.which("xcrun")
    if not simctl_path:
        return CheckResult(
            "iOS Simulator (simctl)",
            Status.MISSING,
            "xcrun not found — install Xcode Command Line Tools",
        )
    return CheckResult("iOS Simulator (simctl)", Status.OK, f"{simctl_path}")


def check_env_vars() -> list[CheckResult]:
    optional_vars = ["APP_PATH", "APP_PACKAGE", "DEVICE_UDID", "DEVICE_NAME"]
    results = []
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            results.append(CheckResult(f"env {var}", Status.OK, value))
        else:
            results.append(CheckResult(f"env {var}", Status.WARNING, "not set"))
    return results


def run_diagnostics(appium_url: str = "http://localhost:4723") -> list[CheckResult]:
    """
    Полный набор проверок окружения. Не падает ни на одной проверке —
    каждая обёрнута в защиту, результат всегда список CheckResult.
    """
    return [
        check_python_version(),
        check_mobius_version(),
        check_core_dependencies(),
        check_appium_server(appium_url),
        check_adb(),
        check_ios_simctl(),
        *check_env_vars(),
    ]


def has_blocking_issues(results: list[CheckResult]) -> bool:
    return any(r.is_blocking for r in results)
