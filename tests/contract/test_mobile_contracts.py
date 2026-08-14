"""Consumer contract tests — мобильный клиент vs backend API (dummyjson.com)."""

from __future__ import annotations

import json

import httpx
import pytest

pytestmark = pytest.mark.contract


class TestAuthContract:
    def test_login_success_contract(self, pact):
        (
            pact.upon_receiving("a valid login request from mobile client")
            .given("valid user credentials exist")
            .with_request("POST", "/auth/login")
            .with_body({"username": "emilys", "password": "emilyspass"})
            .will_respond_with(200)
            .with_body(
                {
                    "id": 1,
                    "username": "emilys",
                    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                }
            )
        )
        assert pact is not None

    def test_login_invalid_credentials_contract(self, pact):
        (
            pact.upon_receiving("a login request with invalid credentials")
            .given("user credentials are invalid")
            .with_request("POST", "/auth/login")
            .with_body({"username": "wrong", "password": "wrong"})
            .will_respond_with(400)
            .with_body({"message": "Invalid credentials"})
        )
        assert pact is not None


class TestUsersContract:
    def test_get_users_list_contract(self, pact):
        (
            pact.upon_receiving("a request for users list")
            .given("users exist in the system")
            .with_request("GET", "/users")
            .will_respond_with(200)
            .with_body(
                {
                    "users": [
                        {
                            "id": 1,
                            "firstName": "Emily",
                            "lastName": "Johnson",
                            "email": "emily.johnson@x.dummyjson.com",
                            "username": "emilys",
                        }
                    ],
                    "total": 208,
                    "skip": 0,
                    "limit": 10,
                }
            )
        )
        assert pact is not None

    def test_get_user_by_id_contract(self, pact):
        (
            pact.upon_receiving("a request for user by id")
            .given("user with id 1 exists")
            .with_request("GET", "/users/1")
            .will_respond_with(200)
            .with_body(
                {
                    "id": 1,
                    "firstName": "Emily",
                    "lastName": "Johnson",
                    "email": "emily.johnson@x.dummyjson.com",
                }
            )
        )
        assert pact is not None

    def test_user_not_found_contract(self, pact):
        (
            pact.upon_receiving("a request for non-existent user")
            .given("user with id 999 does not exist")
            .with_request("GET", "/users/999")
            .will_respond_with(404)
            .with_body({"message": "User '999' not found"})
        )
        assert pact is not None


class TestProductsContract:
    def test_get_products_list_contract(self, pact):
        (
            pact.upon_receiving("a request for products list")
            .given("products exist in catalog")
            .with_request("GET", "/products")
            .will_respond_with(200)
            .with_body(
                {
                    "products": [
                        {
                            "id": 1,
                            "title": "Essence Mascara Lash Princess",
                            "price": 9.99,
                            "rating": 4.94,
                            "stock": 5,
                            "category": "beauty",
                            "description": "Popular mascara for volumizing effects.",
                        }
                    ],
                    "total": 194,
                    "skip": 0,
                    "limit": 10,
                }
            )
        )
        assert pact is not None

    def test_get_product_by_id_contract(self, pact):
        (
            pact.upon_receiving("a request for product by id")
            .given("product with id 1 exists")
            .with_request("GET", "/products/1")
            .will_respond_with(200)
            .with_body(
                {
                    "id": 1,
                    "title": "Essence Mascara Lash Princess",
                    "price": 9.99,
                    "rating": 4.94,
                    "stock": 5,
                    "category": "beauty",
                }
            )
        )
        assert pact is not None


class TestPactFileIntegrity:
    """
    Строит ВСЕ 6 контрактов внутри одного теста (не полагается на
    состояние, накопленное другими тестовыми методами) -- xdist-safe:
    результат не зависит от того, в каком worker-процессе и в каком
    порядке выполнились остальные тесты этого файла.
    """

    def test_pact_file_contains_all_contracts_when_defined_together(self, pact_dir, pact):
        (
            pact.upon_receiving("a valid login request from mobile client")
            .given("valid user credentials exist")
            .with_request("POST", "/auth/login")
            .with_body({"username": "emilys", "password": "emilyspass"})
            .will_respond_with(200)
            .with_body({"id": 1, "accessToken": "eyJhbGciOiJIUzI1NiJ9"})
        )
        (
            pact.upon_receiving("a login request with invalid credentials")
            .given("user credentials are invalid")
            .with_request("POST", "/auth/login")
            .with_body({"username": "wrong", "password": "wrong"})
            .will_respond_with(400)
            .with_body({"message": "Invalid credentials"})
        )
        (
            pact.upon_receiving("a request for users list")
            .given("users exist in the system")
            .with_request("GET", "/users")
            .will_respond_with(200)
            .with_body({"users": [{"id": 1, "firstName": "Emily"}], "total": 208})
        )
        (
            pact.upon_receiving("a request for non-existent user")
            .given("user with id 999 does not exist")
            .with_request("GET", "/users/999")
            .will_respond_with(404)
            .with_body({"message": "User '999' not found"})
        )
        (
            pact.upon_receiving("a request for products list")
            .given("products exist in catalog")
            .with_request("GET", "/products")
            .will_respond_with(200)
            .with_body({"products": [{"id": 1, "title": "Essence Mascara"}], "total": 194})
        )
        (
            pact.upon_receiving("a request for product by id")
            .given("product with id 1 exists")
            .with_request("GET", "/products/1")
            .will_respond_with(200)
            .with_body({"id": 1, "title": "Essence Mascara", "price": 9.99})
        )

        pact.write_file(str(pact_dir))
        files = list(pact_dir.glob("*.json"))
        assert len(files) == 1
        content = json.loads(files[0].read_text())
        assert content["consumer"]["name"] == "mobius"
        assert content["provider"]["name"] == "demo-backend-api"

        interactions = content["interactions"]
        assert len(interactions) == 6
        for ix in interactions:
            assert "description" in ix
            assert "request" in ix
            assert "response" in ix

    def test_pact_file_is_valid_json(self, pact_dir, pact):
        (
            pact.upon_receiving("a minimal smoke interaction")
            .with_request("GET", "/users")
            .will_respond_with(200)
            .with_body({"users": []})
        )
        pact.write_file(str(pact_dir))
        for f in pact_dir.glob("*.json"):
            parsed = json.loads(f.read_text())
            assert isinstance(parsed, dict)


class TestContractVsRealAPI:
    """Опционально: контракт реально выполним против живого API (--live-api)."""

    def test_login_contract_matches_real_api(self, request):
        if not request.config.getoption("--live-api", default=False):
            pytest.skip("Run with --live-api to test against real dummyjson.com")
        r = httpx.post(
            "https://dummyjson.com/auth/login",
            json={"username": "emilys", "password": "emilyspass"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "accessToken" in data
        assert "refreshToken" in data
        assert "id" in data

    def test_users_contract_matches_real_api(self, request):
        if not request.config.getoption("--live-api", default=False):
            pytest.skip("Run with --live-api to test against real dummyjson.com")
        r = httpx.get("https://dummyjson.com/users", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "users" in data
        assert "total" in data
        user = data["users"][0]
        for field in ("id", "firstName", "lastName", "email", "username"):
            assert field in user
