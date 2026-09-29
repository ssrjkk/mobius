"""Разделение «штатного негатива» и «драйвера больше нет».

Best-effort хелперы Mobius (`is_displayed`, `is_element_present`,
`screen_contains_text`) по контракту возвращают False когда элемента нет.
Раньше в тот же `except Exception` попадал и мёртвый Appium: разорванное
соединение или протухшая сессия выглядели как «элемента нет на экране», и
провал на инфраструктуре превращался в зелёный прогон false-green.
"""

from __future__ import annotations

import re

from selenium.common.exceptions import (
    InvalidSessionIdException,
    SessionNotCreatedException,
    WebDriverException,
)

# Ошибки уровня «драйвера больше нет»: протухшая сессия, неподнятая сессия
# (битые capabilities), разорванное соединение. requests/urllib3 наследуют
# ConnectionError от OSError — одного OSError достаточно.
FATAL_ERRORS: tuple[type[Exception], ...] = (
    InvalidSessionIdException,
    SessionNotCreatedException,
    OSError,
)

# Selenium оборачивает транспортные и session-level сбои в голый
# WebDriverException (без отдельного класса) — опознаём их по сообщению.
_FATAL_MESSAGE = re.compile(
    r"invalid session id|no such session|not registered|session (?:has )?(?:expired|closed)"
    r"|max retries exceeded|failed to establish|connection refused|econnrefused"
    r"|remote end closed connection|target machine refused|connection aborted",
    re.IGNORECASE,
)


def is_driver_dead(exc: BaseException) -> bool:
    """True если ошибка означает потерю драйвера, а не отсутствие элемента."""
    if isinstance(exc, FATAL_ERRORS) or isinstance(exc.__cause__, OSError):
        return True
    return isinstance(exc, WebDriverException) and bool(_FATAL_MESSAGE.search(str(exc)))


def rethrow_if_driver_dead(exc: BaseException) -> None:
    """Фатальную ошибку драйвера поднимаем наружу; «элемента нет» оставляем как есть."""
    if is_driver_dead(exc):
        raise exc
