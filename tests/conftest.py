"""Root conftest — драйвер, DevicePool, изоляция тестов, auto-skip без Appium."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import allure
import pytest


def _appium_available() -> bool:
    """Жив ли сервер — по тому же адресу, по которому пойдёт сессия.

    Харкод 127.0.0.1:4723 разошёлся бы с APPIUM_SERVER_URL: тесты либо
    пропускались бы при поднятом сервере, либо стартовали против мёртвого.
    """
    from mobius.driver.appium_driver import is_appium_available

    return is_appium_available()


APPIUM_UP = _appium_available()


# DevicePool — инициализируется один раз, управляет всеми устройствами CI.
# В реальном проекте: добавь сюда все свои эмуляторы/устройства.
# Каждый pytest-xdist worker получит своё устройство по worker_id.
def _build_device_pool():  # type: ignore[return]
    from mobius.driver.capabilities import Platform
    from mobius.driver.device_pool import DevicePool

    pool = DevicePool()
    # DEVICE_UDIDS — список через запятую, когда на раннере несколько
    # эмуляторов; DEVICE_UDID — один дефолт для локальной разработки.
    udids = [
        u.strip()
        for u in os.environ.get("DEVICE_UDIDS", os.environ.get("DEVICE_UDID", "")).split(",")
        if u.strip()
    ] or ["emulator-5554"]
    for udid in udids:
        pool.register(
            udid=udid,
            platform=Platform.ANDROID,
            platform_version=os.environ.get("PLATFORM_VERSION", "13.0"),
            device_name=os.environ.get("DEVICE_NAME", "Pixel 6"),
        )
    pool.assert_no_port_collisions()
    return pool


_POOL = None


@pytest.fixture(scope="session")
def device_pool():  # type: ignore[return]
    """Session-scoped DevicePool — один на всю тестовую сессию."""
    global _POOL
    if _POOL is None:
        _POOL = _build_device_pool()
    return _POOL


@pytest.fixture(scope="session")
def driver(device_pool, request: pytest.FixtureRequest) -> Generator[Any, None, None]:
    """
    Session-scoped Appium driver.
    - Если Appium не запущен: auto-skip всей UI-сессии
    - Если pytest-xdist: каждый worker получает СВОЁ устройство из pool
    - Порты гарантированно уникальны между параллельными worker'ами
    """
    if not APPIUM_UP:
        from mobius.driver.appium_driver import default_server_url

        pytest.skip(
            f"Appium server not reachable at {default_server_url()} — "
            f"start it with `appium` or point APPIUM_SERVER_URL at the running server"
        )

    from mobius.driver.appium_driver import create_driver
    from mobius.driver.capabilities import (
        AutomationName,
        DeviceCapabilities,
        Platform,
        from_env,
    )

    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    device = device_pool.get_for_worker(worker_id)
    extra = device_pool.to_capabilities_extra(device)

    if os.environ.get("CI"):
        caps = from_env()
        caps.extra.update(extra)
    else:
        caps = DeviceCapabilities(
            platform=Platform(device.platform.value),
            device_name=device.device_name,
            platform_version=device.platform_version,
            automation_name=AutomationName.UIAUTOMATOR2,
            app=os.environ.get("APP_PATH", "resources/apk/app.apk"),
            extra=extra,
        )

    d = create_driver(caps)
    d.implicitly_wait(0)
    yield d
    d.quit()


@pytest.fixture
def isolation(driver: Any) -> Any:
    """
    AppResetHelper для сброса состояния приложения между тестами.
    Использование: def test_foo(driver, isolation): isolation.reset()
    """
    from mobius.utils.test_isolation import AppResetHelper

    app_package = os.environ.get("APP_PACKAGE", "com.saucelabs.mydemoapp.rn")
    return AppResetHelper(driver, app_package)


@pytest.fixture
def login_screen(driver: Any):  # type: ignore[return]
    from mobius.screens.login_screen import LoginScreen

    return LoginScreen(driver)


@pytest.fixture
def home_screen(driver: Any):  # type: ignore[return]
    from mobius.screens.home_screen import HomeScreen

    return HomeScreen(driver)


@pytest.fixture
def product_screen(driver: Any):  # type: ignore[return]
    from mobius.screens.product_screen import ProductDetailScreen

    return ProductDetailScreen(driver)


@pytest.fixture
def checkout_screen(driver: Any):  # type: ignore[return]
    from mobius.screens.product_screen import CheckoutScreen

    return CheckoutScreen(driver)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.failed and "driver" in item.fixturenames:
        d = item.funcargs.get("driver")
        if d:
            try:
                allure.attach(
                    d.get_screenshot_as_png(),
                    name=f"FAIL: {item.name}",
                    attachment_type=allure.attachment_type.PNG,
                )
            except Exception:
                pass


def pytest_addoption(parser: pytest.Parser) -> None:
    """--live-api: запустить API тесты против реального dummyjson.com."""
    parser.addoption(
        "--live-api",
        action="store_true",
        default=False,
        help="Run API tests against real dummyjson.com (requires internet)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ui: requires Appium + device")
    config.addinivalue_line("markers", "android: Android-specific")
    config.addinivalue_line("markers", "ios: iOS-specific")
    config.addinivalue_line("markers", "smoke: smoke suite")
    config.addinivalue_line("markers", "regression: full regression")

    # Smart retry (ADR-008): pytest-rerunfailures --reruns не должен
    # ретраить AssertionError/ValueError/AttributeError — это реальные
    # баги, не инфраструктурная flaky-ность (Appium timeout, StaleElement).
    from mobius.utils.retry_config import configure_rerun_filter

    configure_rerun_filter(config)
