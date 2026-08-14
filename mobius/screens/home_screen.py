"""Home Screen + Cart Screen — после успешного логина."""

from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy

from mobius.screens.base_screen import BaseScreen
from mobius.utils.gestures import SwipeDirection


class HomeScreen(BaseScreen):
    _MENU = (AppiumBy.ACCESSIBILITY_ID, "open menu")
    _CART = (AppiumBy.ACCESSIBILITY_ID, "cart badge")
    _ITEMS = (AppiumBy.XPATH, '//*[@content-desc="store item"]')
    _SORT = (AppiumBy.ACCESSIBILITY_ID, "sort button")

    @property
    def is_open(self) -> bool:
        return self.is_element_present(self._MENU, timeout=10)

    def get_product_count(self) -> int:
        return len(self.find_all(self._ITEMS))

    def tap_product(self, index: int = 0) -> None:
        items = self.find_all(self._ITEMS)
        if index < len(items):
            items[index].click()

    def tap_cart(self) -> None:
        self.tap(self._CART)

    def tap_sort(self) -> None:
        self.tap(self._SORT)

    def scroll_down(self) -> None:
        self.gestures.swipe(SwipeDirection.UP)

    def scroll_up(self) -> None:
        self.gestures.swipe(SwipeDirection.DOWN)


class CartScreen(BaseScreen):
    _CHECKOUT = (AppiumBy.ACCESSIBILITY_ID, "Proceed To Checkout button")
    _ITEMS = (AppiumBy.XPATH, '//*[@content-desc="cart item"]')
    _TOTAL = (AppiumBy.ACCESSIBILITY_ID, "total price")
    _REMOVE = (AppiumBy.ACCESSIBILITY_ID, "remove item")

    @property
    def is_open(self) -> bool:
        return self.is_element_present(self._CHECKOUT, timeout=5)

    def get_items_count(self) -> int:
        return len(self.find_all(self._ITEMS))

    def get_total_price(self) -> str:
        return self.get_text(self._TOTAL)

    def tap_checkout(self) -> None:
        self.tap(self._CHECKOUT)

    def remove_first_item(self) -> None:
        self.tap(self._REMOVE)
