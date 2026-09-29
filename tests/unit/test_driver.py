"""Unit tests — appium_driver."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import urlparse

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
        url = APPIUM_SERVERS[ServerMode.SAUCE_LABS]
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname == "ondemand.us-west-1.saucelabs.com"

    def test_browserstack_url(self):
        url = APPIUM_SERVERS[ServerMode.BROWSER_STACK]
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname == "hub-cloud.browserstack.com"

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
    """create_driver обязан передавать выбранный адрес в webdriver.Remote."""

    def test_custom_server_url_overrides_mode(self):
        from mobius.driver.appium_driver import create_driver
        from mobius.driver.capabilities import pixel_6_api33

        with patch("mobius.driver.appium_driver.webdriver.Remote") as MockRemote:
            create_driver(pixel_6_api33(), server_url="http://custom:4723")

        # Безусловно: проверка внутри `if MockRemote.called:` проходила бы и
        # тогда, когда create_driver вообще не дошёл до драйвера.
        MockRemote.assert_called_once()
        assert MockRemote.call_args.kwargs["command_executor"] == "http://custom:4723"

    def test_mode_url_is_used_when_no_server_url_given(self, monkeypatch):
        from mobius.driver.appium_driver import APPIUM_SERVERS, ServerMode, create_driver
        from mobius.driver.capabilities import pixel_6_api33

        monkeypatch.delenv("APPIUM_SERVER_URL", raising=False)
        monkeypatch.setenv("SAUCE_USERNAME", "u")
        monkeypatch.setenv("SAUCE_ACCESS_KEY", "k")

        with patch("mobius.driver.appium_driver.webdriver.Remote") as MockRemote:
            create_driver(pixel_6_api33(), mode=ServerMode.SAUCE_LABS)

        kwargs = MockRemote.call_args.kwargs
        assert kwargs["command_executor"] == APPIUM_SERVERS[ServerMode.SAUCE_LABS]
        # Секрет не в адресе, а в конфиге клиента (Basic-заголовок).
        assert "@" not in kwargs["command_executor"]
        assert kwargs["client_config"] is not None

    def test_cloud_mode_without_credentials_never_opens_a_session(self, monkeypatch):
        """
        Прогон против облачного хаба без ключей — это ошибка конфигурации
        запуска. Молча создать сессию с пустым Basic-заголовком означало бы
        получить 401 посреди теста и принять его за провал приложения.
        """
        from mobius.driver.appium_driver import ServerMode, create_driver
        from mobius.driver.capabilities import pixel_6_api33

        monkeypatch.delenv("APPIUM_SERVER_URL", raising=False)
        monkeypatch.delenv("SAUCE_USERNAME", raising=False)
        monkeypatch.delenv("SAUCE_ACCESS_KEY", raising=False)

        with patch("mobius.driver.appium_driver.webdriver.Remote") as MockRemote:
            with pytest.raises(RuntimeError, match="SAUCE_USERNAME"):
                create_driver(pixel_6_api33(), mode=ServerMode.SAUCE_LABS)

        MockRemote.assert_not_called()


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
