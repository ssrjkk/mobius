"""
API тесты — dummyjson.com (реальный публичный REST API для мобильного SUT).

Запуск с моками (по умолчанию, без сети):
    pytest tests/api/

Запуск против реального dummyjson.com:
    pytest tests/api/ --live-api
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.api
class TestAuth:
    def test_login_valid_credentials(self, api_client: httpx.Client) -> None:
        r = api_client.post("/auth/login", json={"username": "emilys", "password": "emilyspass"})
        assert r.status_code == 200

    def test_login_returns_access_token(self, api_client: httpx.Client) -> None:
        r = api_client.post("/auth/login", json={"username": "emilys", "password": "emilyspass"})
        data = r.json()
        assert "accessToken" in data
        assert len(data["accessToken"]) > 20

    def test_login_returns_refresh_token(self, api_client: httpx.Client) -> None:
        r = api_client.post("/auth/login", json={"username": "emilys", "password": "emilyspass"})
        assert "refreshToken" in r.json()

    def test_login_tokens_are_different(self, api_client: httpx.Client) -> None:
        r = api_client.post("/auth/login", json={"username": "emilys", "password": "emilyspass"})
        data = r.json()
        assert data["accessToken"] != data["refreshToken"]

    def test_login_returns_user_info(self, api_client: httpx.Client) -> None:
        r = api_client.post("/auth/login", json={"username": "emilys", "password": "emilyspass"})
        data = r.json()
        assert "id" in data
        assert "username" in data
        assert "@" in data["email"]

    def test_access_token_is_jwt(self, api_client: httpx.Client) -> None:
        """JWT формат: три части разделённые точкой."""
        r = api_client.post("/auth/login", json={"username": "emilys", "password": "emilyspass"})
        parts = r.json()["accessToken"].split(".")
        assert len(parts) == 3, "accessToken is not valid JWT"

    def test_login_invalid_credentials_400(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/auth/login", json={"username": "wrong_user", "password": "wrong_pass"}
        )
        assert r.status_code == 400

    def test_login_invalid_returns_error_message(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/auth/login", json={"username": "wrong_user", "password": "wrong_pass"}
        )
        assert "message" in r.json()


@pytest.mark.api
class TestUsers:
    def test_get_users_200(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users")
        assert r.status_code == 200

    def test_users_list_structure(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users")
        data = r.json()
        assert "users" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    def test_users_total_positive(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users")
        assert r.json()["total"] > 0

    def test_users_have_required_fields(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users")
        for u in r.json()["users"]:
            assert "id" in u
            assert "firstName" in u
            assert "email" in u
            assert "@" in u["email"]

    def test_get_user_by_id(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users/1")
        assert r.status_code == 200
        assert r.json()["id"] == 1

    def test_get_user_email_valid(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users/1")
        assert "@" in r.json()["email"]

    def test_get_user_not_found_404(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users/999")
        assert r.status_code == 404

    def test_search_users_returns_results(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users/search", params={"q": "Emily"})
        assert r.status_code == 200
        assert len(r.json()["users"]) > 0

    def test_create_user_201(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/users/add",
            json={
                "firstName": "Sergey",
                "lastName": "Sitnikov",
                "email": "sergey@qa.dev",
                "age": 25,
                "gender": "male",
                "username": "ssrjkk",
            },
        )
        assert r.status_code == 201

    def test_create_user_gets_id(self, api_client: httpx.Client) -> None:
        r = api_client.post(
            "/users/add",
            json={
                "firstName": "Test",
                "lastName": "User",
                "email": "test@test.com",
                "age": 30,
                "gender": "male",
                "username": "testuser",
            },
        )
        assert r.json()["id"] > 0

    def test_update_user(self, api_client: httpx.Client) -> None:
        r = api_client.put("/users/1", json={"firstName": "Updated"})
        assert r.status_code == 200
        assert r.json()["firstName"] == "Updated"

    def test_delete_user(self, api_client: httpx.Client) -> None:
        r = api_client.delete("/users/1")
        assert r.status_code == 200
        assert r.json()["isDeleted"] is True

    def test_users_unique_emails(self, api_client: httpx.Client) -> None:
        r = api_client.get("/users")
        emails = [u["email"] for u in r.json()["users"]]
        assert len(emails) == len(set(emails)), "Duplicate emails in users"


@pytest.mark.api
class TestProducts:
    def test_get_products_200(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products")
        assert r.status_code == 200

    def test_products_list_structure(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products")
        data = r.json()
        assert "products" in data
        assert "total" in data

    def test_products_price_positive(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products")
        for p in r.json()["products"]:
            assert p["price"] > 0, f"Product {p['id']} has non-positive price"

    def test_products_rating_in_range(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products")
        for p in r.json()["products"]:
            assert 0 <= p["rating"] <= 5, f"Product {p['id']} rating out of range"

    def test_products_discount_in_range(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products")
        for p in r.json()["products"]:
            assert 0 <= p["discountPercentage"] <= 100

    def test_products_stock_non_negative(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products")
        for p in r.json()["products"]:
            assert p["stock"] >= 0

    def test_get_product_by_id(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products/1")
        assert r.status_code == 200
        assert r.json()["id"] == 1

    def test_product_has_description(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products/1")
        assert len(r.json()["description"]) > 0

    def test_get_product_not_found(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products/999")
        assert r.status_code == 404

    def test_products_by_category(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products/category/beauty")
        assert r.status_code == 200
        for p in r.json()["products"]:
            assert p["category"] == "beauty"

    def test_search_products(self, api_client: httpx.Client) -> None:
        r = api_client.get("/products/search", params={"q": "phone"})
        assert r.status_code == 200
        assert "products" in r.json()

    def test_discounted_price_less_than_original(self, api_client: httpx.Client) -> None:
        """Бизнес-правило: цена со скидкой < оригинальной цены."""
        r = api_client.get("/products/1")
        p = r.json()
        if p["discountPercentage"] > 0:
            discounted = p["price"] * (1 - p["discountPercentage"] / 100)
            assert discounted < p["price"]


@pytest.mark.api
class TestDataIntegrity:
    """Кросс-entity проверки — как в реальном мобильном приложении."""

    def test_users_list_consistent_total(self, api_client: httpx.Client) -> None:
        r1 = api_client.get("/users")
        r2 = api_client.get("/users")
        assert r1.json()["total"] == r2.json()["total"]

    def test_products_total_consistent(self, api_client: httpx.Client) -> None:
        r1 = api_client.get("/products")
        r2 = api_client.get("/products")
        assert r1.json()["total"] == r2.json()["total"]

    def test_user_exists_after_get(self, api_client: httpx.Client) -> None:
        """Пользователь из списка доступен по отдельному endpoint."""
        users = api_client.get("/users").json()["users"]
        first_id = users[0]["id"]
        r = api_client.get(f"/users/{first_id}")
        assert r.status_code == 200
        assert r.json()["id"] == first_id
