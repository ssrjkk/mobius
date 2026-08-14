# ADR 004: Разделение core/test зависимостей

**Статус:** Accepted
**Дата:** 2026-04-15
**Автор:** Ситников Сергей (ssrjkk)

## Контекст

Изначально ВСЕ зависимости (`selenium`, `Appium-Python-Client`,
`allure-pytest`, `Pillow`, `pyyaml`, а также `pytest`, `pytest-cov`,
`faker`, и т.д.) были свалены в единую секцию
`[project.optional-dependencies].test`.

## Проблема

Обнаружено при проверке "смогла бы команда реально это установить":
`pip install mobius` (без `[test]` extras — стандартный
способ поставить библиотеку) ставил пакет БЕЗ единой рантайм-
зависимости. `mobius/utils/gestures.py` безусловно делает `from
selenium...` на уровне модуля — ядро не импортировалось вообще.

Отдельно: `allure-pytest` был неверным выбором даже среди runtime-
зависимостей — этот пакет является pytest-плагином и транзитивно тянет
весь `pytest`. Команда на `unittest`/Robot Framework была бы вынуждена
устанавливать чужой test runner только ради `screenshot.attach()`.

## Решение

```toml
[project]
dependencies = [
    "Appium-Python-Client>=5.3",
    "selenium>=4.27",
    "allure-python-commons>=2.13",  # НЕ allure-pytest
    "Pillow>=10.4",
    "pyyaml>=6.0",
    "requests>=2.32",
]

[project.optional-dependencies]
test = [
    "pytest>=8.3", "pytest-cov>=5.0", "allure-pytest>=2.13", ...
]
```

## Обоснование

- `dependencies` = то, что нужно ЛЮБОМУ коду, который импортирует
  `framework.*`, независимо от того, каким test runner'ом пользуется
  команда-потребитель.
- `[test]` extras = то, что нужно только для запуска НАШЕГО собственного
  тест-сьюта (`tests/`) — не нужно команде, которая просто использует
  `framework` как библиотеку в своих тестах.
- `allure-python-commons` вместо `allure-pytest` — проверено эмпирически
  через `pip show allure-python-commons`: реальный модуль `allure`
  физически находится в этом пакете, `allure-pytest` — это отдельный
  pytest-плагин поверх него.

## Последствия

- Verified: чистый venv, `pip install -e .`, `pip list` → 0 пакетов
  pytest/ruff/mypy. `import framework.utils.gestures` работает.
- Если понадобится добавить новую зависимость в код `mobius/` —
  проверяй, идёт ли она в `dependencies` (используется в коде
  библиотеки) или в `[test]` (используется только в `tests/`).

## Альтернативы рассмотрены

- Единый список без разделения: путь наименьшего сопротивления, но
  ломает установку для любого потребителя не на pytest — отклонено.
- `[project.optional-dependencies].core` вместо безусловных
  `dependencies`: избыточно, `dependencies` — это и есть "core" по
  спецификации `pyproject.toml`.
