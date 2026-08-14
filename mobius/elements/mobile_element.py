"""MobileElement — обёртка над WebElement с retry, устраняет StaleElement."""

from __future__ import annotations

import time
from typing import Any

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mobius.logging_config import get_logger
from mobius.types import Locator

logger = get_logger(__name__)


class MobileElement:
    """Умный wrapper вокруг WebElement. Авто-перенаходит при StaleElement."""

    def __init__(self, driver: Any, locator: Locator, timeout: int = 10) -> None:
        self._driver = driver
        self._locator = locator
        self._timeout = timeout

    def _find(self) -> Any:
        return WebDriverWait(self._driver, self._timeout).until(
            EC.presence_of_element_located(self._locator)
        )

    def _safe_action(self, action_name: str, *args: Any, **kwargs: Any) -> Any:
        for attempt in range(3):
            try:
                elem = self._find()
                return getattr(elem, action_name)(*args, **kwargs)
            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                time.sleep(0.3)
        return None  # pragma: no cover

    def click(self) -> None:
        self._safe_action("click")

    def send_keys(self, *value: str) -> None:
        self._safe_action("send_keys", *value)

    def clear(self) -> None:
        self._safe_action("clear")

    def clear_and_type(self, text: str) -> None:
        self.clear()
        self.send_keys(text)

    @property
    def text(self) -> str:
        """`.text` у Selenium WebElement — атрибут, не метод. Читаем через getattr напрямую."""
        for attempt in range(3):
            try:
                elem = self._find()
                return str(elem.text) if elem.text is not None else ""
            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                import time

                time.sleep(0.3)
        return ""  # pragma: no cover

    @property
    def is_displayed(self) -> bool:
        try:
            return bool(self._safe_action("is_displayed"))
        except Exception as e:
            # DEBUG: элемент отсутствует на экране — это ВАЛИДНЫЙ ответ
            # "не отображается", не ошибка. WARNING здесь завалил бы логи
            # на любой обычной проверке видимости.
            logger.debug("is_displayed: element not found, treating as not displayed: %s", e)
            return False

    @property
    def is_enabled(self) -> bool:
        try:
            return bool(self._safe_action("is_enabled"))
        except Exception as e:
            logger.debug("is_enabled: element not found, treating as not enabled: %s", e)
            return False

    def get_attribute(self, name: str) -> str | None:
        result = self._safe_action("get_attribute", name)
        return str(result) if result is not None else None

    def __repr__(self) -> str:
        return f"MobileElement(locator={self._locator})"
