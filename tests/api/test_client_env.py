"""Гардероб api-фикстуры от машинного прокси.

Причина появления: на этой машине Windows выписывает в NO_PROXY запись `[::1]`,
httpx разбирает её как порт и падает `InvalidURL: Invalid port ':1]'` прямо в
создании клиента. Симптом был не «тесты красные», а «вся api-группа ошибочна на
фикстуре»: покрытие mobius при этом меряется 34.75% вместо 98.58% (оба числа —
замер `pytest tests/unit tests/api -m "unit or api" --cov=mobius`), то есть
публичная цифра проверялась бы по недосчитанному прогону.

Вторая версия этого файла была ложно-зелёной: тест «враждебное окружение» не
поднимал мок и получал 200 от настоящего dummyjson.com — в полном сватье он
упал ConnectTimeout, как только сеть отвалилась. Теперь маршрут объявлен явно и
обязан быть вызван: уход в реальную сеть падает, а не проходит.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from tests.api.conftest import BASE_MOCK


@pytest.mark.api
class TestClientIgnoresMachineProxy:
    def test_fixture_client_does_not_trust_environment(self, api_client: httpx.Client) -> None:
        assert api_client.trust_env is False, (
            "api_client снова читает машинные прокси-переменные: на хосте с "
            "NO_PROXY=[::1] вся api-группа падает на фикстуре"
        )

    def test_client_with_hostile_env_still_serves(self, monkeypatch) -> None:
        monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,127.0.0.0/8,[::1],::1")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        with respx.mock(base_url=BASE_MOCK, assert_all_called=True) as mock:
            route = mock.get("/products/1").respond(200, json={"id": 1})
            with httpx.Client(base_url=BASE_MOCK, trust_env=False) as client:
                assert client.trust_env is False
                r = client.get("/products/1")
            assert route.called, "запрос ушёл мимо мока, в реальную сеть"
        assert r.status_code == 200, "враждебное окружение всё-таки применилось к клиенту"