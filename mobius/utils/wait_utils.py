"""Wait utilities — explicit waits для мобильных элементов."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mobius.logging_config import get_logger
from mobius.types import Locator

logger = get_logger(__name__)

T = TypeVar("T")


class WaitUtils:
    def __init__(self, driver: Any, default_timeout: int = 10) -> None:
        self._driver = driver
        self._timeout = default_timeout

    def wait_for_element_visible(self, locator: Locator, timeout: int | None = None) -> Any:
        return WebDriverWait(self._driver, timeout or self._timeout).until(
            EC.visibility_of_element_located(locator)
        )

    def wait_for_element_clickable(self, locator: Locator, timeout: int | None = None) -> Any:
        return WebDriverWait(self._driver, timeout or self._timeout).until(
            EC.element_to_be_clickable(locator)
        )

    def wait_for_element_invisible(self, locator: Locator, timeout: int | None = None) -> bool:
        result = WebDriverWait(self._driver, timeout or self._timeout).until(
            EC.invisibility_of_element_located(locator)
        )
        return bool(result)

    def wait_for_text(self, locator: Locator, text: str, timeout: int | None = None) -> Any:
        return WebDriverWait(self._driver, timeout or self._timeout).until(
            EC.text_to_be_present_in_element(locator, text)
        )

    def wait_for_condition(
        self,
        condition: Callable[[], T],
        timeout: int | None = None,
        poll_frequency: float = 0.5,
        ignored_exceptions: tuple[type[Exception], ...] = (
            NoSuchElementException,
            StaleElementReferenceException,
        ),
    ) -> T:
        t = timeout or self._timeout
        end_time = time.time() + t
        last_exc: Exception | None = None
        while time.time() < end_time:
            try:
                result = condition()
                if result:
                    return result
            except ignored_exceptions as e:
                last_exc = e
            time.sleep(poll_frequency)
        if last_exc:
            raise last_exc
        raise TimeoutError(f"Condition not met within {t}s")

    def wait_for_loading_gone(self, loading_locator: Locator, timeout: int = 30) -> None:
        try:
            self.wait_for_element_invisible(loading_locator, timeout=timeout)
        except Exception as e:
            # DEBUG: loader мог вообще не появиться на этом прогоне — норма.
            logger.debug("wait_for_loading_gone(%s): %s", loading_locator, e)


class RetryDecorator:
    """Декоратор для повтора нестабильных операций с мобильным UI."""

    @staticmethod
    def retry(
        times: int = 3,
        delay: float = 1.0,
        exceptions: tuple[type[Exception], ...] = (
            StaleElementReferenceException,
            ElementNotInteractableException,
        ),
    ) -> Callable[..., Any]:
        if times < 1:
            raise ValueError(f"RetryDecorator.retry(times={times}) — times must be >= 1")

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Exception | None = None
                for attempt in range(times):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exc = e
                        if attempt < times - 1:
                            time.sleep(delay)
                assert last_exc is not None  # гарантировано циклом выше при times >= 1
                raise last_exc

            return wrapper

        return decorator
