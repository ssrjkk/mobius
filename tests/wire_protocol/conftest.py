"""
conftest для wire_protocol тестов — реальный HTTP сервер, реальный
Appium-Python-Client, реальный create_driver(). Единственное что НЕ
реально — нет настоящего Android/iOS за сервером.

В отличие от tests/unit/ (MagicMock driver) эти тесты проверяют что байты,
реально летящие по HTTP от framework, соответствуют W3C WebDriver protocol —
поймали бы, например, баг с desired_capabilities (mobius/driver/
appium_driver.py ADR-001) на уровне 'сервер получил невалидный запрос',
а не только на уровне 'Python не упал при импорте'.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from tests.wire_protocol.fake_webdriver_server import FakeWebDriverServer


@pytest.fixture
def wire_server() -> Generator[FakeWebDriverServer, None, None]:
    with FakeWebDriverServer() as server:
        yield server


@pytest.fixture
def wire_driver(wire_server: FakeWebDriverServer):  # type: ignore[return]
    """Реальный Appium WebDriver, подключённый к fake серверу."""
    from mobius.driver.appium_driver import create_driver
    from mobius.driver.capabilities import pixel_6_api33

    caps = pixel_6_api33()
    driver = create_driver(caps, server_url=wire_server.url)
    # Многие framework методы вызывают get_window_size() — fake сервер
    # не умеет в него осмысленно, патчим на реалистичное значение.
    driver.get_window_size = lambda: {"width": 1080, "height": 2400}
    yield driver
    driver.quit()
