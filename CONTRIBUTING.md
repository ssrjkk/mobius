# Contributing to Mobius

## Быстрый старт

```bash
git clone git@github.com:ssrjkk/mobius.git
cd mobius
uv pip install -e ".[test,lint]"
make test-unit    # без устройства, < 10s
```

## Структура проекта — что куда

```
mobius/          ← универсальное ядро, НЕ должно знать о конкретном SUT
├── driver/           Appium driver factory, capabilities
├── elements/          StaleElement-safe wrapper
└── utils/             Все universal-модули (device, alerts, gestures, ...)

mobius/screens/  ← ПРИМЕР Screen Object Model под референсное приложение
                       (см. docs/adr/005 — референс устарел, требует миграции)

apps/                ← YAML конфиги для config-driven подхода (ADR-002)

tests/
├── unit/             MagicMock driver — быстро, без сети/устройства
├── api/               respx моки — тестовый backend
├── wire_protocol/     РЕАЛЬНЫЙ HTTP через fake WebDriver сервер (ADR-006)
└── ui/                Требует реальный Appium + эмулятор
```

**Golden rule:** если добавляешь код в `mobius/utils/` — он должен
работать с ЛЮБЫМ Appium driver, не только с референсным SUT. Если код
специфичен для одного приложения — он идёт в `mobius/screens/` как
пример, не в `utils/`.

## Правила для нового кода

### 1. Каждый `except Exception` логирует (ADR-003)

```python
# ❌ Плохо
try:
    self._driver.some_command()
except Exception:
    return False

# ✅ Хорошо
try:
    self._driver.some_command()
except Exception as e:
    logger.warning("some_command failed: %s", e)  # WARNING — реальная проблема
    return False
```

WARNING vs DEBUG — см. `docs/adr/003-structured-logging-warning-vs-debug.md`.
Критерий: "открыл бы дежурный инженер тикет увидев это в 3 часа ночи?"

### 2. Новый метод в `mobius/utils/` — три уровня тестов

1. **Unit** (`tests/unit/`) — `MagicMock()` driver, проверяет логику
2. **Wire-protocol** (`tests/wire_protocol/`) — если метод отправляет
   Appium команду, добавь тест против `FakeWebDriverServer`, проверь
   реальный JSON payload, не только "код не упал"
3. Если применимо — обнови `tests/ui/` (даже если не сможешь прогнать
   локально без эмулятора)

### 3. Типизация — mypy strict, без исключений

```bash
mypy mobius/  # должен быть 0 errors перед PR
```

Если Appium/Selenium API реально не типизирован (проверь через
`inspect.signature`, не угадывай) — точечный override в
`pyproject.toml [[tool.mypy.overrides]]` с комментарием почему, не
глобальное ослабление strict.

### 4. Новые зависимости — core vs test (ADR-004)

Используется в `mobius/*.py` безусловно (не только в тестах)? →
`[project.dependencies]`. Нужно только для `tests/`? → `[project.
optional-dependencies].test`.

### 5. Не пиши непроверенных claim'ов в докстрингах

История: докстринг утверждал "локаторы проверены против APK v2.5.0" —
было неправдой, версия не существовала. Если пишешь "verified"/
"проверено" — это должно быть реально сделано и проверяемо, не
правдоподобное предположение. См. `docs/adr/005`.

## PR checklist

- [ ] `make test-unit` — зелёный
- [ ] `mypy mobius/` — 0 errors
- [ ] `ruff check mobius/ tests/` — 0 errors
- [ ] Если новая Appium-команда — есть wire-protocol тест
- [ ] Если архитектурное решение — добавлен ADR в `docs/adr/`
- [ ] `CHANGELOG.md` обновлён (секция `[Unreleased]`)

## Коммит-конвенция

```
feat(utils): add NetworkSimulator.set_bandwidth_limit
fix(driver): handle timeout on session creation
test(wire_protocol): verify long_press W3C actions payload
docs(adr): document config-driven vs hardcoded decision
```

## Вопросы

Telegram: [@ssrjkk](https://t.me/ssrjkk)
