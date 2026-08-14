# ADR 001: AppiumOptions().load_capabilities() вместо desired_capabilities

**Статус:** Accepted
**Дата:** 2026-04-05
**Автор:** Ситников Сергей (ssrjkk)

## Контекст

`mobius/driver/appium_driver.py::create_driver()` создаёт Appium
WebDriver сессию. Первая версия кода передавала capabilities напрямую:

```python
return webdriver.Remote(command_executor=url, desired_capabilities=caps)
```

## Проблема

`desired_capabilities` — параметр из legacy JSON Wire Protocol.
Appium-Python-Client 5.x перешёл на чистый W3C WebDriver protocol и убрал
этот параметр из `webdriver.Remote.__init__()` полностью.

Баг не проявлялся ни в одном тесте, потому что вся функция
`create_driver()` была помечена `pragma: no cover` с комментарием
"требует реальный Appium сервер" — что было правдой для *успешного*
пути, но не для проверки сигнатуры аргументов. С реальным сервером
код упал бы с `TypeError: unexpected keyword argument
'desired_capabilities'` ещё ДО попытки сетевого подключения.

Найдено через `mypy --strict`: `error: Unexpected keyword argument
"desired_capabilities" for "WebDriver"`. Подтверждено эмпирически через
`inspect.signature(WebDriver.__init__)`.

## Решение

```python
from appium.options.common.base import AppiumOptions

options = AppiumOptions()
options.load_capabilities(capabilities.to_dict())
return webdriver.Remote(command_executor=url, options=options)
```

## Обоснование

`AppiumOptions.load_capabilities(dict)` — официальный способ передать
произвольный capabilities dict через W3C Options API в клиенте 5.x.
Работает с любым набором ключей, не требует явного объявления каждого
capability через отдельные setter-методы.

## Последствия

- Добавлен `tests/wire_protocol/` слой — реальный HTTP через fake
  WebDriver сервер, который поймал бы этот класс багов на уровне
  "сервер получил невалидный запрос", а не полагался бы только на
  mypy/инспекцию сигнатур.
- Урок для будущих изменений: `pragma: no cover` с обоснованием "требует
  реальный сервер" не освобождает от проверки что код вообще
  синтаксически способен дойти до сетевого вызова с правильными
  аргументами.

## Альтернативы рассмотрены

- Остаться на JSON Wire Protocol (устаревший `desired_capabilities`):
  невозможно — параметр физически удалён из установленной версии клиента.
- Явные setter-методы (`options.platform_name = ...` и т.д.) для каждого
  capability: избыточно для динамического dict, который уже собирается
  в `DeviceCapabilities.to_dict()`.
