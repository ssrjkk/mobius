"""
iOS smoke тесты — Sauce Labs Demo App iOS.

⚠️ ЧЕСТНОЕ ПРЕДУПРЕЖДЕНИЕ (обнаружено при аудите):
Референсный SUT всего example-слоя (my-demo-app-rn) архивирован Sauce Labs
8 мая 2024. Цепочка deprecation реальная:
  sample-app-mobile (архивирован) → my-demo-app-rn (архивирован) →
  my-demo-app-android / my-demo-app-ios (актуальные, поддерживаются)
Актуальный нативный iOS демо-app: https://github.com/saucelabs/my-demo-app-ios
(последний релиз проверен: v2.2.2). ВАЖНО: bundle ID менялся между версиями
этого приложения (com.saucelabs.mydemoapp.ios → com.saucelabs.mydemo.app.ios)
— если мигрируешь на него, проверь актуальный bundle ID перед использованием.

Утверждение "labels совпадают между Android/iOS потому что разработчики
специально сохранили одинаковые accessibility identifiers" НЕ было
верифицировано против реального кода — это правдоподобное предположение
(оба приложения используют testProperties/i18n паттерн), но не подтверждённый
факт. Не используй эти локаторы в реальном проекте без проверки на
актуальном билде через Appium Inspector.

Требует: macOS host + Xcode + iOS Simulator, недоступно в Linux CI.
Запуск локально на Mac:
    MOBILE_PLATFORM=iOS pytest tests/ui/test_ios_smoke.py -m ios -v
"""

from __future__ import annotations

import allure
import pytest

from mobius.screens.home_screen import HomeScreen
from mobius.screens.login_screen import LoginScreen

VALID_USER = "bod@example.com"
VALID_PASS = "10203040"


@allure.feature("Authentication - iOS")
@pytest.mark.ui
@pytest.mark.ios
@pytest.mark.smoke
class TestIOSLoginSmoke:
    """
    iOS smoke suite — тот же Screen Object работает для обеих платформ,
    так как Sauce Labs Demo App использует единые accessibility identifiers.
    Appium сам маршрутизирует ACCESSIBILITY_ID через XCUITest driver на iOS.
    """

    @allure.title("[iOS] Login screen opens on app launch")
    def test_ios_login_screen_opens(self, login_screen: LoginScreen) -> None:
        assert login_screen.is_open

    @allure.title("[iOS] Successful login navigates to home")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_ios_login_valid_credentials(
        self, login_screen: LoginScreen, home_screen: HomeScreen
    ) -> None:
        login_screen.login(VALID_USER, VALID_PASS)
        assert home_screen.is_open

    @allure.title("[iOS] Wrong password shows error")
    def test_ios_login_wrong_password(self, login_screen: LoginScreen) -> None:
        login_screen.login(VALID_USER, "wrong")
        assert login_screen.is_error_shown()

    @allure.title("[iOS] Catalog loads after login")
    def test_ios_catalog_loads(self, login_screen: LoginScreen, home_screen: HomeScreen) -> None:
        login_screen.login(VALID_USER, VALID_PASS)
        assert home_screen.is_open
        assert home_screen.get_product_count() > 0
