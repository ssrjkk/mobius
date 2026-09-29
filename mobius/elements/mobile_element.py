"""MobileElement — обёртка над WebElement с retry, устраняет StaleElement."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mobius.logging_config import get_logger
from mobius.types import Locator
from mobius.utils.driver_health import rethrow_if_driver_dead

logger = get_logger(__name__)

T = TypeVar("T")

_ATTEMPTS = 3
_RETRY_DELAY = 0.3


class MobileElement:
    """Умный wrapper вокруг WebElement. Авто-перенаходит при StaleElement."""

    def __init__(self, driver: Any, locator: Locator, timeout: int = 10) -> None:
        self._driver = driver
        self._locator = locator
        self._timeout = timeout

    def _find(self, condition: Callable[[Any], Any] | None = None) -> Any:
        """Локатор → элемент. По умолчанию ждём присутствия, а не отрисовки."""
        ec = EC.presence_of_element_located(self._locator) if condition is None else condition
        return WebDriverWait(self._driver, self._timeout).until(ec)

    def _retry(
        self,
        action: Callable[[Any], T],
        condition: Callable[[Any], Any] | None = None,
    ) -> T:
        """
        Повторяем ТОЛЬКО при StaleElementReferenceException: локатор всё ещё
        верный, протухла лишь ссылка на узел. Другие ошибки значимы сами по
        себе — маскировать или ретраить их нельзя.
        """
        attempts_left = _ATTEMPTS
        while True:
            try:
                return action(self._find(condition))
            except StaleElementReferenceException:
                attempts_left -= 1
                if attempts_left == 0:
                    raise
                time.sleep(_RETRY_DELAY)

    def click(self) -> None:
        self._retry(lambda elem: elem.click())

    def send_keys(self, *value: str) -> None:
        self._retry(lambda elem: elem.send_keys(*value))

    def clear(self) -> None:
        self._retry(lambda elem: elem.clear())

    def clear_and_type(self, text: str) -> None:
        self.clear()
        self.send_keys(text)

    @property
    def text(self) -> str:
        """`.text` у Selenium WebElement — атрибут, не метод. Читаем через getattr напрямую."""
        value = self._retry(lambda elem: elem.text)
        return "" if value is None else str(value)

    @property
    def is_displayed(self) -> bool:
        """
        Ждём ВИДИМОСТИ, а не присутствия: presence-подход возвращал True для
        элемента в скрытом контейнере. Негативный ответ («не отображается»)
        допустим только для штатных случаев отсутствия элемента.
        """
        try:
            visible = EC.visibility_of_element_located(self._locator)
            return bool(self._retry(lambda elem: elem.is_displayed(), visible))
        except Exception as e:
            rethrow_if_driver_dead(e)
            # DEBUG: элемент отсутствует на экране — это ВАЛИДНЫЙ ответ
            # "не отображается", не ошибка. WARNING здесь завалил бы логи
            # на любой обычной проверке видимости.
            logger.debug("is_displayed: element not found, treating as not displayed: %s", e)
            return False

    @property
    def is_enabled(self) -> bool:
        try:
            return bool(self._retry(lambda elem: elem.is_enabled()))
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.debug("is_enabled: element not found, treating as not enabled: %s", e)
            return False

    def get_attribute(self, name: str) -> str | None:
        value = self._retry(lambda elem: elem.get_attribute(name))
        return None if value is None else str(value)

    def __repr__(self) -> str:
        return f"MobileElement(locator={self._locator})"
