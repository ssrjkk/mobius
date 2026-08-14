"""Product Detail и Checkout screens."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from mobius.screens.base_screen import BaseScreen


class ProductDetailScreen(BaseScreen):
    _TITLE = (AppiumBy.ACCESSIBILITY_ID, "product title")
    _PRICE = (AppiumBy.ACCESSIBILITY_ID, "product price")
    _ADD_TO_CART = (AppiumBy.ACCESSIBILITY_ID, "Add To Cart button")
    _COUNTER = (AppiumBy.ACCESSIBILITY_ID, "counter amount")
    _MINUS = (AppiumBy.ACCESSIBILITY_ID, "counter minus button")
    _PLUS = (AppiumBy.ACCESSIBILITY_ID, "counter plus button")

    @property
    def is_open(self) -> bool:
        return self.is_element_present(self._ADD_TO_CART, timeout=5)

    def get_title(self) -> str:
        return self.get_text(self._TITLE)

    def get_price(self) -> str:
        return self.get_text(self._PRICE)

    def get_quantity(self) -> int:
        return int(self.get_text(self._COUNTER))

    def add_to_cart(self) -> None:
        self.tap(self._ADD_TO_CART)

    def increase_quantity(self, times: int = 1) -> None:
        for _ in range(times):
            self.tap(self._PLUS)

    def decrease_quantity(self, times: int = 1) -> None:
        for _ in range(times):
            self.tap(self._MINUS)


class CheckoutScreen(BaseScreen):
    _FULL_NAME = (AppiumBy.ACCESSIBILITY_ID, "Full Name* input field")
    _ADDRESS = (AppiumBy.ACCESSIBILITY_ID, "Address Line 1* input field")
    _CITY = (AppiumBy.ACCESSIBILITY_ID, "City* input field")
    _ZIP = (AppiumBy.ACCESSIBILITY_ID, "Zip Code* input field")
    _COUNTRY = (AppiumBy.ACCESSIBILITY_ID, "Country* input field")
    _PAYMENT_BTN = (AppiumBy.ACCESSIBILITY_ID, "To Payment button")
    _ERROR_MSG = (AppiumBy.XPATH, '//*[@content-desc="error message"]')

    @property
    def is_open(self) -> bool:
        return self.is_element_present(self._FULL_NAME, timeout=5)

    def fill_shipping(
        self,
        full_name: str,
        address: str,
        city: str,
        zip_code: str,
        country: str,
    ) -> CheckoutScreen:
        self.type_text(self._FULL_NAME, full_name)
        self.type_text(self._ADDRESS, address)
        self.type_text(self._CITY, city)
        self.type_text(self._ZIP, zip_code)
        self.type_text(self._COUNTRY, country)
        self.hide_keyboard()
        return self

    def tap_to_payment(self) -> None:
        self.tap(self._PAYMENT_BTN)

    def is_error_shown(self) -> bool:
        return self.is_element_present(self._ERROR_MSG, timeout=3)

    def get_error_message(self) -> str:
        return self.get_text(self._ERROR_MSG)
