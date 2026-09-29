"""
Регресс-тесты на находки аудита release-ветки.

1. `BaseScreen(timeout=N)` должен доводить N до ожидания элемента.
2. Текст поиска не может ломать локатор: ни кавычка, ни `]`, ни перевод
   строки не должны «вылезать» из строкового литерала в код выражения.
3. Предикаты MobileElement не имеют права превращать мёртвый драйвер в
   «элемента нет» (false-green).

Моки ровно на границе I/O — объекте WebDriver; WebDriverWait, expected
conditions и сам Screen Object работают по-настоящему.
"""

from __future__ import annotations

import re
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchElementException,
    SessionNotCreatedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from mobius.elements.mobile_element import MobileElement
from mobius.screens.login_screen import LoginScreen
from mobius.types import Locator

UIA_SELECTOR_SKELETON = (
    "new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector().text())"
)

# Каждый вариант раньше либо ломал синтаксис селектора, либо давал
# инъекцию лишнего предиката.
NASTY_TEXTS = [
    "Add To Cart",
    "it's",
    'say "hi"',
    "список] element",
    'a"] or @label="b',
    "both ' and \" ]",
    "back\\slash",
    'x")) .text("y',
]


def drv() -> MagicMock:
    d = MagicMock()
    d.get_window_size.return_value = {"width": 1080, "height": 2400}
    return d


# Инфраструктурный сбой, а не «элемента нет»: любое из этих исключений
# должно дойти до теста, а не превратиться в спокойный ответ False.
DEAD_DRIVER_ERRORS: list[Exception] = [
    InvalidSessionIdException("invalid session id 'abc'"),
    SessionNotCreatedException("Unable to create a new session"),
    WebDriverException(
        "HTTPConnectionPool(host='127.0.0.1', port=4723): Max retries exceeded with url: /session"
    ),
    WebDriverException(
        "Message: ('Connection aborted.', RemoteDisconnected('Remote end closed "
        "connection without response'))"
    ),
    ConnectionRefusedError(10061, "target machine refused"),
]


def visible_element() -> MagicMock:
    """WebElement-заглушка: visible+enabled, чтобы waits экрана проходили дальше."""
    e = MagicMock()
    e.text = "текст элемента"
    e.is_displayed.return_value = True
    e.is_enabled.return_value = True
    return e


def _scan_literals(expr: str, *, quotes: str, escapes: bool) -> tuple[list[str], str]:
    """
    Разбирает выражение на строковые литералы и «код» вокруг них.

    Незакрытый литерал — это уже битый локатор, поэтому падаем с
    AssertionError, а не возвращает частичный результат.
    """
    literals: list[str] = []
    code: list[str] = []
    current: list[str] | None = None
    quote = ""
    i = 0
    while i < len(expr):
        char = expr[i]
        if current is None:
            if char in quotes:
                current, quote = [], char
            else:
                code.append(char)
            i += 1
            continue
        if escapes and char == "\\" and i + 1 < len(expr):
            current.append(expr[i + 1])
            i += 2
            continue
        if char == quote:
            literals.append("".join(current))
            current = None
        else:
            current.append(char)
        i += 1
    if current is not None:
        raise AssertionError(f"незакрытый строковый литерал: {expr!r}")
    return literals, "".join(code)


def _assert_balanced(code: str, expr: str) -> None:
    closing = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for char in code:
        if char in "([{":
            stack.append(char)
        elif char in closing:
            assert stack and stack.pop() == closing[char], f"разбалансированы скобки: {expr!r}"
    assert not stack, f"незакрытые скобки: {expr!r}"


def assert_xpath_well_formed(expr: str, text: str) -> None:
    """Каркас XPath остался шаблоном BaseScreen, а текст целиком лёг в литералы."""
    literals, code = _scan_literals(expr, quotes="\"'", escapes=False)
    _assert_balanced(code, expr)
    assert code.count("@text=") == 1, f"текст добавил предикат @text: {expr!r}"
    assert code.count("@label=") == 1, f"текст добавил предикат @label: {expr!r}"
    assert re.sub(r"concat\((?:, )*\)", "", code) == "//*[@text= or @label=]", expr
    assert len(literals) % 2 == 0, f"нечётное число литералов: {expr!r}"
    half = len(literals) // 2
    assert literals[:half] == literals[half:], f"@text и @label разошлись: {expr!r}"
    assert "".join(literals[:half]) == text, f"текст не восстановился из литералов: {expr!r}"


def assert_uiautomator_well_formed(expr: str, text: str) -> None:
    literals, code = _scan_literals(expr, quotes='"', escapes=True)
    _assert_balanced(code, expr)
    assert code == UIA_SELECTOR_SKELETON, expr
    assert literals == [text], f"round-trip текста сломался: {expr!r} -> {literals!r}"


@pytest.mark.unit
class TestScreenTimeoutReachesElementWait:
    """BaseScreen.find() обязан передавать таймаут экрана в MobileElement."""

    MISSING: Locator = (AppiumBy.ACCESSIBILITY_ID, "нет такого элемента")

    @staticmethod
    def _driver_that_breaks_after(found_before_failure: int) -> MagicMock:
        """N успешных поисков (нужны wait-ам экрана), дальше элемент исчезает."""
        d = drv()
        state = {"calls": 0}

        def find_element(*args: Any, **kwargs: Any) -> Any:
            state["calls"] += 1
            if state["calls"] <= found_before_failure:
                return visible_element()
            raise NoSuchElementException("элемента нет")

        d.find_element.side_effect = find_element
        return d

    @pytest.mark.parametrize(
        ("operation", "extra_args", "found_before_failure"),
        [
            ("get_text", (), 0),
            ("tap", (), 1),
            ("type_text", ("текст",), 1),
        ],
    )
    def test_waits_only_as_long_as_screen_says(
        self, operation: str, extra_args: tuple[Any, ...], found_before_failure: int
    ) -> None:
        d = self._driver_that_breaks_after(found_before_failure)
        screen = LoginScreen(d, timeout=1)

        started = time.monotonic()
        with pytest.raises(TimeoutException):
            getattr(screen, operation)(self.MISSING, *extra_args)
        elapsed = time.monotonic() - started

        # timeout=1 у экрана + timeout=1 у элемента. Дефолтные 10 секунд
        # означают что настройка экрана снова потерялась по дороге.
        assert elapsed < 4, f"{operation} ждал {elapsed:.1f}s вместо настроенных 2s"
        assert d.find_element.call_count >= 2, f"{operation} не перезапросил драйвер"

    def test_is_displayed_uses_screen_timeout(self) -> None:
        d = drv()
        d.find_element.side_effect = NoSuchElementException("элемента нет")
        screen = LoginScreen(d, timeout=1)

        started = time.monotonic()
        assert screen.find(self.MISSING).is_displayed is False
        assert time.monotonic() - started < 4

    def test_default_timeout_still_ten(self) -> None:
        """Обратная совместимость публичной сигнатуры: таймаут по умолчанию не поехал."""
        element = MobileElement(drv(), ("id", "x"))
        assert element._timeout == 10
        assert LoginScreen(drv())._timeout == 10


@pytest.mark.unit
class TestLocatorInjection:
    """Произвольный текст (из фикстуры или с устройства) не ломает локатор."""

    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_find_by_text_builds_valid_xpath(self, text: str) -> None:
        d = drv()
        LoginScreen(d).find_by_text(text)

        by, xpath = d.find_element.call_args.args
        assert by == AppiumBy.XPATH
        assert_xpath_well_formed(xpath, text)

    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_scroll_to_text_builds_valid_uiautomator_selector(self, text: str) -> None:
        d = drv()
        LoginScreen(d).scroll_to_text(text)

        by, expression = d.find_element.call_args.args
        assert by == AppiumBy.ANDROID_UIAUTOMATOR
        assert_uiautomator_well_formed(expression, text)

    def test_plain_text_is_still_quoted_the_simple_way(self) -> None:
        """Без кавычек в тексте не нужен concat — не усложняем селектор зря."""
        d = drv()
        LoginScreen(d).find_by_text("Login")
        _, xpath = d.find_element.call_args.args
        assert xpath == "//*[@text='Login' or @label='Login']"

    def test_both_quotes_use_concat(self) -> None:
        d = drv()
        LoginScreen(d).find_by_text('it\'s "ok"')
        _, xpath = d.find_element.call_args.args
        assert "concat(" in xpath
        assert_xpath_well_formed(xpath, 'it\'s "ok"')


@pytest.mark.unit
class TestNoFalseGreenOnDeadDriver:
    """Мёртвая сессия/соединение — это падение теста, а не «элемента нет»."""

    @pytest.mark.parametrize("error", DEAD_DRIVER_ERRORS)
    def test_is_displayed_propagates_fatal_error(self, error: Exception) -> None:
        d = drv()
        d.find_element.side_effect = error
        with pytest.raises(type(error)):
            _ = MobileElement(d, ("id", "btn"), timeout=1).is_displayed

    @pytest.mark.parametrize("error", DEAD_DRIVER_ERRORS)
    def test_is_enabled_propagates_fatal_error(self, error: Exception) -> None:
        d = drv()
        d.find_element.side_effect = error
        with pytest.raises(type(error)):
            _ = MobileElement(d, ("id", "btn"), timeout=1).is_enabled

    def test_absent_element_is_still_a_calm_false(self) -> None:
        """Штатный негативный ответ никто не отменял — иначе тесты взводятся."""
        d = drv()
        d.find_element.side_effect = NoSuchElementException("элемента нет")
        element = MobileElement(d, ("id", "btn"), timeout=1)
        assert element.is_displayed is False
        assert element.is_enabled is False

    def test_is_displayed_waits_for_visibility_not_presence(self) -> None:
        """Присутствующий, но не отрисованный элемент — False, и ждём именно видимости."""
        hidden = MagicMock()
        hidden.is_displayed.return_value = False
        d = drv()
        d.find_element.return_value = hidden

        element = MobileElement(d, ("id", "btn"), timeout=1)
        assert element.is_displayed is False
        assert d.find_element.call_count >= 2, "не дожидались видимости, только присутствие"

    def test_visible_element_is_displayed_immediately(self) -> None:
        shown = MagicMock()
        shown.is_displayed.return_value = True
        d = drv()
        d.find_element.return_value = shown

        assert MobileElement(d, ("id", "btn"), timeout=1).is_displayed is True
        assert d.find_element.call_count == 1

    def test_stale_during_visibility_check_re_finds_element(self) -> None:
        """Протухший узел — перенаходим по локатору, а не отвечаем «не отображается»."""
        element = MagicMock()
        element.is_displayed.side_effect = [
            True,
            StaleElementReferenceException("stale"),
            True,
            True,
        ]
        d = drv()
        d.find_element.return_value = element

        assert MobileElement(d, ("id", "btn"), timeout=1).is_displayed is True
        assert d.find_element.call_count == 2


@pytest.mark.unit
class TestScreenPresencePredicate:
    """`BaseScreen.is_element_present` — тот же договор: сбой ≠ «элемент не найден»."""

    MISSING: Locator = (AppiumBy.ID, "com.app:id/missing")

    @pytest.mark.parametrize("error", DEAD_DRIVER_ERRORS)
    def test_dead_driver_propagates_instead_of_returning_false(self, error: Exception) -> None:
        d = drv()
        d.find_element.side_effect = error
        screen = LoginScreen(d, timeout=1)

        with pytest.raises(type(error)):
            screen.is_element_present(self.MISSING, timeout=1)

    def test_absent_element_is_a_calm_false_after_the_wait(self) -> None:
        d = drv()
        d.find_element.side_effect = NoSuchElementException("элемента нет")

        assert LoginScreen(d, timeout=1).is_element_present(self.MISSING, timeout=1) is False
        assert d.find_element.call_count >= 2

    def test_present_element_returns_the_node_found(self) -> None:
        d = drv()
        d.find_element.return_value = visible_element()

        assert LoginScreen(d, timeout=1).is_element_present(self.MISSING, timeout=1) is True
        d.find_element.assert_called_once_with(AppiumBy.ID, "com.app:id/missing")
