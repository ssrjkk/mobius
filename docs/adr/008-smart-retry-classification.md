# ADR 008: Smart retry — классификация инфраструктурных сбоев vs реальных багов

**Статус:** Accepted
**Дата:** 2026-04-23
**Автор:** Ситников Сергей (ssrjkk)

## Контекст

`pytest-rerunfailures --reruns 3` ретраит ВСЁ подряд — включая тесты,
упавшие по-настоящему (неверный `assert`). Команда видит "тест иногда
проходит" в CI и списывает на flaky, хотя на самом деле это реальный баг,
который иногда проявляется на 2-й/3-й попытке случайно (например race
condition в самом приложении).

## Найдено при разработке

Модуль `mobius/utils/retry_config.py` существовал в кодовой базе как
orphaned-код — написан, но нигде не импортировался и не тестировался
(обнаружено случайно через `pre-commit run --all-files`, который вывел
файл в список untracked/unformatted). При ревизии нашлись 2 реальных
дефекта:

1. `RetryConfig` докстринг показывал `for attempt in retry:`, но класс
   не реализовывал `__iter__`/`__next__` — такой код упал бы с
   `TypeError: 'RetryConfig' object is not iterable`.
2. `configure_rerun_filter()` использовал `config.iniconfigs["rerun_except"]
   = [...]` — у `pytest.Config` **нет** атрибута `iniconfigs` вообще
   (проверено: `hasattr(pytest.Config, 'iniconfigs')` → `False`). Функция
   была тихим no-op — не падала, но и ничего не делала.

## Решение

Убрана нерабочая `iterable`-семантика из докстринга `RetryConfig`
(класс — простой tracker состояния, не итератор). `configure_rerun_filter()`
переписан на реальный механизм `pytest-rerunfailures`:

```python
config.option.rerun_except = ["AssertionError", "ValueError", "AttributeError"]
```

`rerun_except` — реальный `dest` CLI-опции `--rerun-except` в
`pytest_rerunfailures/plugin.py` (`group._addoption(..., dest="rerun_except")`).
Устанавливая `config.option.rerun_except` программно в `pytest_configure`,
получаем тот же эффект что и передача флага руками, без необходимости
писать `--rerun-except "AssertionError|ValueError"` в каждой CI команде.

## Проверено эмпирически (не по исходникам, а реальным прогоном)

```bash
# AssertionError — падает 1 раз, НЕ ретраится
pytest test_real_bug.py --reruns 3   →  1 failed (не RERUN)

# TimeoutError — ретраится до успеха
pytest test_flaky.py --reruns 3      →  RERUN, RERUN, 1 passed
```

Оба сценария также покрыты автоматизированным subprocess-тестом
(`tests/unit/test_retry_config.py::TestConfigureRerunFilterRealIntegration`)
— спавнит настоящий `pytest` подпроцесс, не мокает `pytest-rerunfailures`,
по аналогии с `tests/wire_protocol/` (реальное поведение, не мок).

## Последствия

- `INFRASTRUCTURE_EXCEPTIONS`/`REAL_FAILURE_EXCEPTIONS` — списки по
  строковому имени класса исключения, не по `isinstance`. Осознанный
  компромисс: работает для стандартных Selenium/Appium/network исключений
  без импорта их модулей напрямую (снижает связанность), но не поймает
  кастомные подклассы с другим именем класса, наследующиеся от, скажем,
  `TimeoutError`. Fallback на keyword-поиск в тексте исключения (`timeout`,
  `connection`, `stale`) частично компенсирует это.
- `is_infrastructure_error()` — эвристика, не гарантия. Граничные случаи
  (кастомное исключение без "timeout"/"connection" в тексте, но по сути
  инфраструктурное) не будут ретраиться — safer default: лучше не
  ретраить лишний раз, чем маскировать реальный баг под "flaky".

## Урок процесса

Этот ADR — конкретный пример находки из `pre-commit run --all-files`:
инструмент, добавленный для другой цели (форматирование/линтинг), выявил
orphaned незавершённый код. Стоит периодически проверять `git status`/
`grep -rn "TODO\|FIXME"` и unused-import детекторы не только на momento
написания кода, но и позже — код может "потеряться" между сессиями
разработки (в данном случае — между сбросами контейнера в ходе долгой
беседы) и остаться неинтегрированным.
