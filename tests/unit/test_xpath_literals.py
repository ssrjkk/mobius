"""
Экранирование литералов в локаторах: mobius.utils.xpath и UniversalFinder.

Текст поиска приходит извне (из фикстуры, с экрана устройства, от
пользователя). В XPath 1.0 нет экранирования кавычек, поэтому наивный
f-string с кавычкой в тексте либо ломает выражение, либо добавляет в чужой
локатор лишний предикат: `a"] or @label="b` превращал один поиск в два.

Проверка структурная: разбираем готовое выражение на строковые литералы и
«код» вокруг них. Код обязан совпасть с каркасом билдера — значит текст не
прибавил ни предиката, ни скобок, — а литералы обязаны обратно собраться в
исходный текст.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import InvalidSessionIdException

from mobius.utils.universal_finder import UniversalFinder
from mobius.utils.xpath import uiautomator_literal, xpath_literal

NASTY_TEXTS = [
    "Login",
    "Add To Cart",
    "it's",
    'say "hi"',
    'a"] or @label="b',
    "both ' and \" ]",
    "список] element",
    "back\\slash",
    '")) or (',
    "'",
    '"',
    "'\"",
    "",
    "Русский текст",
]

FIND_BY_TEXT_EXACT = "//*[@text= or @label= or @name= or @value=]"
FIND_BY_TEXT_CONTAINS = (
    "//*[contains(@text,) or contains(@label,) or contains(@name,) or contains(@value,)]"
)
FIND_ALL_BY_TEXT = "//*[contains(@text,) or contains(@label,) or contains(@name,)]"


def xpath_parts(expr: str) -> tuple[list[str], str]:
    """Литералы XPath-выражения и код между ними.

    В XPath 1.0 кавычка не экранируется никогда, поэтому первая же кавычка
    того же типа закрывает литерал — искать концы можно простым сканированием.
    """
    literals: list[str] = []
    code: list[str] = []
    i = 0
    while i < len(expr):
        char = expr[i]
        if char in "\"'":
            end = expr.find(char, i + 1)
            assert end != -1, f"незакрытый строковый литерал в {expr!r}"
            literals.append(expr[i + 1 : end])
            i = end + 1
            continue
        code.append(char)
        i += 1
    return literals, "".join(code)


def _strip_concat(code: str) -> str:
    """concat('a', "'", 'b') теряет литералы и превращается в concat( , , ) → ''."""
    return re.sub(r"concat\((?:, )*\)", "", code)


def assert_xpath_safe(expr: str, text: str, expected_skeleton: str, groups: int) -> None:
    literals, code = xpath_parts(expr)
    assert _strip_concat(code) == expected_skeleton, expr
    assert len(literals) % groups == 0, f"литералов не кратно предикатам: {expr!r}"
    size = len(literals) // groups
    for i in range(groups):
        assert "".join(literals[i * size : (i + 1) * size]) == text, (
            f"round-trip текста сломался: {expr!r}"
        )


@pytest.mark.unit
class TestXpathLiteral:
    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_literal_round_trips(self, text: str) -> None:
        literals, code = xpath_parts(xpath_literal(text))
        assert _strip_concat(code) == "", (
            f"текст вылез за пределы литерала: {xpath_literal(text)!r}"
        )
        assert "".join(literals) == text

    def test_plain_text_uses_single_quotes(self) -> None:
        assert xpath_literal("Login") == "'Login'"

    def test_text_with_single_quote_switches_to_double(self) -> None:
        assert xpath_literal("it's") == '"it\'s"'

    def test_text_with_double_quote_keeps_single(self) -> None:
        assert xpath_literal('say "hi"') == "'say \"hi\"'"

    def test_both_quotes_fall_back_to_concat(self) -> None:
        assert xpath_literal('it\'s "ok"') == "concat('it', \"'\", 's \"ok\"')"

    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_uiautomator_literal_round_trips(self, text: str) -> None:
        expr = uiautomator_literal(text)
        assert expr.startswith('"') and expr.endswith('"'), expr
        body = expr[1:-1]
        unescaped = body.replace("\\\\", "\x00").replace('\\"', '"').replace("\x00", "\\")
        assert unescaped == text


@pytest.mark.unit
class TestUniversalFinderInjection:
    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_find_by_text_exact(self, text: str) -> None:
        d = MagicMock()
        UniversalFinder(d).find_by_text(text, exact=True)
        assert_xpath_safe(d.find_element.call_args.args[1], text, FIND_BY_TEXT_EXACT, groups=4)

    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_find_by_text_contains(self, text: str) -> None:
        d = MagicMock()
        UniversalFinder(d).find_by_text(text)
        assert_xpath_safe(d.find_element.call_args.args[1], text, FIND_BY_TEXT_CONTAINS, groups=4)

    @pytest.mark.parametrize("text", NASTY_TEXTS)
    def test_find_all_by_text(self, text: str) -> None:
        d = MagicMock()
        d.find_elements.return_value = []
        UniversalFinder(d).find_all_by_text(text)
        assert_xpath_safe(d.find_elements.call_args.args[1], text, FIND_ALL_BY_TEXT, groups=3)


@pytest.mark.unit
class TestScreenContainsTextFalseGreen:
    """Предикат не имеет права превращать мёртвый драйвер в «текста нет»."""

    @pytest.mark.parametrize(
        "error",
        [
            InvalidSessionIdException("invalid session id"),
            ConnectionRefusedError(10061, "target machine refused"),
        ],
    )
    def test_dead_driver_propagates(self, error: Exception) -> None:
        d = MagicMock()
        d.find_element.side_effect = error
        with pytest.raises(type(error)):
            UniversalFinder(d).screen_contains_text("Login")

    def test_absent_text_is_a_calm_false(self) -> None:
        from selenium.common.exceptions import NoSuchElementException

        d = MagicMock()
        d.find_element.side_effect = NoSuchElementException("нет такого")
        assert UniversalFinder(d).screen_contains_text("Login") is False
