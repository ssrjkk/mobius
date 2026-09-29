"""
Unit tests — все Screen Objects.

Экран проверяется через единственную границу I/O — объект WebDriver: фиксированный
журнал того, что экран реально сделал с узлами экрана и с драйвером. Никаких
`patch.object(screen, "type_text")`: Screen Object обязан набирать текст, тапать
и читать сам, иначе тест подтверждает заглушку вместо поведения.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from mobius.elements.mobile_element import MobileElement
from mobius.screens.base_screen import BaseScreen
from mobius.screens.home_screen import CartScreen, HomeScreen
from mobius.screens.login_screen import LoginScreen
from mobius.screens.product_screen import CheckoutScreen, ProductDetailScreen
from mobius.types import Locator
from mobius.utils.alerts import SystemAlertHandler
from mobius.utils.clipboard import ClipboardManager
from mobius.utils.device import DeviceActions
from mobius.utils.universal_finder import UniversalFinder

Journal = list[tuple[str, ...]]


class FakeElement:
    """
    WebElement-заглушка: каждое действие пишется в общий журнал.

    Visible+enabled по-настоящему, иначе expected_conditions не прошли бы
    дальше и тест проверял бы заглушку, а не экран.
    """

    def __init__(self, journal: Journal, name: str, text: str = "текст узла") -> None:
        self._journal = journal
        self._name = name
        self.text = text

    def click(self) -> None:
        self._journal.append(("click", self._name))

    def clear(self) -> None:
        self._journal.append(("clear", self._name))

    def send_keys(self, *values: str) -> None:
        self._journal.append(("type", self._name, *values))

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def get_attribute(self, name: str) -> str | None:
        self._journal.append(("attribute", self._name, name))
        return None


def screen_driver(
    journal: Journal,
    *,
    texts: Mapping[Locator, str] | None = None,
    lists: Mapping[Locator, Sequence[Any]] | None = None,
    never_appears: Sequence[Locator] = (),
) -> MagicMock:
    """
    WebDriver, у которого локатор → узел, а все действия видны в журнале.

    `never_appears` отвечает TimeoutException — ровно так же драйвер
    сообщает, что элемент не появился за отведённое экраном время. Иначе
    юнит-тест «экран не открылся» спал бы реальные 5-10 секунд на экран.
    """
    d = MagicMock()
    d.get_window_size.return_value = {"width": 1080, "height": 2400}
    text_map: dict[Locator, str] = dict(texts or {})
    list_map: dict[Locator, list[Any]] = {key: list(value) for key, value in (lists or {}).items()}
    missing = set(never_appears)

    def find_element(by: str, value: str) -> Any:
        locator: Locator = (by, value)
        if locator in missing:
            raise TimeoutException(f"Timed out waiting for {value}")
        return FakeElement(journal, value, text=text_map.get(locator, "текст узла"))

    d.find_element.side_effect = find_element
    d.find_elements.side_effect = lambda by, value: list(list_map.get((by, value), []))
    return d


def drv() -> MagicMock:
    """Голый WebDriver-мок: там, где экрану нужен только сам факт вызова."""
    d = MagicMock()
    d.get_window_size.return_value = {"width": 1080, "height": 2400}
    return d


def swipe_path(d: MagicMock) -> list[tuple[int, int]]:
    """Координаты pointerMove из W3C-послания, которое ушло на драйвер."""
    d.execute.assert_called_once()
    actions = d.execute.call_args.args[1]["actions"][0]["actions"]
    return [(step["x"], step["y"]) for step in actions if step["type"] == "pointerMove"]


class NoAlertsSwitchTo:
    """`switch_to` без системного диалога — состояние свежего экрана."""

    @property
    def alert(self) -> Any:
        raise NoSuchElementException("no alert on a fresh screen")


@pytest.mark.unit
class TestLoginScreen:
    def test_login_types_both_fields_and_taps_login(self) -> None:
        journal: Journal = []
        d = screen_driver(journal)

        LoginScreen(d).login("standard_user", "secret_sauce")

        assert journal == [
            ("clear", "Username input field"),
            ("type", "Username input field", "standard_user"),
            ("clear", "Password input field"),
            ("type", "Password input field", "secret_sauce"),
            ("click", "Login button"),
        ]
        d.hide_keyboard.assert_called_once()

    def test_login_asks_the_driver_only_for_declared_locators(self) -> None:
        journal: Journal = []
        d = screen_driver(journal)

        LoginScreen(d).login("u", "p")

        # набор поля = wait(видимость) + clear + send_keys (MobileElement
        # перенаходит узел на каждое действие), тап = wait(clickable) + click.
        assert d.find_element.call_args_list == [
            call(*LoginScreen._USERNAME),
            call(*LoginScreen._USERNAME),
            call(*LoginScreen._USERNAME),
            call(*LoginScreen._PASSWORD),
            call(*LoginScreen._PASSWORD),
            call(*LoginScreen._PASSWORD),
            call(*LoginScreen._LOGIN_BTN),
            call(*LoginScreen._LOGIN_BTN),
        ]

    def test_enter_username_is_fluent_and_types(self) -> None:
        journal: Journal = []
        screen = LoginScreen(screen_driver(journal))

        assert screen.enter_username("u") is screen

        assert journal == [("clear", "Username input field"), ("type", "Username input field", "u")]

    def test_enter_password_hides_the_keyboard(self) -> None:
        journal: Journal = []
        d = screen_driver(journal)
        screen = LoginScreen(d)

        assert screen.enter_password("p") is screen

        assert journal == [("clear", "Password input field"), ("type", "Password input field", "p")]
        d.hide_keyboard.assert_called_once()

    def test_tap_login_clicks_the_login_button(self) -> None:
        journal: Journal = []
        LoginScreen(screen_driver(journal)).tap_login()

        assert journal == [("click", "Login button")]

    def test_tap_biometrics_clicks_the_biometrics_button(self) -> None:
        journal: Journal = []
        LoginScreen(screen_driver(journal)).tap_biometrics()

        assert journal == [("click", "Login with Biometrics button")]

    def test_get_error_message_reads_the_error_node(self) -> None:
        journal: Journal = []
        d = screen_driver(journal, texts={LoginScreen._ERROR_MSG: "Wrong credentials!"})

        assert LoginScreen(d).get_error_message() == "Wrong credentials!"

    def test_is_error_shown_when_the_node_exists(self) -> None:
        d = screen_driver([])

        assert LoginScreen(d).is_error_shown() is True

        assert d.find_element.call_args.args == LoginScreen._ERROR_MSG

    def test_is_error_shown_false_when_the_node_is_absent(self) -> None:
        d = screen_driver([], never_appears=[LoginScreen._ERROR_MSG])

        assert LoginScreen(d).is_error_shown() is False

        assert d.find_element.call_args.args == LoginScreen._ERROR_MSG


@pytest.mark.unit
class TestHomeScreen:
    def test_product_count_counts_found_nodes(self) -> None:
        items = [FakeElement([], f"store item #{i}") for i in range(5)]
        d = screen_driver([], lists={HomeScreen._ITEMS: items})

        assert HomeScreen(d).get_product_count() == 5

        d.find_elements.assert_called_once_with(*HomeScreen._ITEMS)

    def test_product_count_zero_on_empty_catalog(self) -> None:
        d = screen_driver([], lists={HomeScreen._ITEMS: []})

        assert HomeScreen(d).get_product_count() == 0

    def test_tap_product_clicks_exactly_the_requested_item(self) -> None:
        journal: Journal = []
        items = [FakeElement(journal, f"store item #{i}") for i in range(3)]
        HomeScreen(screen_driver(journal, lists={HomeScreen._ITEMS: items})).tap_product(2)

        assert journal == [("click", "store item #2")]

    def test_tap_product_on_empty_list_clicks_nothing(self) -> None:
        """Раньше это был тест «без падений» — теперь проверяется отсутствие действия."""
        journal: Journal = []
        d = screen_driver(journal, lists={HomeScreen._ITEMS: []})

        HomeScreen(d).tap_product(0)

        assert journal == []
        d.find_elements.assert_called_once_with(*HomeScreen._ITEMS)

    def test_tap_product_out_of_range_clicks_nothing(self) -> None:
        journal: Journal = []
        items = [FakeElement(journal, f"store item #{i}") for i in range(2)]
        screen = HomeScreen(screen_driver(journal, lists={HomeScreen._ITEMS: items}))

        screen.tap_product(7)

        assert journal == []

    def test_tap_cart_and_tap_sort_hit_their_badges(self) -> None:
        journal: Journal = []
        screen = HomeScreen(screen_driver(journal))

        screen.tap_cart()
        screen.tap_sort()

        assert journal == [("click", "cart badge"), ("click", "sort button")]

    def test_scroll_down_moves_the_finger_upwards(self) -> None:
        d = drv()

        HomeScreen(d).scroll_down()

        assert swipe_path(d) == [(540, 1920), (540, 480)]

    def test_scroll_up_moves_the_finger_downwards(self) -> None:
        d = drv()

        HomeScreen(d).scroll_up()

        assert swipe_path(d) == [(540, 480), (540, 1920)]


@pytest.mark.unit
class TestCartScreen:
    def test_items_count_and_total_price(self) -> None:
        journal: Journal = []
        items = [FakeElement(journal, "cart item") for _ in range(2)]
        d = screen_driver(
            journal, lists={CartScreen._ITEMS: items}, texts={CartScreen._TOTAL: "$29.98"}
        )
        screen = CartScreen(d)

        assert screen.get_items_count() == 2
        assert screen.get_total_price() == "$29.98"
        assert d.find_elements.call_args.args == CartScreen._ITEMS

    def test_tap_checkout_and_remove_item(self) -> None:
        journal: Journal = []
        screen = CartScreen(screen_driver(journal))

        screen.tap_checkout()
        screen.remove_first_item()

        assert journal == [
            ("click", "Proceed To Checkout button"),
            ("click", "remove item"),
        ]


@pytest.mark.unit
class TestProductDetailScreen:
    def test_title_price_and_quantity_are_read_from_their_nodes(self) -> None:
        d = screen_driver(
            [],
            texts={
                ProductDetailScreen._TITLE: "Sauce Backpack",
                ProductDetailScreen._PRICE: "$29.99",
                ProductDetailScreen._COUNTER: "3",
            },
        )
        screen = ProductDetailScreen(d)

        assert screen.get_title() == "Sauce Backpack"
        assert screen.get_price() == "$29.99"
        assert screen.get_quantity() == 3

    def test_quantity_is_a_real_number(self) -> None:
        d = screen_driver([], texts={ProductDetailScreen._COUNTER: "12"})

        quantity = ProductDetailScreen(d).get_quantity()

        assert quantity == 12
        assert isinstance(quantity, int)

    @pytest.mark.parametrize("rendered", ["", "$29.99", "3 items"])
    def test_unparseable_counter_says_what_was_on_screen(self, rendered: str) -> None:
        """
        Голый int() бросает "invalid literal for int()" без упоминания экрана —
        по такому провалу не отличить пропавший счётчик от изменившегося формата
        текста или локатора не туда.
        """
        d = screen_driver([], texts={ProductDetailScreen._COUNTER: rendered})

        with pytest.raises(ValueError, match="counter amount"):
            ProductDetailScreen(d).get_quantity()

    def test_add_to_cart_clicks_the_button(self) -> None:
        journal: Journal = []
        ProductDetailScreen(screen_driver(journal)).add_to_cart()

        assert journal == [("click", "Add To Cart button")]

    @pytest.mark.parametrize("times", [1, 3])
    def test_increase_quantity_taps_plus_that_many_times(self, times: int) -> None:
        journal: Journal = []
        ProductDetailScreen(screen_driver(journal)).increase_quantity(times)

        assert journal == [("click", "counter plus button")] * times

    def test_decrease_quantity_taps_minus_that_many_times(self) -> None:
        journal: Journal = []
        ProductDetailScreen(screen_driver(journal)).decrease_quantity(2)

        assert journal == [("click", "counter minus button")] * 2


@pytest.mark.unit
class TestCheckoutScreen:
    def test_fill_shipping_types_every_field_in_screen_order(self) -> None:
        journal: Journal = []
        d = screen_driver(journal)

        CheckoutScreen(d).fill_shipping("John", "123 St", "NYC", "10001", "US")

        assert journal == [
            ("clear", "Full Name* input field"),
            ("type", "Full Name* input field", "John"),
            ("clear", "Address Line 1* input field"),
            ("type", "Address Line 1* input field", "123 St"),
            ("clear", "City* input field"),
            ("type", "City* input field", "NYC"),
            ("clear", "Zip Code* input field"),
            ("type", "Zip Code* input field", "10001"),
            ("clear", "Country* input field"),
            ("type", "Country* input field", "US"),
        ]
        d.hide_keyboard.assert_called_once()

    def test_fill_shipping_returns_itself_for_chaining(self) -> None:
        screen = CheckoutScreen(screen_driver([]))

        assert screen.fill_shipping("a", "b", "c", "d", "e") is screen

    def test_tap_to_payment(self) -> None:
        journal: Journal = []
        CheckoutScreen(screen_driver(journal)).tap_to_payment()

        assert journal == [("click", "To Payment button")]

    def test_error_message_is_read_from_the_error_node(self) -> None:
        d = screen_driver([], texts={CheckoutScreen._ERROR_MSG: "Required field"})
        screen = CheckoutScreen(d)

        assert screen.is_error_shown() is True
        assert screen.get_error_message() == "Required field"

    def test_no_error_when_the_error_node_is_absent(self) -> None:
        d = screen_driver([], never_appears=[CheckoutScreen._ERROR_MSG])

        assert CheckoutScreen(d).is_error_shown() is False


@pytest.mark.unit
class TestScreenSignatureElements:
    """is_open каждого экрана завязан на его собственный уникальный узел."""

    SCREENS: list[tuple[Callable[..., BaseScreen], Locator]] = [
        (LoginScreen, LoginScreen._LOGIN_BTN),
        (HomeScreen, HomeScreen._MENU),
        (CartScreen, CartScreen._CHECKOUT),
        (ProductDetailScreen, ProductDetailScreen._ADD_TO_CART),
        (CheckoutScreen, CheckoutScreen._FULL_NAME),
    ]

    @pytest.mark.parametrize(("screen_cls", "signature"), SCREENS)
    def test_is_open_true_for_its_own_element(
        self, screen_cls: Callable[..., BaseScreen], signature: Locator
    ) -> None:
        journal: Journal = []
        d = screen_driver(journal)

        assert screen_cls(d).is_open is True

        assert d.find_element.call_args.args == signature
        assert journal == []

    @pytest.mark.parametrize(("screen_cls", "signature"), SCREENS)
    def test_is_open_false_when_signature_element_never_shows(
        self, screen_cls: Callable[..., BaseScreen], signature: Locator
    ) -> None:
        d = screen_driver([], never_appears=[signature])

        assert screen_cls(d).is_open is False

        assert d.find_element.call_args.args == signature


@pytest.mark.unit
class TestBaseScreenMethods:
    """Методы BaseScreen через конкретный экран: проверяем запросы к драйверу."""

    def setup_method(self) -> None:
        self.d = drv()
        self.s = LoginScreen(self.d)

    def test_find_returns_a_mobile_element_bound_to_this_driver(self) -> None:
        result = self.s.find(("id", "x"))

        assert isinstance(result, MobileElement)
        assert result._driver is self.d
        assert result._locator == ("id", "x")

    def test_find_all_returns_a_materialised_list(self) -> None:
        self.d.find_elements.return_value = iter([MagicMock(), MagicMock()])

        result = self.s.find_all(("xpath", "//btn"))

        assert len(result) == 2
        self.d.find_elements.assert_called_once_with("xpath", "//btn")

    def test_find_by_text_builds_the_text_or_label_xpath(self) -> None:
        self.s.find_by_text("Login")

        self.d.find_element.assert_called_once_with(
            AppiumBy.XPATH, "//*[@text='Login' or @label='Login']"
        )

    def test_find_by_id_uses_the_resource_id_directly(self) -> None:
        self.s.find_by_id("com.app:id/btn")

        self.d.find_element.assert_called_once_with(AppiumBy.ID, "com.app:id/btn")

    def test_find_by_accessibility_uses_the_label(self) -> None:
        self.s.find_by_accessibility("Login button")

        self.d.find_element.assert_called_once_with(AppiumBy.ACCESSIBILITY_ID, "Login button")

    def test_tap_clicks_the_element(self) -> None:
        journal: Journal = []
        LoginScreen(screen_driver(journal)).tap((AppiumBy.ID, "btn"))

        assert journal == [("click", "btn")]

    def test_type_text_clears_then_types(self) -> None:
        journal: Journal = []
        LoginScreen(screen_driver(journal)).type_text((AppiumBy.ID, "input"), "hello")

        assert journal == [("clear", "input"), ("type", "input", "hello")]

    def test_get_text_returns_the_node_text(self) -> None:
        journal: Journal = []
        d = screen_driver(journal, texts={(AppiumBy.ID, "label"): "some text"})

        assert LoginScreen(d).get_text((AppiumBy.ID, "label")) == "some text"

    def test_is_element_present_true(self) -> None:
        assert LoginScreen(screen_driver([])).is_element_present((AppiumBy.ID, "x")) is True

    def test_is_element_present_absent_element_is_false_after_waiting(self) -> None:
        """Настоящий WebDriverWait: элемент не появился за 1s → False после ~1s ожидания."""
        d = drv()
        d.find_element.side_effect = NoSuchElementException("нет такого")
        screen = LoginScreen(d)

        started = time.monotonic()
        assert screen.is_element_present((AppiumBy.ID, "x"), timeout=1) is False

        assert time.monotonic() - started >= 1.0
        assert d.find_element.call_count >= 2

    def test_scroll_to_text_builds_the_ui_scrollable_selector(self) -> None:
        self.s.scroll_to_text("Add To Cart")

        self.d.find_element.assert_called_once_with(
            AppiumBy.ANDROID_UIAUTOMATOR,
            "new UiScrollable(new UiSelector().scrollable(true))"
            '.scrollIntoView(new UiSelector().text("Add To Cart"))',
        )

    def test_hide_keyboard_reports_a_hidden_keyboard_in_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Раньше тест только «не падал»; теперь проверяется наблюдаемое состояние."""
        d = drv()
        d.hide_keyboard.side_effect = Exception("no keyboard")
        screen = LoginScreen(d)

        with caplog.at_level(logging.DEBUG, logger="mobius.screens.base_screen"):
            screen.hide_keyboard()

        records = [r for r in caplog.records if r.name == "mobius.screens.base_screen"]
        d.hide_keyboard.assert_called_once()
        assert [r.levelno for r in records] == [logging.DEBUG]
        assert "hide_keyboard" in records[0].getMessage()

    def test_go_back(self) -> None:
        self.s.go_back()

        self.d.back.assert_called_once()

    def test_attach_screenshot_on_failure_pulls_both_artifacts(self) -> None:
        d = drv()
        d.get_screenshot_as_png.return_value = b"\x89PNG fake"
        d.page_source = "<hierarchy />"

        with patch("mobius.utils.screenshot.allure.attach") as attach:
            LoginScreen(d).attach_screenshot_on_failure()

        d.get_screenshot_as_png.assert_called_once()
        assert attach.call_count == 2


@pytest.mark.unit
class TestBaseScreenUniversalAttributes:
    """
    Любой Screen Object автоматически получает universal-инструменты —
    не только конкретные для одного SUT (find_by_id и т.п.), но и
    app-agnostic device/alerts/clipboard/finder.
    """

    def setup_method(self) -> None:
        self.d = drv()
        self.s = LoginScreen(self.d)

    def test_has_device_actions(self) -> None:
        assert isinstance(self.s.device, DeviceActions)

    def test_has_alerts_handler(self) -> None:
        assert isinstance(self.s.alerts, SystemAlertHandler)

    def test_has_clipboard_manager(self) -> None:
        assert isinstance(self.s.clipboard, ClipboardManager)

    def test_has_universal_finder(self) -> None:
        assert isinstance(self.s.finder, UniversalFinder)

    def test_universal_tools_share_the_screen_driver(self) -> None:
        tools: list[Any] = [self.s.device, self.s.alerts, self.s.clipboard, self.s.finder]

        for tool in tools:
            assert tool._driver is self.d

    def test_finder_reports_text_present_on_screen(self) -> None:
        assert self.s.finder.screen_contains_text("anything") is True

        by, xpath = self.d.find_element.call_args.args
        assert by == AppiumBy.XPATH
        assert "'anything'" in xpath

    def test_finder_reports_absent_text_as_false(self) -> None:
        d = drv()
        d.find_element.side_effect = NoSuchElementException("нет такого текста")

        assert LoginScreen(d).finder.screen_contains_text("anything") is False

    def test_alerts_accept_if_present_on_fresh_screen(self) -> None:
        """
        Свободный экран без alert: accept_if_present обязан ответить False и
        ничего не отправить драйверу. `switch_to` подменяем на атрибуте одного
        мок-объекта — глобальный класс MagicMock трогать нельзя.
        """
        d = drv()
        d.switch_to = NoAlertsSwitchTo()

        assert LoginScreen(d).alerts.accept_if_present() is False

        d.execute_script.assert_not_called()

    def test_fresh_mock_still_has_an_untouched_switch_to(self) -> None:
        """Защита от регресса: предыдущий тест не должен портить другие мок-драйверы."""
        assert isinstance(drv().switch_to, MagicMock)
