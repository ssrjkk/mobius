"""
Чтение строк из capabilities сессии.

Capabilities — внешний вход: их формирует конфиг/окружение, а отдаёт их драйвер
уже после старта сессии. Значение может отсутствовать или прийти не строкой, и
приведение через `str(...)` превращает и то и другое в осмысленную на вид
строку: `appPackage` становится текстом repr, а `locale` — тем, чего на
устройстве нет. Проверка типа здесь поэтому не придирка, а единственное, что
отличает «capability задан» от «мусор на входе».
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


def read_capability(driver: Any, *keys: str, caller: str) -> str:
    """
    Возвращает первое непустое строковое значение из capabilities по ключам.

    Пустая строка — это «значения нет», и вызывающий код обязан отреагировать
    явно (предупреждение/False), а не подставлять заглушку.
    """
    try:
        caps = driver.capabilities
    except Exception as e:
        logger.warning("%s: couldn't read driver capabilities: %s", caller, e)
        return ""
    if not isinstance(caps, Mapping):
        logger.warning(
            "%s: driver.capabilities is %s, not a mapping — no capability is readable from it.",
            caller,
            type(caps).__name__,
        )
        return ""
    for key in keys:
        value = caps.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            logger.warning(
                "%s: capability %r is %s, expected a string — ignored.",
                caller,
                key,
                type(value).__name__,
            )
            continue
        return value.strip()
    return ""
