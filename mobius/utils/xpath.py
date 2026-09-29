"""Экранирование литералов для XPath и UiSelector.

Любой текст, который попадает в локатор извне (из фикстуры, с экрана
устройства, от пользователя), обязан проходить через эти функции. В XPath 1.0
нет механизма экранирования кавычек: литерал закрывается следующим таким же
символом, поэтому кавычка внутри текста ломает выражение, а кавычка + `]` —
это уже инъекция лишнего предиката в чужой локатор.
"""

from __future__ import annotations


def xpath_literal(value: str) -> str:
    """Произвольная строка → валидный XPath string literal."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts: list[str] = []
    chunks = value.split("'")
    for i, chunk in enumerate(chunks):
        if i:
            parts.append('"\'"')
        if chunk:
            parts.append(f"'{chunk}'")
    return "concat(" + ", ".join(parts) + ")"


def uiautomator_literal(value: str) -> str:
    """
    Строка → литерал аргумента UiSelector.

    Парсер Appium читает выражение как Java-строку: обратный слэш и двойная
    кавычка обязательны для экранирования, иначе поиск по тексту закрывает
    литерал раньше времени и ломает всё выражение.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
