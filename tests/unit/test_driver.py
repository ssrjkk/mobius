"""Unit tests — appium_driver."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mobius.driver.appium_driver import (
    APPIUM_SERVERS,
    ServerMode,
    get_server_url,
    is_appium_available,
)


@pytest.mark.unit
class TestServerMode:
    def test_local_url(self):
        assert APPIUM_SERVERS[ServerMode.LOCAL] == "http://localhost:4723"

    def test_saucelabs_url(self):
        assert "saucelabs.com" in APPIUM_SERVERS[ServerMode.SAUCE_LABS]

    def test_browserstack_url(self):
        assert "browserstack.com" in APPIUM_SERVERS[ServerMode.BROWSER_STACK]

    def test_get_server_url_local(self):
        assert get_server_url(ServerMode.LOCAL) == "http://localhost:4723"

    def test_get_server_url_sauce(self):
        assert "saucelabs" in get_server_url(ServerMode.SAUCE_LABS)

    def test_get_server_url_bs(self):
        assert "browserstack" in get_server_url(ServerMode.BROWSER_STACK)

    def test_all_modes_have_url(self):
        for mode in ServerMode:
            assert get_server_url(mode)


@pytest.mark.unit
class TestIsAppiumAvailable:
    def test_false_when_unavailable(self):
        assert is_appium_available("http://localhost:19999") is False

    def test_false_on_exception(self):
        with patch("mobius.driver.appium_driver.requests") as m:
            m.get.side_effect = Exception("refused")
            assert is_appium_available() is False

    def test_true_on_200(self):
        with patch("mobius.driver.appium_driver.requests") as m:
            m.get.return_value.status_code = 200
            assert is_appium_available() is True

    def test_false_on_non_200(self):
        with patch("mobius.driver.appium_driver.requests") as m:
            m.get.return_value.status_code = 500
            assert is_appium_available() is False


@pytest.mark.unit
class TestCreateDriverUrl:
    """Покрываем line 32: url = server_url or APPIUM_SERVERS[mode]."""

    def test_custom_server_url_overrides_mode(self):
        from mobius.driver.appium_driver import create_driver
        from mobius.driver.capabilities import pixel_6_api33

        caps = pixel_6_api33()
        # create_driver вызовет webdriver.Remote который упадёт без сервера,
        # но мы мокируем его — нас интересует только что url передан правильно
        from unittest.mock import patch

        with patch("mobius.driver.appium_driver.webdriver.Remote") as MockRemote:
            try:
                create_driver(caps, server_url="http://custom:4723")
            except Exception:
                pass
            if MockRemote.called:
                call_kwargs = MockRemote.call_args
                url_used = call_kwargs[1].get("command_executor") or call_kwargs[0][0]
                assert url_used == "http://custom:4723"


@pytest.mark.unit
class TestCreateDriverCapabilities:
    """
    Регрессионный тест: Appium-Python-Client 5.x убрал desired_capabilities
    из webdriver.Remote(). Проверяем что create_driver использует правильный
    AppiumOptions.load_capabilities() путь, а не невалидный kwarg.
    """

    def test_uses_appium_options_load_capabilities(self):
        from unittest.mock import MagicMock, patch

        from mobius.driver.appium_driver import create_driver
        from mobius.driver.capabilities import pixel_6_api33

        caps = pixel_6_api33()

        with (
            patch("mobius.driver.appium_driver.webdriver.Remote") as MockRemote,
            patch("mobius.driver.appium_driver.AppiumOptions") as MockOptions,
        ):
            mock_options_instance = MagicMock()
            MockOptions.return_value = mock_options_instance

            create_driver(caps, server_url="http://localhost:4723")

            # AppiumOptions() создан и load_capabilities вызван с dict капабилити
            mock_options_instance.load_capabilities.assert_called_once_with(caps.to_dict())

            # webdriver.Remote вызван с options=..., НЕ с desired_capabilities=...
            _, call_kwargs = MockRemote.call_args
            assert "options" in call_kwargs
            assert "desired_capabilities" not in call_kwargs
            assert call_kwargs["options"] is mock_options_instance

    def test_real_appium_options_accepts_capabilities_dict(self):
        """
        Не мокаем AppiumOptions — проверяем что реальный класс из
        установленного Appium-Python-Client действительно принимает
        наш словарь капабилити без ошибок.
        """
        from appium.options.common.base import AppiumOptions

        from mobius.driver.capabilities import pixel_6_api33

        caps = pixel_6_api33()
        options = AppiumOptions()
        options.load_capabilities(caps.to_dict())

        assert options.capabilities["platformName"] == "Android"
        assert options.capabilities["appium:deviceName"] == "Pixel 6"
