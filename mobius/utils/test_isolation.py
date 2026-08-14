"""
Test isolation — сброс состояния приложения между тестами.

Главная причина flaky mobile тестов в реальных командах: тест 1 логинится,
тест 2 видит уже залогиненного пользователя и падает. Без явной стратегии
изоляции тесты зависят от порядка выполнения — классический признак
suite, который "работает локально, но падает на CI".

TestIsolationHelper инкапсулирует четыре стратегии из ResetStrategy enum,
выбор зависит от trade-off скорость/гарантия изоляции:

  TERMINATE: 50-200ms. Рекомендуется для большинства тестов.
  FULL_RESET: 5-30s. Только когда нужна гарантированная чистая установка.
"""

from __future__ import annotations

from typing import Any

from mobius.driver.capabilities import ResetStrategy
from mobius.logging_config import get_logger

logger = get_logger(__name__)


class AppResetHelper:
    """
    Применяет стратегию изоляции к приложению перед/после теста.

    Использование в conftest.py:
        @pytest.fixture(autouse=True)
        def reset_app(driver, app_package):
            isolation = AppResetHelper(driver, app_package)
            isolation.reset(ResetStrategy.TERMINATE)
            yield
            # опционально: cleanup после теста
    """

    def __init__(self, driver: Any, app_package: str) -> None:
        self._driver = driver
        self._package = app_package

    def reset(self, strategy: ResetStrategy = ResetStrategy.TERMINATE) -> bool:
        """
        Сбрасывает состояние приложения выбранной стратегией.
        Возвращает True если операция выполнена, False если не поддерживается.
        """
        if strategy == ResetStrategy.NONE:
            logger.debug("reset: strategy=NONE, skipping")
            return True
        elif strategy == ResetStrategy.TERMINATE:
            return self._terminate_and_relaunch()
        elif strategy == ResetStrategy.FULL_RESET:
            return self._full_reset()
        elif strategy == ResetStrategy.NO_RESET:
            logger.debug("reset: strategy=NO_RESET — noReset set in capabilities")
            return True
        return False

    def _terminate_and_relaunch(self) -> bool:
        try:
            self._driver.terminate_app(self._package)
        except Exception as e:
            logger.debug("terminate_app('%s'): %s (may not be running)", self._package, e)
        try:
            self._driver.activate_app(self._package)
            logger.debug("reset TERMINATE: '%s' relaunched", self._package)
            return True
        except Exception as e:
            logger.warning("reset TERMINATE: activate_app('%s') failed: %s", self._package, e)
            return False

    def _full_reset(self) -> bool:
        try:
            self._driver.remove_app(self._package)
        except Exception as e:
            logger.warning("reset FULL_RESET: remove_app failed: %s", e)
        try:
            app_path = self._driver.capabilities.get("appium:app", "")
            if not app_path:
                logger.warning("reset FULL_RESET: no appium:app in capabilities, can't reinstall")
                return False
            self._driver.install_app(app_path)
            self._driver.activate_app(self._package)
            logger.debug("reset FULL_RESET: '%s' reinstalled and relaunched", self._package)
            return True
        except Exception as e:
            logger.warning("reset FULL_RESET: install/activate failed: %s", e)
            return False

    def clear_app_data(self) -> bool:
        """
        Android-only: очищает данные приложения (аналог 'Настройки →
        Приложения → Очистить данные') без переустановки.
        Быстрее FULL_RESET когда нужно только сбросить user data.
        """
        try:
            self._driver.execute_script(
                "mobile: shell",
                {"command": "pm", "args": ["clear", self._package]},
            )
            self._driver.activate_app(self._package)
            logger.debug("clear_app_data: '%s' data cleared", self._package)
            return True
        except Exception as e:
            logger.warning("clear_app_data('%s') failed: %s", self._package, e)
            return False
