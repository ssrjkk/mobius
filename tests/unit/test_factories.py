"""Unit tests — factory_boy."""

from __future__ import annotations

import pytest

from tests.factories.user_factory import MobileUserFactory, ProductFactory, ShippingAddressFactory


@pytest.mark.unit
class TestFactories:
    def test_user_unique_usernames(self):
        users = [MobileUserFactory() for _ in range(10)]
        usernames = [u["username"] for u in users]
        assert len(set(usernames)) == 10

    def test_user_has_required_fields(self):
        u = MobileUserFactory()
        assert all(k in u for k in ["username", "password", "email", "first_name", "last_name"])

    def test_user_password_default(self):
        assert MobileUserFactory()["password"] == "10203040"

    def test_user_email_contains_at(self):
        u = MobileUserFactory()
        assert "@" in u["email"]

    def test_shipping_has_all_fields(self):
        a = ShippingAddressFactory()
        assert all(k in a for k in ["full_name", "address", "city", "zip_code", "country"])

    def test_shipping_country_default(self):
        assert ShippingAddressFactory()["country"] == "United States"

    def test_product_price_positive(self):
        assert ProductFactory()["price"] > 0

    def test_product_category_valid(self):
        valid = {"beauty", "electronics", "clothing", "sports"}
        assert ProductFactory()["category"] in valid

    def test_product_stock_non_negative(self):
        assert ProductFactory()["stock"] >= 0

    def test_product_batch_unique(self):
        products = [ProductFactory() for _ in range(5)]
        assert len(products) == 5
