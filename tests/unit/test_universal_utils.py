"""
Unit tests — universal device-level utilities.
Покрывает: platform_info, device, alerts, permissions, clipboard, locale,
universal_finder, notifications.

Эти модули не зависят от конкретного SUT — работают на любом Android/iOS
приложении, поэтому тестируются через generic mock driver без привязки
к Sauce Labs Demo App.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mobius.utils.alerts import SystemAlertHandler
from mobius.utils.clipboard import ClipboardManager
from mobius.utils.device import DeviceActions, HardwareKey, Orientation
from mobius.utils.locale import LocaleManager
from mobius.utils.notifications import NotificationHelper
from mobius.utils.permissions import Permission, PermissionAction, PermissionsManager
from mobius.utils.platform_info import get_platform_name, is_android, is_ios
from mobius.utils.universal_finder import UniversalFinder


def android_driver() -> MagicMock:
    d = MagicMock()
    d.capabilities = {"platformName": "Android"}
    return d


def ios_driver() -> MagicMock:
    d = MagicMock()
    d.capabilities = {"platformName": "iOS"}
    return d


# ── platform_info ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPlatformInfo:
    def test_get_platform_name_android(self):
        assert get_platform_name(android_driver()) == "android"

    def test_get_platform_name_ios(self):
        assert get_platform_name(ios_driver()) == "ios"

    def test_get_platform_name_missing_returns_empty(self):
        d = MagicMock()
        d.capabilities = {}
        assert get_platform_name(d) == ""

    def test_get_platform_name_exception_returns_empty(self):
        d = MagicMock()
        type(d).capabilities = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert get_platform_name(d) == ""

    def test_is_android_true(self):
        assert is_android(android_driver()) is True

    def test_is_android_false_for_ios(self):
        assert is_android(ios_driver()) is False

    def test_is_ios_true(self):
        assert is_ios(ios_driver()) is True

    def test_is_ios_false_for_android(self):
        assert is_ios(android_driver()) is False


# ── DeviceActions ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDeviceActions:
    def setup_method(self):
        self.d = android_driver()
        self.dev = DeviceActions(self.d)

    def test_get_orientation(self):
        self.d.orientation = "PORTRAIT"
        assert self.dev.get_orientation() == "PORTRAIT"

    def test_set_orientation(self):
        self.dev.set_orientation(Orientation.LANDSCAPE)
        assert self.d.orientation == "LANDSCAPE"

    def test_rotate_to_landscape(self):
        self.dev.rotate_to_landscape()
        assert self.d.orientation == "LANDSCAPE"

    def test_rotate_to_portrait(self):
        self.dev.rotate_to_portrait()
        assert self.d.orientation == "PORTRAIT"

    def test_is_landscape_true(self):
        self.d.orientation = "LANDSCAPE"
        assert self.dev.is_landscape() is True

    def test_is_landscape_false(self):
        self.d.orientation = "PORTRAIT"
        assert self.dev.is_landscape() is False

    def test_lock(self):
        self.dev.lock(5)
        self.d.lock.assert_called_once_with(5)

    def test_unlock(self):
        self.dev.unlock()
        self.d.unlock.assert_called_once()

    def test_is_locked_true(self):
        self.d.is_locked.return_value = True
        assert self.dev.is_locked() is True

    def test_press_key(self):
        self.dev.press_key(HardwareKey.BACK)
        self.d.press_keycode.assert_called_once_with(4)

    def test_press_back(self):
        self.dev.press_back()
        self.d.press_keycode.assert_called_once_with(HardwareKey.BACK.value)

    def test_press_home(self):
        self.dev.press_home()
        self.d.press_keycode.assert_called_once_with(HardwareKey.HOME.value)

    def test_press_app_switch(self):
        self.dev.press_app_switch()
        self.d.press_keycode.assert_called_once_with(HardwareKey.APP_SWITCH.value)

    def test_background_app(self):
        self.dev.background_app(3)
        self.d.background_app.assert_called_once_with(3)

    def test_activate_app(self):
        self.dev.activate_app("com.app")
        self.d.activate_app.assert_called_once_with("com.app")

    def test_terminate_app_true(self):
        self.d.terminate_app.return_value = True
        assert self.dev.terminate_app("com.app") is True

    def test_is_app_installed_true(self):
        self.d.is_app_installed.return_value = True
        assert self.dev.is_app_installed("com.app") is True

    def test_reset_app_calls_terminate_then_activate(self):
        self.dev.reset_app("com.app")
        self.d.terminate_app.assert_called_once_with("com.app")
        self.d.activate_app.assert_called_once_with("com.app")

    def test_reset_app_survives_terminate_exception(self):
        self.d.terminate_app.side_effect = Exception("not running")
        self.dev.reset_app("com.app")  # не падает
        self.d.activate_app.assert_called_once_with("com.app")

    def test_set_location(self):
        self.dev.set_location(55.75, 37.61)
        self.d.set_location.assert_called_once_with(55.75, 37.61, 0.0)

    def test_get_location(self):
        self.d.location = {"latitude": 55.75, "longitude": 37.61, "altitude": 0}
        result = self.dev.get_location()
        assert result == {"latitude": 55.75, "longitude": 37.61}

    def test_get_location_empty(self):
        self.d.location = None
        result = self.dev.get_location()
        assert result == {"latitude": None, "longitude": None}

    def test_shake_no_crash_on_android(self):
        self.d.shake.side_effect = Exception("not supported on Android")
        self.dev.shake()  # не падает

    def test_get_device_time(self):
        self.d.device_time = "2026-07-01T12:00:00Z"
        assert self.dev.get_device_time() == "2026-07-01T12:00:00Z"

    def test_get_current_activity(self):
        self.d.current_activity = ".MainActivity"
        assert self.dev.get_current_activity() == ".MainActivity"

    def test_get_current_activity_exception_returns_empty(self):
        type(self.d).current_activity = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.dev.get_current_activity() == ""


# ── SystemAlertHandler ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestSystemAlertHandler:
    def setup_method(self):
        self.d = MagicMock()
        self.alerts = SystemAlertHandler(self.d)

    def test_is_present_true(self):
        self.d.switch_to.alert.text = "Allow access?"
        assert self.alerts.is_present() is True

    def test_is_present_false_on_exception(self):
        type(self.d.switch_to).alert = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.alerts.is_present() is False

    def test_accept_calls_selenium_accept(self):
        self.alerts.accept()
        self.d.switch_to.alert.accept.assert_called_once()

    def test_accept_falls_back_to_mobile_command(self):
        self.d.switch_to.alert.accept.side_effect = Exception("no alert")
        self.alerts.accept()
        self.d.execute_script.assert_called_once_with("mobile: acceptAlert")

    def test_accept_swallows_all_failures(self):
        self.d.switch_to.alert.accept.side_effect = Exception()
        self.d.execute_script.side_effect = Exception()
        self.alerts.accept()  # не падает

    def test_dismiss_calls_selenium_dismiss(self):
        self.alerts.dismiss()
        self.d.switch_to.alert.dismiss.assert_called_once()

    def test_dismiss_falls_back_to_mobile_command(self):
        self.d.switch_to.alert.dismiss.side_effect = Exception()
        self.alerts.dismiss()
        self.d.execute_script.assert_called_once_with("mobile: dismissAlert")

    def test_get_text(self):
        self.d.switch_to.alert.text = "Permission needed"
        assert self.alerts.get_text() == "Permission needed"

    def test_get_text_exception_returns_empty(self):
        type(self.d.switch_to).alert = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.alerts.get_text() == ""

    def test_accept_if_present_true(self):
        self.d.switch_to.alert.text = "x"
        assert self.alerts.accept_if_present() is True
        self.d.switch_to.alert.accept.assert_called_once()

    def test_accept_if_present_false_when_absent(self):
        type(self.d.switch_to).alert = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.alerts.accept_if_present() is False

    def test_dismiss_if_present_true(self):
        self.d.switch_to.alert.text = "x"
        assert self.alerts.dismiss_if_present() is True

    def test_dismiss_if_present_false_when_absent(self):
        type(self.d.switch_to).alert = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.alerts.dismiss_if_present() is False


# ── PermissionsManager ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestPermissionsManager:
    def setup_method(self):
        self.d = MagicMock()
        self.perms = PermissionsManager(self.d, app_package="com.app.test")

    def test_grant_calls_execute_script(self):
        self.perms.grant(Permission.CAMERA)
        self.d.execute_script.assert_called_once()
        args = self.d.execute_script.call_args[0]
        assert args[0] == "mobile: changePermissions"
        assert args[1]["permissions"] == ["camera"]
        assert args[1]["action"] == "grant"

    def test_revoke_calls_execute_script(self):
        self.perms.revoke(Permission.LOCATION)
        args = self.d.execute_script.call_args[0]
        assert args[1]["action"] == "revoke"

    def test_grant_swallows_exception(self):
        self.d.execute_script.side_effect = Exception("not supported")
        self.perms.grant(Permission.MICROPHONE)  # не падает

    def test_handle_permission_dialog_absent_returns_false(self):
        type(self.d.switch_to).alert = property(lambda self: (_ for _ in ()).throw(Exception()))
        assert self.perms.handle_permission_dialog(PermissionAction.ALLOW) is False

    def test_handle_permission_dialog_allow(self):
        self.d.switch_to.alert.text = "Allow camera access?"
        result = self.perms.handle_permission_dialog(PermissionAction.ALLOW)
        assert result is True
        self.d.switch_to.alert.accept.assert_called_once()

    def test_handle_permission_dialog_deny(self):
        self.d.switch_to.alert.text = "Allow camera access?"
        result = self.perms.handle_permission_dialog(PermissionAction.DENY)
        assert result is True
        self.d.switch_to.alert.dismiss.assert_called_once()


# ── ClipboardManager ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestClipboardManager:
    def setup_method(self):
        self.d = MagicMock()
        self.cb = ClipboardManager(self.d)

    def test_set_text(self):
        self.cb.set_text("hello world")
        self.d.set_clipboard_text.assert_called_once_with("hello world")

    def test_get_text(self):
        self.d.get_clipboard_text.return_value = "copied text"
        assert self.cb.get_text() == "copied text"

    def test_get_text_exception_returns_empty(self):
        self.d.get_clipboard_text.side_effect = Exception("not supported")
        assert self.cb.get_text() == ""

    def test_get_text_none_returns_empty(self):
        self.d.get_clipboard_text.return_value = None
        assert self.cb.get_text() == ""

    def test_clear_sets_empty_string(self):
        self.cb.clear()
        self.d.set_clipboard_text.assert_called_once_with("")


# ── LocaleManager ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLocaleManager:
    def test_set_locale_android_uses_correct_command(self):
        d = android_driver()
        loc = LocaleManager(d)
        result = loc.set_locale("ru", "RU")
        assert result is True
        args = d.execute_script.call_args[0]
        assert args[0] == "mobile: setDeviceLocale"
        assert args[1]["language"] == "ru"
        assert args[1]["country"] == "RU"

    def test_set_locale_ios_uses_correct_command(self):
        d = ios_driver()
        loc = LocaleManager(d)
        loc.set_locale("en", "US")
        args = d.execute_script.call_args[0]
        assert args[0] == "mobile: setLocale"

    def test_set_locale_without_country(self):
        d = android_driver()
        loc = LocaleManager(d)
        loc.set_locale("en")
        args = d.execute_script.call_args[0]
        assert "country" not in args[1]

    def test_set_locale_returns_false_on_exception(self):
        d = android_driver()
        d.execute_script.side_effect = Exception("unsupported")
        loc = LocaleManager(d)
        assert loc.set_locale("fr") is False

    def test_get_current_locale(self):
        d = android_driver()
        d.get_settings.return_value = {"locale": "ru_RU"}
        loc = LocaleManager(d)
        assert loc.get_current_locale() == {"locale": "ru_RU"}

    def test_get_current_locale_exception_returns_unknown(self):
        d = android_driver()
        d.get_settings.side_effect = Exception()
        loc = LocaleManager(d)
        assert loc.get_current_locale() == {"locale": "unknown"}


# ── UniversalFinder ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestUniversalFinder:
    def setup_method(self):
        self.d = android_driver()
        self.finder = UniversalFinder(self.d)

    def test_find_by_text_calls_find_element(self):
        self.d.find_element.return_value = MagicMock()
        self.finder.find_by_text("Login")
        self.d.find_element.assert_called_once()
        xpath = self.d.find_element.call_args[0][1]
        assert "Login" in xpath
        assert "contains(" in xpath

    def test_find_by_text_exact_uses_equality(self):
        self.finder.find_by_text("Login", exact=True)
        xpath = self.d.find_element.call_args[0][1]
        assert 'text="Login"' in xpath
        assert "contains(" not in xpath

    def test_find_all_by_text(self):
        self.d.find_elements.return_value = [MagicMock(), MagicMock()]
        result = self.finder.find_all_by_text("Item")
        assert len(result) == 2

    def test_find_any_button_android_uses_widget_classes(self):
        self.finder.find_any_button()
        xpath = self.d.find_elements.call_args[0][1]
        assert "android.widget.Button" in xpath

    def test_find_any_button_ios_uses_xcuitest_types(self):
        finder = UniversalFinder(ios_driver())
        finder._driver.find_elements.return_value = []
        finder.find_any_button()
        xpath = finder._driver.find_elements.call_args[0][1]
        assert "XCUIElementTypeButton" in xpath

    def test_find_any_input_android(self):
        self.finder.find_any_input()
        xpath = self.d.find_elements.call_args[0][1]
        assert "EditText" in xpath

    def test_find_any_input_ios(self):
        finder = UniversalFinder(ios_driver())
        finder._driver.find_elements.return_value = []
        finder.find_any_input()
        xpath = finder._driver.find_elements.call_args[0][1]
        assert "XCUIElementTypeTextField" in xpath

    def test_find_button_by_text_found(self):
        btn = MagicMock()
        btn.get_attribute.side_effect = lambda k: {"text": "Sign In"}.get(k, "")
        self.d.find_elements.return_value = [btn]
        result = self.finder.find_button_by_text("Sign In")
        assert result == btn

    def test_find_button_by_text_case_insensitive(self):
        btn = MagicMock()
        btn.get_attribute.side_effect = lambda k: {"text": "SIGN IN"}.get(k, "")
        self.d.find_elements.return_value = [btn]
        result = self.finder.find_button_by_text("sign in")
        assert result == btn

    def test_find_button_by_text_not_found_raises(self):
        self.d.find_elements.return_value = []
        with pytest.raises(ValueError, match="not found"):
            self.finder.find_button_by_text("Nonexistent")

    def test_find_button_by_text_uses_content_desc_fallback(self):
        btn = MagicMock()
        btn.get_attribute.side_effect = lambda k: {"content-desc": "Submit Order"}.get(k, "")
        self.d.find_elements.return_value = [btn]
        result = self.finder.find_button_by_text("Submit")
        assert result == btn

    def test_get_all_texts_on_screen(self):
        e1, e2 = MagicMock(), MagicMock()
        e1.get_attribute.side_effect = lambda k: {"text": "Hello"}.get(k, "")
        e2.get_attribute.side_effect = lambda k: {"text": "World"}.get(k, "")
        self.d.find_elements.return_value = [e1, e2]
        texts = self.finder.get_all_texts_on_screen()
        assert texts == ["Hello", "World"]

    def test_get_all_texts_skips_empty(self):
        e1 = MagicMock()
        e1.get_attribute.side_effect = lambda k: ""
        self.d.find_elements.return_value = [e1]
        texts = self.finder.get_all_texts_on_screen()
        assert texts == []

    def test_screen_contains_text_true(self):
        self.d.find_element.return_value = MagicMock()
        assert self.finder.screen_contains_text("Welcome") is True

    def test_screen_contains_text_false(self):
        from selenium.common.exceptions import NoSuchElementException

        self.d.find_element.side_effect = NoSuchElementException()
        assert self.finder.screen_contains_text("Missing") is False


# ── NotificationHelper ───────────────────────────────────────────────────────


@pytest.mark.unit
class TestNotificationHelper:
    def setup_method(self):
        self.d = MagicMock()
        self.notif = NotificationHelper(self.d)

    def test_open_shade(self):
        self.notif.open_shade()
        self.d.open_notifications.assert_called_once()

    def test_open_shade_swallows_exception(self):
        self.d.open_notifications.side_effect = Exception("not supported")
        self.notif.open_shade()  # не падает

    def test_get_notifications_text(self):
        e1, e2 = MagicMock(), MagicMock()
        e1.text = "New message"
        e2.text = "Update available"
        self.d.find_elements.return_value = [e1, e2]
        result = self.notif.get_notifications_text()
        assert result == ["New message", "Update available"]

    def test_get_notifications_text_skips_empty(self):
        e1 = MagicMock()
        e1.text = ""
        self.d.find_elements.return_value = [e1]
        result = self.notif.get_notifications_text()
        assert result == []

    def test_get_notifications_text_exception_returns_empty_list(self):
        self.d.find_elements.side_effect = Exception("driver error")
        assert self.notif.get_notifications_text() == []

    def test_has_notification_containing_true(self):
        e1 = MagicMock()
        e1.text = "Order shipped successfully"
        self.d.find_elements.return_value = [e1]
        assert self.notif.has_notification_containing("shipped") is True

    def test_has_notification_containing_false(self):
        e1 = MagicMock()
        e1.text = "Unrelated notification"
        self.d.find_elements.return_value = [e1]
        assert self.notif.has_notification_containing("shipped") is False

    def test_close_shade(self):
        self.notif.close_shade()
        self.d.press_keycode.assert_called_once_with(4)

    def test_close_shade_swallows_exception(self):
        self.d.press_keycode.side_effect = Exception("no keycode support")
        self.notif.close_shade()  # не падает


@pytest.mark.unit
class TestAlertsAndPermissionsExtra:
    """Покрываем оставшиеся ветки alerts.py и permissions.py."""

    def test_dismiss_falls_back_swallows_both_exceptions(self):
        d = MagicMock()
        d.switch_to.alert.dismiss.side_effect = Exception("no alert")
        d.execute_script.side_effect = Exception("not supported")
        alerts = SystemAlertHandler(d)
        alerts.dismiss()  # не падает

    def test_revoke_swallows_exception(self):
        d = MagicMock()
        d.execute_script.side_effect = Exception("unsupported command")
        perms = PermissionsManager(d, "com.app")
        perms.revoke(Permission.LOCATION)  # не падает

    def test_all_permission_types_exist(self):
        for perm in Permission:
            assert perm.value
            assert isinstance(perm.value, str)

    def test_locale_manager_uses_right_command_each_platform(self):
        for drv_fn, expected_cmd in [
            (android_driver, "mobile: setDeviceLocale"),
            (ios_driver, "mobile: setLocale"),
        ]:
            d = drv_fn()
            LocaleManager(d).set_locale("de", "DE")
            cmd = d.execute_script.call_args[0][0]
            assert cmd == expected_cmd


@pytest.mark.unit
class TestSauceLabsProvider:
    def test_build_pool_android(self):
        from mobius.utils.cloud_providers import SauceLabsProvider

        pool = SauceLabsProvider.build_pool(
            [
                {"device": "Samsung Galaxy S23", "platform": "Android", "version": "13"},
                {"device": "Pixel 7", "platform": "Android", "version": "14"},
            ]
        )
        assert len(pool) == 2
        pool.assert_no_port_collisions()

    def test_build_pool_mixed_platforms(self):
        from mobius.utils.cloud_providers import SauceLabsProvider

        pool = SauceLabsProvider.build_pool(
            [
                {"device": "Samsung Galaxy S23", "platform": "Android", "version": "13"},
                {"device": "iPhone 14 Pro", "platform": "iOS", "version": "16"},
            ]
        )
        assert len(pool) == 2

    def test_capabilities_for_android_has_sauce_options(self, monkeypatch):
        from mobius.utils.cloud_providers import SauceLabsProvider

        monkeypatch.setenv("SAUCE_USERNAME", "test_user")
        monkeypatch.setenv("SAUCE_ACCESS_KEY", "test_key")
        pool = SauceLabsProvider.build_pool(
            [
                {"device": "Pixel 6", "platform": "Android", "version": "13"},
            ]
        )
        caps = SauceLabsProvider.capabilities_for(
            pool.devices[0],
            build_name="CI-build-123",
            test_name="login_smoke",
        )
        sauce_opts = caps.to_dict().get("sauce:options", {})
        assert sauce_opts.get("build") == "CI-build-123"
        assert sauce_opts.get("name") == "login_smoke"

    def test_capabilities_for_with_tunnel(self, monkeypatch):
        from mobius.utils.cloud_providers import SauceLabsProvider

        monkeypatch.setenv("SAUCE_USERNAME", "u")
        monkeypatch.setenv("SAUCE_ACCESS_KEY", "k")
        pool = SauceLabsProvider.build_pool(
            [
                {"device": "Pixel 6", "platform": "Android", "version": "13"},
            ]
        )
        caps = SauceLabsProvider.capabilities_for(pool.devices[0], tunnel_id="my-sc-tunnel")
        assert caps.to_dict().get("sauce:options", {}).get("tunnelIdentifier") == "my-sc-tunnel"

    def test_capabilities_warns_without_credentials(self, monkeypatch, caplog):
        import logging

        from mobius.utils.cloud_providers import SauceLabsProvider

        monkeypatch.delenv("SAUCE_USERNAME", raising=False)
        monkeypatch.delenv("SAUCE_ACCESS_KEY", raising=False)
        pool = SauceLabsProvider.build_pool(
            [
                {"device": "Pixel 6", "platform": "Android", "version": "13"},
            ]
        )
        with caplog.at_level(logging.WARNING, logger="mobius.utils.cloud_providers"):
            SauceLabsProvider.capabilities_for(pool.devices[0])
        assert any("SAUCE_USERNAME" in r.message for r in caplog.records)


@pytest.mark.unit
class TestBrowserStackProvider:
    def test_build_pool(self):
        from mobius.utils.cloud_providers import BrowserStackProvider

        pool = BrowserStackProvider.build_pool(
            [
                {"device": "Samsung Galaxy S23", "platform": "Android", "os_version": "13.0"},
                {"device": "iPhone 14", "platform": "iOS", "os_version": "16"},
            ]
        )
        assert len(pool) == 2
        pool.assert_no_port_collisions()

    def test_capabilities_has_bstack_options(self, monkeypatch):
        from mobius.utils.cloud_providers import BrowserStackProvider

        monkeypatch.setenv("BROWSERSTACK_USER", "bs_user")
        monkeypatch.setenv("BROWSERSTACK_KEY", "bs_key")
        pool = BrowserStackProvider.build_pool(
            [
                {"device": "Samsung Galaxy S23", "platform": "Android", "os_version": "13.0"},
            ]
        )
        caps = BrowserStackProvider.capabilities_for(
            pool.devices[0],
            project="mobile-qa",
            build="sprint-42",
            test_name="smoke_test",
        )
        bstack = caps.to_dict().get("bstack:options", {})
        assert bstack["userName"] == "bs_user"
        assert bstack["projectName"] == "mobile-qa"
        assert bstack["buildName"] == "sprint-42"
        assert bstack["sessionName"] == "smoke_test"
        assert bstack["enableBiometric"] is True

    def test_capabilities_warns_without_credentials(self, monkeypatch, caplog):
        import logging

        from mobius.utils.cloud_providers import BrowserStackProvider

        monkeypatch.delenv("BROWSERSTACK_USER", raising=False)
        monkeypatch.delenv("BROWSERSTACK_KEY", raising=False)
        pool = BrowserStackProvider.build_pool(
            [
                {"device": "iPhone 14", "platform": "iOS", "os_version": "16"},
            ]
        )
        with caplog.at_level(logging.WARNING, logger="mobius.utils.cloud_providers"):
            BrowserStackProvider.capabilities_for(pool.devices[0])
        assert any("BROWSERSTACK_USER" in r.message for r in caplog.records)
