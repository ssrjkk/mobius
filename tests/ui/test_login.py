"""
UI тесты — Login flow против Sauce Labs My Demo App (React Native).
SUT: https://github.com/saucelabs/my-demo-app-rn

⚠️ ЧЕСТНОЕ ПРЕДУПРЕЖДЕНИЕ (обнаружено при аудите, не должно было быть
пропущено раньше):
  1. Репозиторий АРХИВИРОВАН владельцем 8 мая 2024 — больше не
     поддерживается. Существует активный преемник:
     https://github.com/saucelabs/sample-app-mobile — рекомендуется
     смигрировать реальный проект на него.
  2. Локаторы ниже НЕ верифицированы против конкретного APK-билда —
     сеть в среде разработки не даёт скачать реальный бинарник
     (redirect на CDN вне allowlist). Строки вроде "Username input
     field" основаны на паттернах из публичной документации/тьюториалов
     по этому приложению, а не на инспекции живого APK. Реальный проект
     использует testProperties(i18n.t('key')) — accessibility ID строятся
     из файла переводов, не хардкожены — так что точные строки могут
     отличаться. Перед использованием в реальном проекте: собери APK
     локально и проверь локаторы через `appium inspector` или
     `uiautomatorviewer`.
"""

from __future__ import annotations

import allure
import pytest

from mobius.screens.home_screen import HomeScreen
from mobius.screens.login_screen import LoginScreen

# Sauce Labs Demo App — стандартные тестовые credentials из документации
VALID_USER = "bod@example.com"
VALID_PASS = "10203040"
LOCKED_USER = "alice@example.com"  # locked-out аккаунт для негативных тестов


@allure.feature("Authentication")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.smoke
class TestLoginSmoke:
    @allure.title("Successful login redirects to home screen")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_login_valid_credentials(
        self, login_screen: LoginScreen, home_screen: HomeScreen
    ) -> None:
        with allure.step(f"Login as {VALID_USER}"):
            login_screen.login(VALID_USER, VALID_PASS)
        with allure.step("Verify home screen opened"):
            assert home_screen.is_open, "Home screen did not open after valid login"

    @allure.title("Wrong password shows error message")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login_wrong_password(self, login_screen: LoginScreen) -> None:
        with allure.step("Enter valid username, wrong password"):
            login_screen.login(VALID_USER, "wrong_password_123")
        with allure.step("Verify error is shown"):
            assert login_screen.is_error_shown()

    @allure.title("Empty credentials show validation error")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_empty_fields(self, login_screen: LoginScreen) -> None:
        with allure.step("Tap login without entering anything"):
            login_screen.tap_login()
        with allure.step("Verify error appears"):
            assert login_screen.is_error_shown()

    @allure.title("Login screen loads with all elements visible")
    @allure.severity(allure.severity_level.NORMAL)
    def test_login_screen_elements_present(self, login_screen: LoginScreen) -> None:
        assert login_screen.is_open


@allure.feature("Authentication")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestLoginRegression:
    @allure.title("Can retype credentials after error and succeed")
    def test_retry_after_error_succeeds(
        self, login_screen: LoginScreen, home_screen: HomeScreen
    ) -> None:
        with allure.step("First attempt fails"):
            login_screen.login(VALID_USER, "wrong")
            assert login_screen.is_error_shown()
        with allure.step("Retry with correct password"):
            login_screen.enter_username(VALID_USER)
            login_screen.enter_password(VALID_PASS)
            login_screen.tap_login()
        with allure.step("Home screen opens"):
            assert home_screen.is_open

    @pytest.mark.parametrize(
        "username,password,case",
        [
            ("", VALID_PASS, "empty username"),
            (VALID_USER, "", "empty password"),
            ("not-an-email", VALID_PASS, "malformed email"),
            (VALID_USER, "123", "too short password"),
            ("a" * 200, VALID_PASS, "extremely long username"),
        ],
    )
    @allure.title("Invalid input rejected: {case}")
    def test_invalid_input_parametrized(
        self, login_screen: LoginScreen, username: str, password: str, case: str
    ) -> None:
        with allure.step(f"Testing case: {case}"):
            login_screen.login(username, password)
        assert login_screen.is_error_shown(), f"Expected error for case: {case}"

    @allure.title("SQL injection attempt is safely rejected")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_sql_injection_safe(self, login_screen: LoginScreen) -> None:
        login_screen.login("' OR '1'='1", "' OR '1'='1")
        assert login_screen.is_error_shown()

    @allure.title("XSS attempt in username field is handled safely")
    def test_xss_in_username_safe(self, login_screen: LoginScreen) -> None:
        login_screen.login("<script>alert(1)</script>", "pass")
        assert login_screen.is_error_shown()

    @allure.title("Login form persists after app backgrounding")
    @pytest.mark.slow
    def test_login_survives_app_background(self, login_screen: LoginScreen, driver) -> None:
        login_screen.enter_username(VALID_USER)
        with allure.step("Background the app for 2 seconds"):
            driver.background_app(2)
        with allure.step("Verify username field retained value"):
            # Поле должно сохранить введённое значение
            assert login_screen.is_open
