"""Appium Driver Factory — Appium-Python-Client 5.x/6.x совместимый.

ВАЖНО: 5.x убрал параметр desired_capabilities из webdriver.Remote().
Правильный путь — appium.options.common.base.AppiumOptions с load_capabilities().
Проверено: inspect.signature(WebDriver.__init__) содержит только
command_executor / extensions / options / client_config.

Облачные креды НИКОГДА не попадают в URL. Selenium сам предупреждает об этом
(«Embedding username and password in URL could be insecure, use ClientConfig
instead»); проверено эмпирически. Креды в адресе утекают в access-логи прокси
и стейдж-агентов, в вывод `ps`, в traceback и в repr command_executor.
Поэтому авторизация идёт Basic-заголовком через AppiumClientConfig, который
наследуется от selenium ClientConfig и принимается Appium's webdriver.Remote.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import requests
from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.client_config import AppiumClientConfig

from mobius.driver.capabilities import DeviceCapabilities
from mobius.logging_config import get_logger

logger = get_logger(__name__)


class ServerMode(str, Enum):
    LOCAL = "local"
    SAUCE_LABS = "saucelabs"
    BROWSER_STACK = "browserstack"


APPIUM_SERVERS = {
    ServerMode.LOCAL: "http://localhost:4723",
    ServerMode.SAUCE_LABS: "https://ondemand.us-west-1.saucelabs.com/wd/hub",
    ServerMode.BROWSER_STACK: "https://hub-cloud.browserstack.com/wd/hub",
}

#: Переменные окружения, из которых берутся креды для каждого облачного режима.
CREDENTIAL_ENV_VARS: dict[ServerMode, tuple[str, str]] = {
    ServerMode.SAUCE_LABS: ("SAUCE_USERNAME", "SAUCE_ACCESS_KEY"),
    ServerMode.BROWSER_STACK: ("BROWSERSTACK_USER", "BROWSERSTACK_KEY"),
}

#: Явный адрес сервера/хаба. Нужен, когда Appium запущен с --base-path
#: (например http://localhost:4723/wd/hub) — иначе POST /session уходит не туда.
SERVER_URL_ENV = "APPIUM_SERVER_URL"

#: Жёсткий таймаут health-check'а: is_appium_available() вызывается из conftest
#: на каждом запуске и не должен вешать прогон на зависший прокси.
SERVER_STATUS_TIMEOUT = 2


def _extract_url_credentials(url: str) -> tuple[str, str | None, str | None]:
    """Разбирает `scheme://user:pass@host/path` на чистый URL и креды.

    Пользователь мог передать hub-адрес с кредами в userinfo — это рабочий,
    но небезопасный формат. Разворачиваем его в Basic-авторизацию, чтобы
    секрет не оставался в адресе строки запроса.
    """
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url, None, None
    userinfo, _, host = parts.netloc.rpartition("@")
    username, _, password = userinfo.partition(":")
    clean = urlunsplit(parts._replace(netloc=host))
    return clean, unquote(username) or None, unquote(password) or None


def cloud_credentials(mode: ServerMode) -> tuple[str, str]:
    """Креды облачного провайдера из окружения.

    Отсутствие переменной — это конфигурационная ошибка запуска, а не баг
    внутри Mobius, поэтому поднимаем RuntimeError с actionable-сообщением
    вместо голого KeyError из `os.environ[...]`.
    """
    env_vars = CREDENTIAL_ENV_VARS.get(mode)
    if env_vars is None:
        raise ValueError(f"Mode '{mode}' is not a cloud provider")
    username_var, key_var = env_vars
    username = os.environ.get(username_var, "").strip()
    access_key = os.environ.get(key_var, "").strip()
    if not username or not access_key:
        raise RuntimeError(
            f"{mode.value} requires both {username_var} and {key_var} to be set "
            f"(got username={'set' if username else 'missing'}, "
            f"access_key={'set' if access_key else 'missing'})"
        )
    return username, access_key


def default_server_url(mode: ServerMode = ServerMode.LOCAL) -> str:
    """Адрес по умолчанию: APPIUM_SERVER_URL важнее встроенного для mode.

    Встроенный адрес локального режима — Appium 2 по умолчанию (без base-path).
    Кто запускает Appium с `--base-path /wd/hub` обязан дать APPIUM_SERVER_URL,
    иначе POST /session уходит не туда и даёт 404.
    """
    override = os.environ.get(SERVER_URL_ENV, "").strip()
    return override or APPIUM_SERVERS[mode]


def resolve_connection(
    mode: ServerMode = ServerMode.LOCAL,
    server_url: str | None = None,
) -> tuple[str, AppiumClientConfig | None]:
    """Адрес Appium/хаба и конфиг с Basic-авторизацией (None — без её).

    Креды из окружения приоритетнее: облачный режим обязан быть настроен
    переменными, а не секретом в строке адреса. Если переменных нет, а креды
    всё-таки вписаны в server_url, они попадают в Basic-заголовок и мы
    предупреждаем о нежелательном формате.
    """
    if server_url is None:
        server_url = default_server_url(mode)

    url, url_user, url_password = _extract_url_credentials(server_url)
    username: str | None = url_user
    password: str | None = url_password

    if mode in CREDENTIAL_ENV_VARS:
        try:
            username, password = cloud_credentials(mode)
        except RuntimeError:
            if not (username and password):
                raise
            logger.warning(
                "%s: credentials taken from server_url — prefer the %s and %s "
                "environment variables so the secret stays out of the address",
                mode.value,
                *CREDENTIAL_ENV_VARS[mode],
            )

    if not (username and password):
        return url, None
    return url, AppiumClientConfig(remote_server_addr=url, username=username, password=password)


def create_driver(
    capabilities: DeviceCapabilities,
    mode: ServerMode = ServerMode.LOCAL,
    server_url: str | None = None,
) -> Any:
    """Создаёт Appium WebDriver сессию."""
    url, client_config = resolve_connection(mode, server_url)

    options = AppiumOptions()
    options.load_capabilities(capabilities.to_dict())

    return webdriver.Remote(
        command_executor=url,
        options=options,
        client_config=client_config,
    )


def is_appium_available(server_url: str | None = None) -> bool:
    """Проверяем доступность Appium сервера без создания сессии."""
    url = server_url or default_server_url()
    try:
        response = requests.get(f"{url}/status", timeout=SERVER_STATUS_TIMEOUT)
        return bool(response.status_code == 200)
    except Exception as e:
        # DEBUG: используется в conftest.py чтобы решить пропускать ли UI
        # тесты — "сервера нет" абсолютно нормальный исход при unit-only
        # прогоне, не повод для WARNING.
        logger.debug("is_appium_available('%s'): server not reachable: %s", url, e)
        return False


def get_server_url(mode: ServerMode) -> str:
    """Возвращает URL сервера для заданного режима."""
    return default_server_url(mode)
