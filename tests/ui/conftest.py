"""
UI test conftest — setup для E2E тестов на реальном устройстве/эмуляторе.

Каждый UI тест получает:
  - login_as_valid_user: предварительный логин через fixture
  - auto_reset: AppResetHelper.reset() перед каждым тестом (TERMINATE)
  - screenshot on failure: автоматически через pytest hook в root conftest

Зависит от driver fixture в tests/conftest.py (session-scoped,
auto-skip если Appium недоступен).
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from mobius.driver.capabilities import ResetStrategy
from mobius.utils.test_isolation import AppResetHelper

APP_PACKAGE = os.environ.get("APP_PACKAGE", "com.saucelabs.mydemoapp.rn")
VALID_USER = "bod@example.com"
VALID_PASS = "10203040"


@pytest.fixture(autouse=True)
def auto_reset(driver: Any) -> None:
    """
    Сбрасывает состояние приложения ПЕРЕД каждым UI-тестом (TERMINATE).

    Почему autouse=True: без явного сброса каждый тест зависит от
    финального состояния предыдущего — это главная причина order-dependent
    flaky тестов в mobile CI. Terminate+relaunch занимает ~100ms, что
    приемлемо для изоляции.

    Если конкретный тест нуждается в более чистом состоянии
    (например тест первого запуска после установки):
        def test_onboarding(driver, isolation):
            isolation.reset(ResetStrategy.FULL_RESET)
    """
    helper = AppResetHelper(driver, APP_PACKAGE)
    helper.reset(ResetStrategy.TERMINATE)


@pytest.fixture
def isolation(driver: Any) -> AppResetHelper:
    """
    AppResetHelper для явного управления состоянием внутри теста.
    Использование:
        def test_clean_install(driver, isolation):
            isolation.reset(ResetStrategy.FULL_RESET)
    """
    return AppResetHelper(driver, APP_PACKAGE)


@pytest.fixture
def logged_in(driver: Any) -> Any:
    """
    Fixture: гарантирует что тест начинается с залогиненным пользователем.
    auto_reset (выше) уже перезапустил приложение — делаем логин.

    Возвращает home_screen для использования в тесте.
    """
    from mobius.screens.home_screen import HomeScreen
    from mobius.screens.login_screen import LoginScreen

    login = LoginScreen(driver)
    if login.is_open:
        login.login(VALID_USER, VALID_PASS)

    home = HomeScreen(driver)
    assert home.is_open, "Login fixture failed — home screen not visible after login"
    return home
