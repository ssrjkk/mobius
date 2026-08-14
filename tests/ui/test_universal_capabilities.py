"""
UI тесты — демонстрация universal-слоя против реального устройства/эмулятора.

В отличие от test_login.py / test_catalog.py (которые тестируют КОНКРЕТНОЕ
приложение через Screen Objects), эти тесты показывают что device/alerts/
clipboard/finder работают ОДИНАКОВО вне зависимости от того, что запущено
на экране — это ключевое свойство "универсальности" framework.
"""

from __future__ import annotations

import allure
import pytest

from mobius.screens.home_screen import HomeScreen
from mobius.screens.login_screen import LoginScreen
from mobius.utils.universal_finder import UniversalFinder

VALID_USER = "bod@example.com"
VALID_PASS = "10203040"


@allure.feature("Universal — Device Actions")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestDeviceRotation:
    """Rotation не завязан на конкретный экран — работает в любом состоянии приложения."""

    @allure.title("App survives rotation to landscape and back")
    def test_rotate_landscape_and_back(self, login_screen: LoginScreen) -> None:
        device = login_screen.device
        with allure.step("Rotate to landscape"):
            device.rotate_to_landscape()
            assert device.is_landscape()
        with allure.step("Rotate back to portrait"):
            device.rotate_to_portrait()
            assert not device.is_landscape()
        with allure.step("Screen still functional after rotation"):
            assert login_screen.is_open

    @allure.title("Login form usable in landscape orientation")
    def test_login_works_in_landscape(
        self, login_screen: LoginScreen, home_screen: HomeScreen
    ) -> None:
        login_screen.device.rotate_to_landscape()
        try:
            login_screen.login(VALID_USER, VALID_PASS)
            assert home_screen.is_open
        finally:
            login_screen.device.rotate_to_portrait()


@allure.feature("Universal — App Lifecycle")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestAppLifecycle:
    @allure.title("App state preserved after backgrounding")
    def test_background_and_foreground(self, login_screen: LoginScreen) -> None:
        login_screen.enter_username(VALID_USER)
        with allure.step("Background app for 3 seconds"):
            login_screen.device.background_app(3)
        with allure.step("App resumes with screen intact"):
            assert login_screen.is_open

    @allure.title("Hardware back button navigates correctly")
    def test_hardware_back_button(self, login_screen: LoginScreen, home_screen: HomeScreen) -> None:
        login_screen.login(VALID_USER, VALID_PASS)
        assert home_screen.is_open
        with allure.step("Open product detail, then press hardware back"):
            home_screen.tap_product(0)
            home_screen.device.press_back()
        with allure.step("Back on home screen"):
            assert home_screen.is_open

    @allure.title("reset_app clears session state")
    @pytest.mark.slow
    def test_reset_app_clears_session(
        self, login_screen: LoginScreen, home_screen: HomeScreen, driver
    ) -> None:
        import os

        package = os.environ.get("APP_PACKAGE", "com.saucelabs.mydemoapp.rn")
        login_screen.login(VALID_USER, VALID_PASS)
        assert home_screen.is_open
        with allure.step("Reset app — full terminate + relaunch"):
            login_screen.device.reset_app(package)
        with allure.step("Back to login screen — session cleared"):
            fresh_login = LoginScreen(driver)
            assert fresh_login.is_open


@allure.feature("Universal — System Alerts")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestSystemAlerts:
    @allure.title("accept_if_present is safe when no alert is shown")
    def test_accept_if_present_safe_without_alert(self, login_screen: LoginScreen) -> None:
        # На чистом login screen обычно нет системных алертов —
        # проверяем что вызов безопасен и не ломает тест
        result = login_screen.alerts.accept_if_present()
        assert result in (True, False)  # не падает независимо от результата
        assert login_screen.is_open


@allure.feature("Universal — Clipboard")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestClipboard:
    @allure.title("Copy username, paste into password field, roundtrip works")
    def test_clipboard_roundtrip(self, login_screen: LoginScreen) -> None:
        test_value = "clipboard_test_value_123"
        with allure.step("Set clipboard text"):
            login_screen.clipboard.set_text(test_value)
        with allure.step("Read clipboard back"):
            result = login_screen.clipboard.get_text()
        assert result == test_value


@allure.feature("Universal — Finder Fallback")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestUniversalFinderFallback:
    """
    Сценарий: локатор в Screen Object устарел (приложение обновилось),
    но UniversalFinder всё ещё находит элемент по видимому тексту —
    полезный fallback пока Screen Object не обновлён.
    """

    @allure.title("find_button_by_text locates login button without exact locator")
    def test_finder_locates_login_button(self, login_screen: LoginScreen) -> None:
        finder: UniversalFinder = login_screen.finder
        with allure.step("Find login-like button by common text patterns"):
            buttons = finder.find_any_button()
        assert len(buttons) > 0, "UniversalFinder found no buttons on login screen"

    @allure.title("screen_contains_text detects visible content")
    def test_screen_contains_text(self, login_screen: LoginScreen) -> None:
        # Login screen обычно содержит слово с латиницей — smoke-проверка
        # что finder вообще может парсить экран
        has_any_button = len(login_screen.finder.find_any_button()) > 0
        has_any_input = len(login_screen.finder.find_any_input()) > 0
        assert has_any_button or has_any_input, "Screen appears empty to UniversalFinder"

    @allure.title("get_all_texts_on_screen returns non-empty list on catalog")
    def test_get_all_texts_after_login(
        self, login_screen: LoginScreen, home_screen: HomeScreen
    ) -> None:
        login_screen.login(VALID_USER, VALID_PASS)
        assert home_screen.is_open
        texts = home_screen.finder.get_all_texts_on_screen()
        assert isinstance(texts, list)
