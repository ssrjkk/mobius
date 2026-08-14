"""
Pact contract tests conftest.

ВАЖНО: module-scoped `pact` fixture, накапливающая interactions через
несколько тестовых методов, ломается под `pytest -n N` -- pytest-xdist
default dist=load может раскидать тестовые методы ОДНОГО модуля по
РАЗНЫМ worker-процессам. Fixture не шарится между процессами -> каждый
worker видит только свою часть накопленных interactions -> integrity-тест
видел меньше interactions чем ожидалось (воспроизведено 3/3 раза подряд
под -n 4: "assert 1 >= 6").

@pytest.mark.xdist_group существует как альтернатива, но требует
--dist=loadgroup специально -- легко забыть при обычном вызове, хрупко.
Правильный fix -- architectural: НЕ полагаться на shared mutable state
между тестовыми item'ами. pact fixture теперь function-scoped -- каждый
тест получает СВОЙ Pact и сам его записывает/проверяет, без зависимости
от порядка/распределения других тестов между worker-процессами.
"""

from __future__ import annotations

import json

import pytest
from pact.pact import Pact

CONSUMER = "mobius"
PROVIDER = "demo-backend-api"


@pytest.fixture
def pact_dir(tmp_path):
    return tmp_path


@pytest.fixture
def pact(pact_dir):
    """
    Function-scoped: каждый тест получает независимый Pact объект.
    xdist-safe по конструкции -- нет разделяемого состояния между тестами.
    """
    p = Pact(CONSUMER, PROVIDER)
    yield p
    p.write_file(str(pact_dir))
    files = list(pact_dir.glob("*.json"))
    assert len(files) == 1
    content = json.loads(files[0].read_text())
    assert content["consumer"]["name"] == CONSUMER
    assert content["provider"]["name"] == PROVIDER
