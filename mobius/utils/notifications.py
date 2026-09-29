"""
Push notification helper — универсальная работа с системными уведомлениями.
Android-only (open_notifications — Android UiAutomator2 команда).
"""

from __future__ import annotations

from typing import Any

from appium.webdriver.common.appiumby import AppiumBy

from mobius.logging_config import get_logger
from mobius.utils.driver_health import rethrow_if_driver_dead

logger = get_logger(__name__)

NOTIFICATION_XPATH = "//*[contains(@resource-id,'notification')]"


class NotificationHelper:
    """
    Читает шторку уведомлений.

    Проверки обязаны различать «уведомлений нет» и «мы ничего не прочитали» —
    как в DeviceLogCollector.assert_no_crash. Не открытая шторка это не пустой
    список, а пустое наблюдение: без явной реакции негативный ассерт
    («пуша не пришло») зелёным проходит на устройстве, где не увидели ничего.
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def open_shade(self) -> bool:
        """Открывает шторку уведомлений. True только когда драйвер принял команду."""
        try:
            self._driver.open_notifications()
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning(
                "open_shade: open_notifications() failed — Android-only "
                "command, check if called on iOS: %s",
                e,
            )
            return False

    def get_notifications_text(self) -> list[str]:
        """
        Открывает шторку и возвращает тексты видимых уведомлений.

        Пустой список означает и «уведомлений нет», и «шторку прочитать не
        удалось»: для ассертов используйте has_notification_containing(), который
        эти случаи различает.
        """
        self.open_shade()
        return self._read_texts()

    def has_notification_containing(self, text: str, *, require_shade: bool = True) -> bool:
        """
        True только когда шторка открыта, прочитана, и в ней есть эта подстрока.

        `require_shade` — как `require_logs` в assert_no_crash: False означает
        «считай, что уведомлений нет, если шторку открыть не удалось», и тогда
        проверка опирается на ничего.
        """
        if not text:
            raise ValueError("has_notification_containing: empty text matches every notification")
        if not self.open_shade():
            if require_shade:
                raise AssertionError(
                    "Notification check is vacuous: the shade did not open, so no "
                    "notification was examined — pass require_shade=False only if you "
                    "accept a result built on nothing."
                )
            return False
        needle = text.lower()
        return any(needle in available.lower() for available in self._read_texts())

    def close_shade(self) -> bool:
        """Закрывает шторку (BACK). True только когда нажатие прошло."""
        try:
            self._driver.press_keycode(4)  # BACK
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning("close_shade: press_keycode(BACK) failed: %s", e)
            return False

    def _read_texts(self) -> list[str]:
        try:
            elements = self._driver.find_elements(AppiumBy.XPATH, NOTIFICATION_XPATH)
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning("get_notifications_text: failed to read notification shade: %s", e)
            return []

        texts: list[str] = []
        for element in elements:
            raw = element.text
            if not raw:
                continue
            if not isinstance(raw, str):
                logger.warning(
                    "get_notifications_text: element text came back as %s, not a string — skipped.",
                    type(raw).__name__,
                )
                continue
            texts.append(raw)
        return texts
