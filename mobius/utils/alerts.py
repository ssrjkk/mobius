"""
System alert / native dialog handling — универсально для любого приложения.

Permission prompts, "App wants to send notifications", geolocation запросы —
все они рендерятся ОС, а не приложением. Один и тот же handler работает
на любом SUT.
"""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger
from mobius.utils.driver_health import rethrow_if_driver_dead

logger = get_logger(__name__)


class SystemAlertHandler:
    """Обрабатывает нативные системные диалоги — независимо от SUT."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def is_present(self) -> bool:
        try:
            _ = self._driver.switch_to.alert.text
            return True
        except Exception as e:
            # «Алерта нет» и «драйвера нет» — разные ситуации: иначе потерянная
            # сессия окрасит прогон в зелёный.
            rethrow_if_driver_dead(e)
            logger.debug("is_present: no alert currently displayed")
            return False

    def accept(self) -> bool:
        """Принять alert (OK / Allow). True только если его реально приняли."""
        try:
            self._driver.switch_to.alert.accept()
            return True
        except Exception as e1:
            rethrow_if_driver_dead(e1)
            logger.debug(
                "accept: Selenium alert.accept() failed (%s), trying mobile: acceptAlert",
                e1,
            )
            try:
                self._driver.execute_script("mobile: acceptAlert")
                return True
            except Exception as e2:
                rethrow_if_driver_dead(e2)
                logger.warning("accept: both alert.accept() and mobile: acceptAlert failed: %s", e2)
                return False

    def dismiss(self) -> bool:
        """Отклонить alert (Cancel / Deny). True только если его реально отклонили."""
        try:
            self._driver.switch_to.alert.dismiss()
            return True
        except Exception as e1:
            rethrow_if_driver_dead(e1)
            logger.debug(
                "dismiss: Selenium alert.dismiss() failed (%s), trying mobile: dismissAlert",
                e1,
            )
            try:
                self._driver.execute_script("mobile: dismissAlert")
                return True
            except Exception as e2:
                rethrow_if_driver_dead(e2)
                logger.warning(
                    "dismiss: both alert.dismiss() and mobile: dismissAlert failed: %s",
                    e2,
                )
                return False

    def get_text(self) -> str:
        try:
            text = self._driver.switch_to.alert.text
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.debug("get_text: no alert present to read text from")
            return ""
        if not isinstance(text, str):
            logger.warning(
                "get_text: alert text came back as %s, not a string — treated as no text.",
                type(text).__name__,
            )
            return ""
        return text

    def accept_if_present(self) -> bool:
        """Принимает alert если он есть. Возвращает True только когда alert реально принят."""
        return self.is_present() and self.accept()

    def dismiss_if_present(self) -> bool:
        """Отклоняет alert если он есть. Возвращает True только когда alert реально отклонён."""
        return self.is_present() and self.dismiss()
