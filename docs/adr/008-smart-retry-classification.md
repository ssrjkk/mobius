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

# не-assertion сбой в test_flaky.py — ретраится до успеха
# (подпроцесс поднимает встроенный TimeoutError: rerun_except — ЧЁРНЫЙ
#  список, туда попадают только AssertionError/ValueError/AttributeError)
pytest test_flaky.py --reruns 3      →  RERUN, RERUN, 1 passed
```

Оба сценария также покрыты автоматизированным subprocess-тестом
(`tests/unit/test_retry_config.py::TestConfigureRerunFilterRealIntegration`)
— спавнит настоящий `pytest` подпроцесс, не мокает `pytest-rerunfailures`,
по аналогии с `tests/wire_protocol/` (реальное поведение, не мок).

## Обновление 2026-09-27: что в коде сейчас (не по памяти, по исходникам)

### 1. Таймаут условия — `TimeoutException`, не встроенный `TimeoutError`

`mobius/utils/wait_utils.py::WaitUtils.wait_for_condition` поднимает
`selenium.common.exceptions.TimeoutException`:

```python
if last_exc is not None:
    raise last_exc
raise TimeoutException(f"Condition not met within {t}s")
```

Раньше тут был голый builtin `TimeoutError` — и он не совпадал ни с одной
строкой фильтра в `[tool.pytest.ini_options] addopts`
(`--only-rerun=WebDriverException`, `--only-rerun=TimeoutException`,
`--only-rerun=StaleElementReferenceException`,
`--only-rerun=ConnectionResetError`): pytest-rerunfailures сопоставляет имя
класса, поэтому инфраструктурный таймаут валил прогон как баг вместо
ретрая. Классификация `retry_config.is_infrastructure_error()` тоже
сравнивает `type(exc).__name__` со `INFRASTRUCTURE_EXCEPTIONS`, где стоит
`"TimeoutException"` (встроенный `"TimeoutError"` там же, но он ловится
только этой эвристикой, а не `--only-rerun`). Закреплено тестом
`tests/unit/test_wait_utils.py::TestWaitUtils::test_condition_timeout_is_not_builtin`
(проверяет и `not isinstance(exc, TimeoutError)`, и
`is_infrastructure_error(...) is True`).

Не путать два механизма: subprocess-тест выше про `rerun_except` — это
чёрный список (ретраится всё кроме перечисленного), а `addopts` нашего
сьюта идёт через `--only-rerun` — БЕЛЫЙ список (ретрашится только
перечисленное). Для белого списка имя класса и решает, отсюда и
`selenium`-исключение вместо встроенного.

### 2. "Элемента нет" vs "драйвера больше нет" — в `mobius/utils/driver_health.py`

Разделение вынесено из best-effort хелперов в отдельный модуль
`mobius/utils/driver_health.py`:

- `FATAL_ERRORS` — `(InvalidSessionIdException, SessionNotCreatedException,
  OSError)`;
- `_FATAL_MESSAGE` — regex по сообщению, потому что Selenium оборачивает
  транспортные и session-level сбои в голый `WebDriverException` без
  отдельного класса ("invalid session id", "max retries exceeded",
  "connection refused" и т.п.);
- `is_driver_dead(exc)` — True если это потеря драйвера, а не отсутствие
  элемента;
- `rethrow_if_driver_dead(exc)` — поднимает фатальное наружу, "элемента
  нет" оставляет как есть.

Вызывается из best-effort хелперов: `mobius/elements/mobile_element.py`
(`is_displayed`, `is_enabled`), `mobius/screens/base_screen.py`
(`is_element_present`), `mobius/utils/universal_finder.py`
(`screen_contains_text`). Без этого разделения разорванное соединение
выглядело как "элемента нет на экране", и инфраструктурный провал
окрашивался в зелёный (false-green).

### 3. `RetryDecorator.retry` больше не делает `assert` перед re-raise

Было `assert last_exc is not None` сразу перед финальным `raise last_exc`.
Под `python -O` assert исчезает, а `raise None` превращал настоящую ошибку
в `TypeError`. Сейчас накопленные исключения живут в списке и наружу
поднимается последнее:

```python
errors.append(e)
...
raise errors[-1]
```

`times < 1` по-прежнему отсекается в момент декорирования (`ValueError`),
поэтому `errors` гарантированно непустой — без assert'а.

## Последствия

- `INFRASTRUCTURE_EXCEPTIONS`/`REAL_FAILURE_EXCEPTIONS` — списки по
  строковому имени класса исключения, не по `isinstance`. Осознанный
  компромисс: работает для стандартных Selenium/Appium/network исключений
  без импорта их модулей напрямую (снижает связанность), но не поймает
  кастомные подклассы с другим именем класса, наследующиеся от, скажем,
  `TimeoutException`. Fallback на keyword-поиск в тексте исключения
  (`timeout`, `connection`, `refused`, `unreachable`, `stale`) частично
  компенсирует это.
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
