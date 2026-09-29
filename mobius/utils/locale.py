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
from mobius.utils.capability import read_capability
from mobius.utils.driver_health import rethrow_if_driver_dead
from mobius.utils.platform_info import is_android

logger = get_logger(__name__)


def _shell_stdout(out: Any, prop: str) -> str:
    """
    Разбирает ответ `mobile: shell`: драйвер отдаёт либо строку stdout, либо
    словарь {'stdout': ..., 'stderr': ..., 'code': ...}.

    Приведение через str() здесь — это ловушка: любое нетекстовое значение
    (None-ответ, dict без stdout, огрыток протокола) превращается в
    непустую строку, и get_current_locale() возвращает «локаль», которой
    устройство не выдавало.
    """
    if isinstance(out, str):
        return out.strip()
    if isinstance(out, dict):
        stdout = out.get("stdout")
        if isinstance(stdout, str):
            return stdout.strip()
    logger.warning(
        "get_current_locale: unexpected 'mobile: shell getprop %s' response type %s "
        "— treated as no value.",
        prop,
        type(out).__name__,
    )
    return ""


class LocaleManager:
    # persist.sys.locale — текущая локаль, выставленная пользователем/системой;
    # ro.product.locale — локаль сборки по умолчанию (тоже полезная, но weaker).
    _LOCALE_PROPS: tuple[str, ...] = ("persist.sys.locale", "ro.product.locale")

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
            rethrow_if_driver_dead(e)
            logger.warning(
                "set_locale: '%s' with payload %s failed — driver/platform "
                "may not support runtime locale change (see module docstring): %s",
                command,
                payload,
                e,
            )
            return False

    def get_current_locale(self) -> dict[str, Any]:
        """
        Читает локаль с самого устройства, а не из настроек сессии.

        `driver.get_settings()` локаль не отдаёт вообще: сверяться с ним —
        значит вечно получать 'unknown' и иметь «локализационный тест», который
        ничего не сверил. Ключ 'source' говорит, откуда взято значение;
        'unknown' возвращается только когда прочитать нечем, и это логируется.
        """
        if is_android(self._driver):
            for prop in self._LOCALE_PROPS:
                value = self._read_android_prop(prop)
                if value:
                    return self._as_dict(value, prop)
            logger.warning(
                "get_current_locale: neither %s returned a value — locale is unknown "
                "for this device.",
                " / ".join(self._LOCALE_PROPS),
            )
            return self._as_dict("unknown", "unavailable")

        caps = self._capabilities_locale()
        if caps:
            return self._as_dict(caps, "appium:locale (requested in capabilities)")
        logger.warning(
            "get_current_locale: this platform exposes no locale read command and the "
            "session has no appium:locale capability — locale is unknown."
        )
        return self._as_dict("unknown", "unavailable")

    def _read_android_prop(self, prop: str) -> str:
        try:
            out = self._driver.execute_script(
                "mobile: shell", {"command": "getprop", "args": [prop]}
            )
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning("get_current_locale: getprop %s failed: %s", prop, e)
            return ""
        return _shell_stdout(out, prop)

    def _capabilities_locale(self) -> str:
        return read_capability(self._driver, "appium:locale", "locale", caller="get_current_locale")

    @staticmethod
    def _as_dict(locale_value: str, source: str) -> dict[str, Any]:
        # Android отдаёт BCP-47 через дефис ('ru-RU'), iOS capabilities — через
        # подчёркивание ('ru_RU'): нормализуем, чтобы сравнение не зависело от источника.
        normalized = locale_value.replace("_", "-")
        language, _, country = normalized.partition("-")
        return {
            "locale": normalized,
            "language": language,
            "country": country,
            "source": source,
        }
