"""
Push notification helper — универсальная работа с системными уведомлениями.
Android-only (open_notifications — Android UiAutomator2 команда).
"""

from __future__ import annotations

from typing import Any

from appium.webdriver.common.appiumby import AppiumBy

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class NotificationHelper:
    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def open_shade(self) -> None:
        """Открывает шторку уведомлений (свайп сверху экрана)."""
        try:
            self._driver.open_notifications()
        except Exception as e:
            logger.warning(
                "open_shade: open_notifications() failed — Android-only "
                "command, check if called on iOS: %s",
                e,
            )

    def get_notifications_text(self) -> list[str]:
        """Открывает шторку и возвращает тексты видимых уведомлений."""
        self.open_shade()
        try:
            elements = self._driver.find_elements(
                AppiumBy.XPATH, "//*[contains(@resource-id,'notification')]"
            )
            return [e.text for e in elements if e.text]
        except Exception as e:
            logger.warning("get_notifications_text: failed to read notification shade: %s", e)
            return []

    def has_notification_containing(self, text: str) -> bool:
        texts = self.get_notifications_text()
        return any(text.lower() in t.lower() for t in texts)

    def close_shade(self) -> None:
        try:
            self._driver.press_keycode(4)  # BACK
        except Exception as e:
            logger.warning("close_shade: press_keycode(BACK) failed: %s", e)
