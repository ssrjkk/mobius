"""
API тесты conftest — respx моки или реальный dummyjson.com.

Режимы:
  По умолчанию  → respx (детерминированы, без сети, быстро)
  --live-api    → реальный HTTP к dummyjson.com

Запуск:
  pytest tests/api/                    # mock
  pytest tests/api/ --live-api         # real network
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

BASE_MOCK = "https://dummyjson.com"

# Загружаем fixtures из qa-sentinel если есть, или используем inline
FIXTURES = {
    "users": {
        "users": [
            {
                "id": 1,
                "firstName": "Emily",
                "lastName": "Johnson",
                "email": "emily.johnson@x.dummyjson.com",
                "age": 28,
                "gender": "female",
                "username": "emilys",
                "phone": "+81 965-431-3024",
            },
            {
                "id": 2,
                "firstName": "Michael",
                "lastName": "Williams",
                "email": "michael.williams@x.dummyjson.com",
                "age": 35,
                "gender": "male",
                "username": "michaelw",
                "phone": "+49 258-627-6685",
            },
        ],
        "total": 208,
        "skip": 0,
        "limit": 10,
    },
    "products": {
        "products": [
            {
                "id": 1,
                "title": "Essence Mascara Lash Princess",
                "description": "Popular mascara for volumizing effects.",
                "price": 9.99,
                "discountPercentage": 7.17,
                "rating": 4.94,
                "stock": 5,
                "category": "beauty",
            },
            {
                "id": 2,
                "title": "Eyeshadow Palette with Mirror",
                "description": "Versatile eyeshadow palette.",
                "price": 19.99,
                "discountPercentage": 5.50,
                "rating": 3.28,
                "stock": 44,
                "category": "beauty",
            },
        ],
        "total": 194,
        "skip": 0,
        "limit": 10,
    },
}


@pytest.fixture
def live_api(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--live-api"))


@pytest.fixture
def api_client(live_api: bool):
    """
    httpx клиент — реальный или с respx моками.
    """
    if live_api:
        with httpx.Client(base_url=BASE_MOCK, timeout=10) as client:
            yield client
    else:
        with respx.mock(base_url=BASE_MOCK, assert_all_called=False) as mock:
            _setup_mocks(mock)
            with httpx.Client(base_url=BASE_MOCK) as client:
                yield client


def _setup_mocks(mock: respx.MockRouter) -> None:
    u1 = FIXTURES["users"]["users"][0]
    p1 = FIXTURES["products"]["products"][0]
    p2 = FIXTURES["products"]["products"][1]

    # Users
    mock.get("/users").mock(return_value=httpx.Response(200, json=FIXTURES["users"]))
    mock.get("/users/1").mock(return_value=httpx.Response(200, json=u1))
    mock.get("/users/999").mock(
        return_value=httpx.Response(404, json={"message": "User '999' not found"})
    )
    mock.get(url__regex=r"/users/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "users": [u1],
                "total": 1,
                "skip": 0,
                "limit": 10,
            },
        )
    )
    mock.post("/users/add").mock(return_value=httpx.Response(201, json={**u1, "id": 101}))
    mock.put("/users/1").mock(return_value=httpx.Response(200, json={**u1, "firstName": "Updated"}))
    mock.delete("/users/1").mock(
        return_value=httpx.Response(
            200,
            json={
                **u1,
                "isDeleted": True,
                "deletedOn": "2026-01-01T00:00:00.000Z",
            },
        )
    )

    # Products
    mock.get("/products").mock(return_value=httpx.Response(200, json=FIXTURES["products"]))
    mock.get("/products/1").mock(return_value=httpx.Response(200, json=p1))
    mock.get("/products/999").mock(
        return_value=httpx.Response(404, json={"message": "Product '999' not found"})
    )
    mock.get(url__regex=r"/products/category/").mock(
        return_value=httpx.Response(
            200,
            json={
                "products": [p1, p2],
                "total": 2,
                "skip": 0,
                "limit": 10,
            },
        )
    )
    mock.get(url__regex=r"/products/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "products": [p1],
                "total": 1,
                "skip": 0,
                "limit": 10,
            },
        )
    )

    # Auth
    def auth_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("username") == "emilys":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "username": "emilys",
                    "email": "emily.johnson@x.dummyjson.com",
                    "firstName": "Emily",
                    "lastName": "Johnson",
                    "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MX0.test",
                    "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MX0.refresh",
                },
            )
        return httpx.Response(400, json={"message": "Invalid credentials"})

    mock.post("/auth/login").mock(side_effect=auth_handler)
