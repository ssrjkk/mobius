"""
Unit tests — MobileElement.

Мок только на границе I/O: объекте WebDriver. WebDriverWait, expected
conditions, retry-цикл и сам wrapper работают по-настоящему, поэтому тест
проваливается вместе с кодом, а не вместе с заглушкой.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from mobius.elements.mobile_element import MobileElement
from mobius.types import Locator

LOCATOR: Locator = ("id", "btn")


def web_element() -> MagicMock:
    """WebElement-заглушка: видимый и активный, чтобы предикаты не «жульничали»."""
    element = MagicMock()
    element.is_displayed.return_value = True
    element.is_enabled.return_value = True
    return element


def driver_with(*finds: Any) -> MagicMock:
    """
    WebDriver, который на каждый find_element отдаёт следующий аргумент.

    Один аргумент — стабильный ответ (можно поллить сколько угодно),
    несколько — сценарий, где элемент меняется от поиска к поиску.
    """
    d = MagicMock()
    if len(finds) == 1:
        d.find_element.return_value = finds[0]
    else:
        d.find_element.side_effect = list(finds)
    return d


@pytest.mark.unit
class TestDelegatesToDriver:
    """Каждое действие — настоящий запрос к драйверу по локатору wrapper'а."""

    def test_click_looks_up_the_element_by_locator(self) -> None:
        inner = web_element()
        d = driver_with(inner)

        MobileElement(d, LOCATOR, timeout=1).click()

        d.find_element.assert_called_once_with(*LOCATOR)
        inner.click.assert_called_once_with()

    def test_send_keys_forwards_every_argument(self) -> None:
        inner = web_element()
        d = driver_with(inner)

        MobileElement(d, LOCATOR, timeout=1).send_keys("привет", "!")

        assert d.find_element.call_args_list == [call(*LOCATOR)]
        inner.send_keys.assert_called_once_with("привет", "!")

    def test_clear_touches_only_the_element(self) -> None:
        inner = web_element()
        d = driver_with(inner)

        MobileElement(d, LOCATOR, timeout=1).clear()

        inner.clear.assert_called_once_with()
        inner.send_keys.assert_not_called()

    def test_clear_and_type_clears_before_typing(self) -> None:
        """Порядок observable: сначала clear, потом send_keys, ровно по одному разу."""
        inner = web_element()
        actions: list[str] = []
        inner.clear.side_effect = lambda: actions.append("clear")
        inner.send_keys.side_effect = lambda *values: actions.append(f"send_keys:{values}")

        MobileElement(driver_with(inner), LOCATOR, timeout=1).clear_and_type("text")

        assert actions == ["clear", "send_keys:('text',)"]


@pytest.mark.unit
class TestReadsAttributes:
    def test_text(self) -> None:
        inner = web_element()
        inner.text = "Hello"

        assert MobileElement(driver_with(inner), LOCATOR, timeout=1).text == "Hello"

    def test_text_of_empty_element_is_empty_string(self) -> None:
        """У WebElement `.text` может быть None — наружу уходит пустая строка."""
        inner = web_element()
        inner.text = None

        assert MobileElement(driver_with(inner), LOCATOR, timeout=1).text == ""

    def test_get_attribute(self) -> None:
        inner = web_element()
        inner.get_attribute.return_value = "com.app:id/btn"

        wrapper = MobileElement(driver_with(inner), LOCATOR, timeout=1)
        assert wrapper.get_attribute("resource-id") == "com.app:id/btn"
        inner.get_attribute.assert_called_once_with("resource-id")

    def test_get_attribute_returns_none_when_absent(self) -> None:
        inner = web_element()
        inner.get_attribute.return_value = None

        wrapper = MobileElement(driver_with(inner), LOCATOR, timeout=1)
        assert wrapper.get_attribute("content-desc") is None

    def test_repr_shows_the_locator(self) -> None:
        wrapper = MobileElement(MagicMock(), ("accessibility id", "Login"))

        assert repr(wrapper) == "MobileElement(locator=('accessibility id', 'Login'))"


@pytest.mark.unit
class TestStaleElementRetry:
    """Перенаходим узел по локатору — и только при «протухании»."""

    def test_stale_during_action_reelects_the_element(self) -> None:
        stale, fresh = MagicMock(), web_element()
        stale.click.side_effect = StaleElementReferenceException("stale")
        d = driver_with(stale, fresh)

        MobileElement(d, LOCATOR, timeout=1).click()

        assert d.find_element.call_count == 2
        fresh.click.assert_called_once_with()

    def test_stale_during_lookup_reelects_the_element(self) -> None:
        fresh = web_element()
        d = driver_with(StaleElementReferenceException("stale"), fresh)

        MobileElement(d, LOCATOR, timeout=1).click()

        assert d.find_element.call_count == 2
        fresh.click.assert_called_once_with()

    def test_gives_up_after_three_attempts(self) -> None:
        """Ретраить вечно нельзя: упрямый стейл должен упасть, а не подвиснуть."""
        inner = MagicMock()
        inner.click.side_effect = StaleElementReferenceException("stale")
        d = driver_with(inner)

        with pytest.raises(StaleElementReferenceException):
            MobileElement(d, LOCATOR, timeout=1).click()

        assert inner.click.call_count == 3
        assert d.find_element.call_count == 3

    def test_text_recovers_when_node_stales_on_read(self) -> None:
        class StaleNode:
            """Чтение любого атрибута отсоединённого узла поднимает StaleElement."""

            def __getattr__(self, name: str) -> Any:
                raise StaleElementReferenceException("stale")

        fresh = web_element()
        fresh.text = "Hello"
        d = driver_with(StaleNode(), fresh)

        assert MobileElement(d, LOCATOR, timeout=1).text == "Hello"
        assert d.find_element.call_count == 2

    def test_non_stale_failure_is_not_retried(self) -> None:
        """Чужая ошибка — не стейл: её нельзя проглатывать и нельзя ретраить."""
        inner = MagicMock()
        inner.click.side_effect = NoSuchElementException("не клик")
        d = driver_with(inner)

        with pytest.raises(NoSuchElementException):
            MobileElement(d, LOCATOR, timeout=1).click()

        assert inner.click.call_count == 1
        assert d.find_element.call_count == 1


@pytest.mark.unit
class TestFatalErrorsPropagate:
    def test_dead_session_is_not_a_retry(self) -> None:
        """Перенаходить элемент в мёртвой сессии бессмысленно — падаем сразу."""
        inner = MagicMock()
        inner.click.side_effect = InvalidSessionIdException("invalid session id 'abc'")
        d = driver_with(inner)

        with pytest.raises(InvalidSessionIdException):
            MobileElement(d, LOCATOR, timeout=1).click()

        assert d.find_element.call_count == 1
