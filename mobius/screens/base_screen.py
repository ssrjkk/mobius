"""BaseScreen — родительский Screen Object для всех экранов (SOM pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mobius.elements.mobile_element import MobileElement
from mobius.logging_config import get_logger
from mobius.types import Locator
from mobius.utils.alerts import SystemAlertHandler
from mobius.utils.clipboard import ClipboardManager
from mobius.utils.device import DeviceActions
from mobius.utils.gestures import Gestures
from mobius.utils.screenshot import ScreenshotUtils
from mobius.utils.universal_finder import UniversalFinder
from mobius.utils.wait_utils import WaitUtils

logger = get_logger(__name__)


class BaseScreen(ABC):
    """
    Базовый класс для всех Screen Objects.

    Использование:
        class LoginScreen(BaseScreen):
            LOCATOR = (AppiumBy.ID, "com.app:id/username")
            def enter_username(self, u: str) -> "LoginScreen":
                self.type_text(self.LOCATOR, u)
                return self  # fluent interface
    """

    def __init__(self, driver: Any, timeout: int = 10) -> None:
        self._driver = driver
        self._timeout = timeout
        self.wait = WaitUtils(driver, default_timeout=timeout)
        self.gestures = Gestures(driver)
        self.screenshot = ScreenshotUtils(driver)
        # Universal — работают одинаково независимо от того, какой SUT
        # тестирует конкретный Screen Object. Доступны на любом экране.
        self.device = DeviceActions(driver)
        self.alerts = SystemAlertHandler(driver)
        self.clipboard = ClipboardManager(driver)
        self.finder = UniversalFinder(driver)

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Проверяем что экран открыт — уникальный элемент присутствует."""
        ...  # pragma: no cover

    def find(self, locator: Locator) -> MobileElement:
        """Возвращает MobileElement — StaleElement-safe wrapper с auto-retry x3."""
        return MobileElement(self._driver, locator)

    def find_all(self, locator: Locator) -> list[Any]:
        return list(self._driver.find_elements(*locator))

    def find_by_text(self, text: str) -> Any:
        return self._driver.find_element(AppiumBy.XPATH, f'//*[@text="{text}" or @label="{text}"]')

    def find_by_id(self, resource_id: str) -> Any:
        return self._driver.find_element(AppiumBy.ID, resource_id)

    def find_by_accessibility(self, label: str) -> Any:
        return self._driver.find_element(AppiumBy.ACCESSIBILITY_ID, label)

    def tap(self, locator: Locator) -> None:
        """Wait-until-clickable, затем click через MobileElement (StaleElement-safe)."""
        self.wait.wait_for_element_clickable(locator)
        MobileElement(self._driver, locator).click()

    def type_text(self, locator: Locator, text: str) -> None:
        """Wait-until-visible, затем clear+send_keys через MobileElement (StaleElement-safe)."""
        self.wait.wait_for_element_visible(locator)
        MobileElement(self._driver, locator).clear_and_type(text)

    def get_text(self, locator: Locator) -> str:
        return MobileElement(self._driver, locator).text

    def is_element_present(self, locator: Locator, timeout: int = 3) -> bool:
        try:
            WebDriverWait(self._driver, timeout).until(EC.presence_of_element_located(locator))
            return True
        except Exception as e:
            # DEBUG: "элемент отсутствует" — это часто ОЖИДАЕМЫЙ результат
            # проверки (например is_error_shown() на happy path). WARNING
            # здесь будет ложным срабатыванием на каждый негативный тест.
            logger.debug("is_element_present(%s): not found within %ss: %s", locator, timeout, e)
            return False

    def scroll_to_text(self, text: str) -> Any:
        """Android UiScrollable — скролл до текста."""
        return self._driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f"new UiScrollable(new UiSelector().scrollable(true))"
            f'.scrollIntoView(new UiSelector().text("{text}"))',
        )

    def hide_keyboard(self) -> None:
        try:
            self._driver.hide_keyboard()
        except Exception as e:
            # DEBUG: клавиатура часто уже скрыта — не ошибка, а норма.
            logger.debug("hide_keyboard: no keyboard visible or driver doesn't support it: %s", e)

    def go_back(self) -> None:
        self._driver.back()

    def attach_screenshot_on_failure(self) -> None:
        self.screenshot.attach_to_allure("Screenshot on failure")
        self.screenshot.attach_page_source("Page source on failure")
