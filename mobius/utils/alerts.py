"""
System alert / native dialog handling — универсально для любого приложения.

Permission prompts, "App wants to send notifications", geolocation запросы —
все они рендерятся ОС, а не приложением. Один и тот же handler работает
на любом SUT.
"""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class SystemAlertHandler:
    """Обрабатывает нативные системные диалоги — независимо от SUT."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def is_present(self) -> bool:
        try:
            _ = self._driver.switch_to.alert.text
            return True
        except Exception:
            logger.debug("is_present: no alert currently displayed")
            return False

    def accept(self) -> None:
        """Принять alert (OK / Allow)."""
        try:
            self._driver.switch_to.alert.accept()
        except Exception as e1:
            logger.debug(
                "accept: Selenium alert.accept() failed (%s), trying mobile: acceptAlert",
                e1,
            )
            try:
                self._driver.execute_script("mobile: acceptAlert")
            except Exception as e2:
                logger.warning("accept: both alert.accept() and mobile: acceptAlert failed: %s", e2)

    def dismiss(self) -> None:
        """Отклонить alert (Cancel / Deny)."""
        try:
            self._driver.switch_to.alert.dismiss()
        except Exception as e1:
            logger.debug(
                "dismiss: Selenium alert.dismiss() failed (%s), trying mobile: dismissAlert",
                e1,
            )
            try:
                self._driver.execute_script("mobile: dismissAlert")
            except Exception as e2:
                logger.warning(
                    "dismiss: both alert.dismiss() and mobile: dismissAlert failed: %s",
                    e2,
                )

    def get_text(self) -> str:
        try:
            return str(self._driver.switch_to.alert.text)
        except Exception:
            logger.debug("get_text: no alert present to read text from")
            return ""

    def accept_if_present(self) -> bool:
        """Принимает alert если он есть. Возвращает True если что-то обработано."""
        if self.is_present():
            self.accept()
            return True
        return False

    def dismiss_if_present(self) -> bool:
        """Отклоняет alert если он есть. Возвращает True если что-то обработано."""
        if self.is_present():
            self.dismiss()
            return True
        return False
