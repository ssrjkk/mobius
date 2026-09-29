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
from selenium.common.exceptions import InvalidSessionIdException

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

    def test_accept_returns_false_when_both_paths_fail(self):
        """
        'Alert принят' должно означать что alert реально принят. Молчаливое
        проглатывание обеих неудач давало зелёный прогон с необработанным
        системным диалогом, который потом вешал следующий шаг теста.
        """
        self.d.switch_to.alert.accept.side_effect = Exception()
        self.d.execute_script.side_effect = Exception()
        assert self.alerts.accept() is False

    def test_accept_rethrows_dead_session(self):
        self.d.switch_to.alert.accept.side_effect = InvalidSessionIdException(
            "invalid session id 'abc'"
        )
        with pytest.raises(InvalidSessionIdException):
            self.alerts.accept()

    def test_is_present_rethrows_dead_session(self):
        """Протухшая сессия — не «алерта нет», иначе прогон окрашивается в зелёный."""
        type(self.d.switch_to).alert = property(
            lambda self: (_ for _ in ()).throw(OSError("[Errno 10054] remote host closed"))
        )
        with pytest.raises(OSError):
            self.alerts.is_present()

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

    def test_get_text_never_invents_value_from_non_text_response(self):
        """
        Без проверки типа `str(...)` превращает не-текст (например MagicMock из
        кривой заглушки) в похожую на правду строку, и тест начинает сверять
        текст которого не существовало.
        """
        assert self.alerts.get_text() == ""

    def test_get_text_rethrows_dead_session(self):
        type(self.d.switch_to).alert = property(
            lambda self: (_ for _ in ()).throw(InvalidSessionIdException("invalid session id"))
        )
        with pytest.raises(InvalidSessionIdException):
            self.alerts.get_text()

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

    def test_grant_sends_android_permission_constants(self):
        """
        'mobile: changePermissions' принимает только настоящие константы
        android.permission.* (или алиасы all/appops): payload вида ["camera"]
        драйвер отклонял, а тест считал это успехом.
        """
        assert self.perms.grant(Permission.CAMERA) is True
        self.d.execute_script.assert_called_once()
        args = self.d.execute_script.call_args[0]
        assert args[0] == "mobile: changePermissions"
        assert args[1]["permissions"] == ["android.permission.CAMERA"]
        assert args[1]["action"] == "grant"
        assert args[1]["appPackage"] == "com.app.test"

    def test_revoke_sends_all_permission_constants_for_scope(self):
        assert self.perms.revoke(Permission.LOCATION) is True
        args = self.d.execute_script.call_args[0]
        assert args[1]["action"] == "revoke"
        assert args[1]["permissions"] == [
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
        ]

    def test_every_permission_maps_to_real_constants(self):
        from mobius.utils.permissions import _ANDROID_PERMISSIONS

        for perm, names in _ANDROID_PERMISSIONS.items():
            assert names, f"{perm} maps to no permission"
            for name in names:
                assert name.startswith("android.permission."), f"{perm} → {name!r}"

    def test_grant_returns_false_when_driver_rejects(self):
        self.d.execute_script.side_effect = Exception("not supported")
        assert self.perms.grant(Permission.MICROPHONE) is False

    def test_grant_without_package_skips_driver_and_returns_false(self):
        perms = PermissionsManager(MagicMock())
        assert perms.grant(Permission.CAMERA) is False
        perms._driver.execute_script.assert_not_called()

    def test_package_resolved_from_capabilities(self):
        d = MagicMock()
        d.capabilities = {"appium:appPackage": "com.from.caps"}
        assert PermissionsManager(d).grant(Permission.CAMERA) is True
        assert d.execute_script.call_args[0][1]["appPackage"] == "com.from.caps"

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

    def test_handle_permission_dialog_returns_false_when_accept_fails(self):
        """Диалог есть, но нажатие не прошло: 'разрешение обработано' — это False."""
        self.d.switch_to.alert.text = "Allow camera access?"
        self.d.switch_to.alert.accept.side_effect = Exception("not clickable")
        self.d.execute_script.side_effect = Exception("mobile: acceptAlert unsupported")
        assert self.perms.handle_permission_dialog(PermissionAction.ALLOW) is False


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

    def test_get_current_locale_reads_device_prop(self):
        """
        get_settings() локаль не отдаёт, поэтому значение читается getprop'ом.
        Старый тест сверялся с get_settings и «проходил», ничего не прочитав.
        """
        d = android_driver()
        d.execute_script.return_value = "ru-RU"
        loc = LocaleManager(d)
        assert loc.get_current_locale() == {
            "locale": "ru-RU",
            "language": "ru",
            "country": "RU",
            "source": "persist.sys.locale",
        }
        d.get_settings.assert_not_called()

    def test_get_current_locale_accepts_stdout_dict(self):
        d = android_driver()
        d.execute_script.return_value = {"stdout": "en-US\r\n", "stderr": "", "code": 0}
        assert LocaleManager(d).get_current_locale()["locale"] == "en-US"

    def test_get_current_locale_falls_back_to_build_locale(self):
        d = android_driver()
        d.execute_script.side_effect = ["", "de-DE"]
        result = LocaleManager(d).get_current_locale()
        assert result["locale"] == "de-DE"
        assert result["source"] == "ro.product.locale"

    def test_get_current_locale_underscores_are_normalized(self):
        d = ios_driver()
        d.capabilities = {"platformName": "iOS", "appium:locale": "ru_RU"}
        result = LocaleManager(d).get_current_locale()
        assert result["locale"] == "ru-RU"
        assert (result["language"], result["country"]) == ("ru", "RU")
        assert "capabilities" in result["source"]

    def test_get_current_locale_unknown_when_nothing_readable(self):
        d = android_driver()
        d.execute_script.return_value = None
        assert LocaleManager(d).get_current_locale() == {
            "locale": "unknown",
            "language": "unknown",
            "country": "",
            "source": "unavailable",
        }

    def test_get_current_locale_unknown_on_shell_exception(self):
        d = android_driver()
        d.execute_script.side_effect = Exception("shell not supported")
        assert LocaleManager(d).get_current_locale()["source"] == "unavailable"

    def test_get_current_locale_never_invents_value_from_non_text_response(self):
        """
        Ответ не строка и не dict со stdout — значит прочитать нечем. str(out)
        превратил бы любой мусор в «локаль», и локализационный тест сверялся бы
        с собственным mock'ом.
        """
        d = android_driver()
        assert LocaleManager(d).get_current_locale()["source"] == "unavailable"

    def test_get_current_locale_ios_without_capability_is_unknown(self):
        d = ios_driver()
        assert LocaleManager(d).get_current_locale()["locale"] == "unknown"

    def test_get_current_locale_ios_reads_capabilities_not_shell(self):
        d = ios_driver()
        LocaleManager(d).get_current_locale()
        d.execute_script.assert_not_called()


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
        assert "text='Login'" in xpath
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

    def test_open_shade_returns_true(self):
        assert self.notif.open_shade() is True
        self.d.open_notifications.assert_called_once()

    def test_open_shade_returns_false_when_command_rejected(self):
        self.d.open_notifications.side_effect = Exception("not supported")
        assert self.notif.open_shade() is False

    def test_open_shade_rethrows_dead_driver(self):
        self.d.open_notifications.side_effect = InvalidSessionIdException("gone")
        with pytest.raises(InvalidSessionIdException):
            self.notif.open_shade()

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

    def test_get_notifications_text_skips_non_string_text(self):
        e1 = MagicMock()
        e1.text = 42
        self.d.find_elements.return_value = [e1]
        assert self.notif.get_notifications_text() == []

    def test_get_notifications_text_exception_returns_empty_list(self):
        self.d.find_elements.side_effect = Exception("driver error")
        assert self.notif.get_notifications_text() == []

    def test_get_notifications_text_rethrows_dead_driver(self):
        self.d.find_elements.side_effect = InvalidSessionIdException("gone")
        with pytest.raises(InvalidSessionIdException):
            self.notif.get_notifications_text()

    def test_has_notification_containing_true(self):
        e1 = MagicMock()
        e1.text = "Order shipped successfully"
        self.d.find_elements.return_value = [e1]
        assert self.notif.has_notification_containing("shipped") is True

    def test_has_notification_containing_is_case_insensitive(self):
        e1 = MagicMock()
        e1.text = "Order SHIPPED"
        self.d.find_elements.return_value = [e1]
        assert self.notif.has_notification_containing("shipped") is True

    def test_has_notification_containing_false(self):
        e1 = MagicMock()
        e1.text = "Unrelated notification"
        self.d.find_elements.return_value = [e1]
        assert self.notif.has_notification_containing("shipped") is False

    def test_has_notification_containing_opens_shade_once(self):
        self.d.find_elements.return_value = []
        self.notif.has_notification_containing("shipped")
        self.d.open_notifications.assert_called_once()

    def test_has_notification_containing_rejects_empty_text(self):
        # Пустая подстрока совпадает с любым уведомлением — проверка была бы
        # всегда истинной.
        with pytest.raises(ValueError, match="empty text"):
            self.notif.has_notification_containing("")

    def test_has_notification_containing_refuses_vacuous_check(self):
        # Шторка не открылась → мы ничего не посмотрели. False здесь означало
        # «уведомления нет», то есть зелёный негативный ассерт на пустоте.
        self.d.open_notifications.side_effect = Exception("not supported")
        with pytest.raises(AssertionError, match="vacuous"):
            self.notif.has_notification_containing("shipped")
        self.d.find_elements.assert_not_called()

    def test_has_notification_containing_require_shade_false_accepts_blind_result(self):
        self.d.open_notifications.side_effect = Exception("not supported")
        assert self.notif.has_notification_containing("shipped", require_shade=False) is False

    def test_close_shade(self):
        assert self.notif.close_shade() is True
        self.d.press_keycode.assert_called_once_with(4)

    def test_close_shade_returns_false_when_key_rejected(self):
        self.d.press_keycode.side_effect = Exception("no keycode support")
        assert self.notif.close_shade() is False

    def test_close_shade_rethrows_dead_driver(self):
        self.d.press_keycode.side_effect = InvalidSessionIdException("gone")
        with pytest.raises(InvalidSessionIdException):
            self.notif.close_shade()


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
