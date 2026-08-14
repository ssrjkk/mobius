"""
Locale / language switching — для тестирования локализации.

ВАЖНО: runtime-смена локали поддерживается не всеми версиями Appium драйверов
одинаково. Самый надёжный способ — задать 'language'/'locale' capabilities
при старте сессии. Этот класс даёт best-effort попытку через mobile: команды
и безопасно no-op'ится если платформа/драйвер её не поддерживает.
"""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger
from mobius.utils.platform_info import is_android

logger = get_logger(__name__)


class LocaleManager:
    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def set_locale(self, language: str, country: str | None = None) -> bool:
        """
        language: ISO 639-1, например 'en', 'ru', 'de'.
        country: ISO 3166-1, например 'US', 'RU', 'DE'.
        Возвращает True если команда выполнена без исключения (не гарантирует
        что драйвер её реально поддержал — проверяй get_current_locale()).
        """
        payload: dict[str, Any] = {"language": language}
        if country:
            payload["country"] = country
        command = "mobile: setDeviceLocale" if is_android(self._driver) else "mobile: setLocale"
        try:
            self._driver.execute_script(command, payload)
            return True
        except Exception as e:
            logger.warning(
                "set_locale: '%s' with payload %s failed — driver/platform "
                "may not support runtime locale change (see module docstring): %s",
                command,
                payload,
                e,
            )
            return False

    def get_current_locale(self) -> dict[str, Any]:
        try:
            settings = self._driver.get_settings() or {}
            return {"locale": settings.get("locale", "unknown")}
        except Exception as e:
            logger.warning("get_current_locale: get_settings() failed: %s", e)
            return {"locale": "unknown"}
