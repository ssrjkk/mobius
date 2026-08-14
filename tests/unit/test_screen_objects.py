"""Unit tests — все Screen Objects."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mobius.screens.home_screen import CartScreen, HomeScreen
from mobius.screens.login_screen import LoginScreen
from mobius.screens.product_screen import CheckoutScreen, ProductDetailScreen


def drv():
    d = MagicMock()
    d.get_window_size.return_value = {"width": 1080, "height": 2400}
    return d


@pytest.mark.unit
class TestLoginScreen:
    def setup_method(self):
        self.s = LoginScreen(drv())

    def test_login_calls_type_twice(self):
        with (
            patch.object(self.s, "type_text") as m,
            patch.object(self.s, "tap"),
            patch.object(self.s, "hide_keyboard"),
        ):
            self.s.login("u", "p")
        assert m.call_count == 2

    def test_enter_username_returns_self(self):
        with patch.object(self.s, "type_text"):
            assert self.s.enter_username("u") is self.s

    def test_enter_password_returns_self(self):
        with patch.object(self.s, "type_text"), patch.object(self.s, "hide_keyboard"):
            assert self.s.enter_password("p") is self.s

    def test_is_open_true(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_open is True

    def test_is_open_false(self):
        with patch.object(self.s, "is_element_present", return_value=False):
            assert self.s.is_open is False

    def test_is_error_shown_true(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_error_shown() is True

    def test_is_error_shown_false(self):
        with patch.object(self.s, "is_element_present", return_value=False):
            assert self.s.is_error_shown() is False

    def test_get_error(self):
        with patch.object(self.s, "get_text", return_value="Bad creds"):
            assert self.s.get_error_message() == "Bad creds"

    def test_tap_biometrics(self):
        with patch.object(self.s, "tap") as m:
            self.s.tap_biometrics()
        m.assert_called_once()

    def test_tap_login(self):
        with patch.object(self.s, "tap") as m:
            self.s.tap_login()
        m.assert_called_once()


@pytest.mark.unit
class TestHomeScreen:
    def setup_method(self):
        self.s = HomeScreen(drv())

    def test_is_open_true(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_open is True

    def test_is_open_false(self):
        with patch.object(self.s, "is_element_present", return_value=False):
            assert self.s.is_open is False

    def test_product_count(self):
        with patch.object(self.s, "find_all", return_value=[MagicMock()] * 5):
            assert self.s.get_product_count() == 5

    def test_product_count_empty(self):
        with patch.object(self.s, "find_all", return_value=[]):
            assert self.s.get_product_count() == 0

    def test_tap_product_correct_index(self):
        items = [MagicMock() for _ in range(3)]
        with patch.object(self.s, "find_all", return_value=items):
            self.s.tap_product(2)
        items[2].click.assert_called_once()

    def test_tap_product_empty_no_crash(self):
        with patch.object(self.s, "find_all", return_value=[]):
            self.s.tap_product(0)

    def test_tap_cart(self):
        with patch.object(self.s, "tap") as m:
            self.s.tap_cart()
        m.assert_called_once()

    def test_tap_sort(self):
        with patch.object(self.s, "tap") as m:
            self.s.tap_sort()
        m.assert_called_once()

    def test_scroll_down(self):
        with patch.object(self.s.gestures, "swipe") as m:
            self.s.scroll_down()
        m.assert_called_once()

    def test_scroll_up(self):
        with patch.object(self.s.gestures, "swipe") as m:
            self.s.scroll_up()
        m.assert_called_once()


@pytest.mark.unit
class TestCartScreen:
    def setup_method(self):
        self.s = CartScreen(drv())

    def test_is_open_true(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_open is True

    def test_items_count(self):
        with patch.object(self.s, "find_all", return_value=[MagicMock()] * 2):
            assert self.s.get_items_count() == 2

    def test_total_price(self):
        with patch.object(self.s, "get_text", return_value="$29.98"):
            assert self.s.get_total_price() == "$29.98"

    def test_tap_checkout(self):
        with patch.object(self.s, "tap") as m:
            self.s.tap_checkout()
        m.assert_called_once()

    def test_remove_first_item(self):
        with patch.object(self.s, "tap") as m:
            self.s.remove_first_item()
        m.assert_called_once()


@pytest.mark.unit
class TestProductDetailScreen:
    def setup_method(self):
        self.s = ProductDetailScreen(drv())

    def test_is_open_true(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_open is True

    def test_get_title(self):
        with patch.object(self.s, "get_text", return_value="Sauce Backpack"):
            assert self.s.get_title() == "Sauce Backpack"

    def test_get_price(self):
        with patch.object(self.s, "get_text", return_value="$29.99"):
            assert self.s.get_price() == "$29.99"

    def test_get_quantity(self):
        with patch.object(self.s, "get_text", return_value="3"):
            assert self.s.get_quantity() == 3

    def test_add_to_cart(self):
        with patch.object(self.s, "tap") as m:
            self.s.add_to_cart()
        m.assert_called_once()

    def test_increase_quantity(self):
        with patch.object(self.s, "tap") as m:
            self.s.increase_quantity(3)
        assert m.call_count == 3

    def test_decrease_quantity(self):
        with patch.object(self.s, "tap") as m:
            self.s.decrease_quantity(2)
        assert m.call_count == 2


@pytest.mark.unit
class TestCheckoutScreen:
    def setup_method(self):
        self.s = CheckoutScreen(drv())

    def test_is_open_true(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_open is True

    def test_fill_shipping_types_5_fields(self):
        with patch.object(self.s, "type_text") as m, patch.object(self.s, "hide_keyboard"):
            self.s.fill_shipping("John", "123 St", "NYC", "10001", "US")
        assert m.call_count == 5

    def test_fill_returns_self(self):
        with patch.object(self.s, "type_text"), patch.object(self.s, "hide_keyboard"):
            assert self.s.fill_shipping("a", "b", "c", "d", "e") is self.s

    def test_tap_to_payment(self):
        with patch.object(self.s, "tap") as m:
            self.s.tap_to_payment()
        m.assert_called_once()

    def test_is_error_shown(self):
        with patch.object(self.s, "is_element_present", return_value=True):
            assert self.s.is_error_shown() is True

    def test_get_error_message(self):
        with patch.object(self.s, "get_text", return_value="Required field"):
            assert self.s.get_error_message() == "Required field"


@pytest.mark.unit
class TestBaseScreenMethods:
    """Покрываем BaseScreen методы через конкретный LoginScreen."""

    def setup_method(self):
        self.d = drv()
        self.s = LoginScreen(self.d)

    def test_find(self):
        from mobius.elements.mobile_element import MobileElement

        result = self.s.find(("id", "x"))
        assert isinstance(result, MobileElement)

    def test_find_all(self):
        self.d.find_elements.return_value = [MagicMock()]
        result = self.s.find_all(("xpath", "//btn"))
        assert len(result) == 1

    def test_find_by_text(self):
        self.s.find_by_text("Login")
        self.d.find_element.assert_called_once()

    def test_find_by_id(self):
        self.s.find_by_id("com.app:id/btn")
        self.d.find_element.assert_called_once()

    def test_find_by_accessibility(self):
        self.s.find_by_accessibility("Login button")
        self.d.find_element.assert_called_once()

    def test_tap_calls_click(self):
        mock_elem = MagicMock()
        with (
            patch.object(self.s.wait, "wait_for_element_clickable", return_value=mock_elem),
            patch("mobius.elements.mobile_element.WebDriverWait") as WM,
        ):
            WM.return_value.until.return_value = mock_elem
            self.s.tap(("id", "btn"))
        mock_elem.click.assert_called()

    def test_type_text(self):
        mock_elem = MagicMock()
        with (
            patch.object(self.s.wait, "wait_for_element_visible", return_value=mock_elem),
            patch("mobius.elements.mobile_element.WebDriverWait") as WM,
        ):
            WM.return_value.until.return_value = mock_elem
            self.s.type_text(("id", "input"), "hello")
        mock_elem.clear.assert_called_once()
        mock_elem.send_keys.assert_called_once_with("hello")

    def test_get_text(self):
        mock_elem = MagicMock()
        mock_elem.text = "some text"  # атрибут, не метод
        with patch("mobius.elements.mobile_element.WebDriverWait") as W:
            W.return_value.until.return_value = mock_elem
            result = self.s.get_text(("id", "label"))
        assert result == "some text"

    def test_is_element_present_true(self):
        with patch("mobius.screens.base_screen.WebDriverWait") as W:
            W.return_value.until.return_value = MagicMock()
            assert self.s.is_element_present(("id", "x"), timeout=1) is True

    def test_is_element_present_false(self):
        with patch("mobius.screens.base_screen.WebDriverWait") as W:
            W.return_value.until.side_effect = Exception()
            assert self.s.is_element_present(("id", "x"), timeout=1) is False

    def test_scroll_to_text(self):
        self.s.scroll_to_text("Add To Cart")
        self.d.find_element.assert_called_once()

    def test_hide_keyboard_no_crash(self):
        self.d.hide_keyboard.side_effect = Exception("no keyboard")
        self.s.hide_keyboard()

    def test_go_back(self):
        self.s.go_back()
        self.d.back.assert_called_once()

    def test_attach_screenshot_on_failure(self):
        with (
            patch.object(self.s.screenshot, "attach_to_allure") as ss,
            patch.object(self.s.screenshot, "attach_page_source"),
        ):
            self.s.attach_screenshot_on_failure()
        ss.assert_called_once()


@pytest.mark.unit
class TestBaseScreenUniversalAttributes:
    """
    Любой Screen Object автоматически получает universal-инструменты —
    не только конкретные для одного SUT (find_by_id и т.п.), но и
    app-agnostic device/alerts/clipboard/finder.
    """

    def setup_method(self):
        self.s = LoginScreen(drv())

    def test_has_device_actions(self):
        from mobius.utils.device import DeviceActions

        assert isinstance(self.s.device, DeviceActions)

    def test_has_alerts_handler(self):
        from mobius.utils.alerts import SystemAlertHandler

        assert isinstance(self.s.alerts, SystemAlertHandler)

    def test_has_clipboard_manager(self):
        from mobius.utils.clipboard import ClipboardManager

        assert isinstance(self.s.clipboard, ClipboardManager)

    def test_has_universal_finder(self):
        from mobius.utils.universal_finder import UniversalFinder

        assert isinstance(self.s.finder, UniversalFinder)

    def test_device_shares_same_driver(self):
        assert self.s.device._driver is self.s._driver

    def test_finder_can_screen_contains_text(self):
        self.s._driver.find_element.return_value = MagicMock()
        assert self.s.finder.screen_contains_text("anything") is True

    def test_alerts_accept_if_present_on_fresh_screen(self):
        # На новом экране без alert — accept_if_present должен быть безопасен
        type(self.s._driver.switch_to).alert = property(
            lambda self: (_ for _ in ()).throw(Exception())
        )
        assert self.s.alerts.accept_if_present() is False
