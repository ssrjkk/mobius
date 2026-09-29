"""Проверка аргументов, которые уходят в `mobile: shell`.

Эти значения — внешние: они приходят из конфигов, фикстур и тестовых данных,
поэтому их нельзя считать доверенными.

Appium драйвер собирает `{'command': ..., 'args': [...]}` в одну строку
`adb shell`, а `mobile: shell emu ...` попадает в Telnet-консоль эмулятора,
где перевод строки означает «началась следующая команда». Поэтому передача
аргументов списком сама по себе не защита: значение с `;`, обратным слэшем
или `\\n` домножает команду на устройстве. Здесь эти дыры закрываются на
входе — молчаливый `return False` вместо этого означал бы зелёный тест,
который ничего не выполнил.
"""

from __future__ import annotations

import re

# Имя пакета Android: reverse-DOM из сегментов, начинающихся с буквы.
_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$")

# Телефон для emulator console: цифры с опциональным '+'.
_PHONE_RE = re.compile(r"^\+?[0-9]{1,15}$")

# Управляющие символы (включая \n, \r, \t, NUL и DEL) рвут одну аргумент-
# строку на несколько команд.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def checked_package(package: str, *, caller: str) -> str:
    """Возвращает имя пакета или падает, если его нельзя безопасно отправить в shell."""
    if not _PACKAGE_RE.match(package or ""):
        raise ValueError(
            f"{caller}: '{package}' is not a valid Android package name "
            "(expected a reverse-DOM value like 'com.example.app'). Refusing to "
            "pass it to 'mobile: shell' — shell arguments are joined into one "
            "command line, so an arbitrary string could add commands."
        )
    return package


def checked_phone(phone_number: str, *, caller: str) -> str:
    """Возвращает номер телефона в формате, безопасном для консоли эмулятора."""
    if not _PHONE_RE.match(phone_number or ""):
        raise ValueError(
            f"{caller}: '{phone_number}' is not a plain phone number "
            "(digits, optional leading '+'). Refusing to send it to the emulator "
            "console, where extra whitespace or a newline starts another command."
        )
    return phone_number


def checked_console_text(message: str, *, caller: str) -> str:
    """Разрешает многословный текст (пробелы — нормально), но без управляющих символов."""
    found = _CONTROL_RE.search(message or "")
    if found:
        raise ValueError(
            f"{caller}: message contains control character "
            f"{hex(ord(found.group(0)))} — the emulator console treats a newline "
            "as the start of a new command. Strip control characters in test data."
        )
    return message
