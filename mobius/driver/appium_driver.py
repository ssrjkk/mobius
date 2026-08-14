"""Appium Driver Factory — Appium-Python-Client 5.x совместимый.

ВАЖНО: 5.x убрал параметр desired_capabilities из webdriver.Remote().
Правильный путь — appium.options.common.base.AppiumOptions с load_capabilities().
Проверено: inspect.signature(WebDriver.__init__) содержит только
command_executor / extensions / options / client_config.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any

import requests
from appium import webdriver
from appium.options.common.base import AppiumOptions

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


def create_driver(
    capabilities: DeviceCapabilities,
    mode: ServerMode = ServerMode.LOCAL,
    server_url: str | None = None,
) -> Any:
    """Создаёт Appium WebDriver сессию."""
    url = server_url or APPIUM_SERVERS[mode]

    if mode == ServerMode.SAUCE_LABS:  # pragma: no cover
        u, k = os.environ["SAUCE_USERNAME"], os.environ["SAUCE_ACCESS_KEY"]
        url = f"https://{u}:{k}@ondemand.us-west-1.saucelabs.com/wd/hub"
    elif mode == ServerMode.BROWSER_STACK:  # pragma: no cover
        u, k = os.environ["BROWSERSTACK_USER"], os.environ["BROWSERSTACK_KEY"]
        url = f"https://{u}:{k}@hub-cloud.browserstack.com/wd/hub"

    options = AppiumOptions()
    options.load_capabilities(capabilities.to_dict())

    return webdriver.Remote(  # pragma: no cover
        command_executor=url,
        options=options,
    )


def is_appium_available(server_url: str = "http://localhost:4723") -> bool:
    """Проверяем доступность Appium сервера без создания сессии."""
    try:
        return bool(requests.get(f"{server_url}/status", timeout=2).status_code == 200)
    except Exception as e:
        # DEBUG: используется в conftest.py чтобы решить пропускать ли UI
        # тесты — "сервера нет" абсолютно нормальный исход при unit-only
        # прогоне, не повод для WARNING.
        logger.debug("is_appium_available('%s'): server not reachable: %s", server_url, e)
        return False


def get_server_url(mode: ServerMode) -> str:
    """Возвращает URL сервера для заданного режима."""
    return APPIUM_SERVERS.get(mode, APPIUM_SERVERS[ServerMode.LOCAL])
