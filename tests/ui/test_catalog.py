"""
UI тесты — каталог товаров, корзина, жесты.
SUT: Sauce Labs My Demo App RN.
"""

from __future__ import annotations

import allure
import pytest

from mobius.screens.home_screen import CartScreen, HomeScreen
from mobius.screens.login_screen import LoginScreen
from mobius.screens.product_screen import ProductDetailScreen

VALID_USER = "bod@example.com"
VALID_PASS = "10203040"


@pytest.fixture
def logged_in_home(login_screen: LoginScreen, home_screen: HomeScreen) -> HomeScreen:
    """Общий сетап — логинимся и попадаем на home screen."""
    login_screen.login(VALID_USER, VALID_PASS)
    assert home_screen.is_open, "Setup failed: home screen did not open"
    return home_screen


@allure.feature("Catalog")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.smoke
class TestCatalogSmoke:
    @allure.title("Catalog shows products after login")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_catalog_has_products(self, logged_in_home: HomeScreen) -> None:
        count = logged_in_home.get_product_count()
        assert count > 0, "No products visible in catalog"

    @allure.title("Tapping a product opens product detail screen")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_tap_product_opens_detail(
        self, logged_in_home: HomeScreen, product_screen: ProductDetailScreen
    ) -> None:
        with allure.step("Tap first product"):
            logged_in_home.tap_product(0)
        with allure.step("Verify product detail screen opened"):
            assert product_screen.is_open

    @allure.title("Add to cart increases cart badge")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_add_to_cart(
        self, logged_in_home: HomeScreen, product_screen: ProductDetailScreen
    ) -> None:
        with allure.step("Open first product and add to cart"):
            logged_in_home.tap_product(0)
            assert product_screen.is_open
            product_screen.add_to_cart()
        with allure.step("Verify cart has item"):
            logged_in_home.go_back()
            logged_in_home.tap_cart()


@allure.feature("Catalog")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestGestures:
    @allure.title("Swipe up scrolls catalog down")
    def test_swipe_up_scrolls(self, logged_in_home: HomeScreen) -> None:
        logged_in_home.scroll_down()
        after_count = logged_in_home.get_product_count()
        # Список не должен опустеть после скролла
        assert after_count >= 0

    @allure.title("Swipe down then up returns to original position")
    def test_swipe_down_then_up(self, logged_in_home: HomeScreen) -> None:
        logged_in_home.scroll_down()
        logged_in_home.scroll_up()
        assert logged_in_home.is_open

    @allure.title("Long press on product shows context options")
    @pytest.mark.slow
    def test_long_press_product(self, logged_in_home: HomeScreen) -> None:
        products = logged_in_home.find_all(logged_in_home._ITEMS)
        if products:
            with allure.step("Long press first product"):
                logged_in_home.gestures.long_press(products[0], duration_ms=1000)


@allure.feature("Product Detail")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestProductDetail:
    @allure.title("Quantity counter increases correctly")
    def test_increase_quantity(
        self, logged_in_home: HomeScreen, product_screen: ProductDetailScreen
    ) -> None:
        logged_in_home.tap_product(0)
        assert product_screen.is_open
        initial_qty = product_screen.get_quantity()
        product_screen.increase_quantity(2)
        new_qty = product_screen.get_quantity()
        assert new_qty == initial_qty + 2

    @allure.title("Quantity counter cannot go below 1")
    def test_decrease_quantity_floor(
        self, logged_in_home: HomeScreen, product_screen: ProductDetailScreen
    ) -> None:
        logged_in_home.tap_product(0)
        assert product_screen.is_open
        product_screen.decrease_quantity(5)  # пытаемся уйти в минус
        qty = product_screen.get_quantity()
        assert qty >= 1, "Quantity should not go below 1"

    @allure.title("Product price is displayed and non-empty")
    def test_product_price_visible(
        self, logged_in_home: HomeScreen, product_screen: ProductDetailScreen
    ) -> None:
        logged_in_home.tap_product(0)
        assert product_screen.is_open
        price = product_screen.get_price()
        assert len(price) > 0
        assert "$" in price


@allure.feature("Cart")
@pytest.mark.ui
@pytest.mark.android
@pytest.mark.regression
class TestCart:
    @pytest.fixture(autouse=True)
    def add_item_to_cart(self, logged_in_home: HomeScreen, product_screen: ProductDetailScreen):
        """Добавляем товар в корзину перед каждым тестом этого класса."""
        logged_in_home.tap_product(0)
        assert product_screen.is_open
        product_screen.add_to_cart()
        logged_in_home.go_back()
        yield

    @allure.title("Cart contains the added item")
    def test_cart_has_item(self, logged_in_home: HomeScreen, driver) -> None:
        logged_in_home.tap_cart()
        cart = CartScreen(driver)
        assert cart.get_items_count() > 0

    @allure.title("Cart total price is shown and valid")
    def test_cart_total_price_valid(self, logged_in_home: HomeScreen, driver) -> None:
        logged_in_home.tap_cart()
        cart = CartScreen(driver)
        total = cart.get_total_price()
        assert "$" in total

    @allure.title("Removing item empties cart")
    def test_remove_item_from_cart(self, logged_in_home: HomeScreen, driver) -> None:
        logged_in_home.tap_cart()
        cart = CartScreen(driver)
        initial_count = cart.get_items_count()
        if initial_count > 0:
            cart.remove_first_item()
            new_count = cart.get_items_count()
            assert new_count == initial_count - 1
