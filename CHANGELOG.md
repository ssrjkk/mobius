# Changelog

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Версионирование: [Semantic Versioning](https://semver.org/).

## [2.2.0] — 2026-05-29 — Rebrand: mobile-qa-framework → Mobius

### BREAKING CHANGE

Проект переименован из `mobile-qa-framework` в **Mobius**. Импортируемый
пакет тоже переименован — `import framework` → `import mobius`, чтобы
имя PyPI-пакета совпадало с именем импорта (как у `django`, `flask`,
`playwright`), а не расходилось как раньше.

**Миграция для существующего кода:**
```python
# было
from framework.driver.device_pool import DevicePool
from framework import create_driver

# стало
from mobius.driver.device_pool import DevicePool
from mobius import create_driver
```

```bash
# было
pip install mobile-qa-framework
git clone git@github.com:ssrjkk/mobile-qa-framework.git

# стало
pip install mobius
git clone git@github.com:ssrjkk/mobius.git
```

### Changed
- Директория пакета: `framework/` → `mobius/`
- `pyproject.toml`: `name`, `[tool.hatch.build.targets.wheel] packages`,
  `[tool.coverage.run] source`, `[[tool.mypy.overrides]] module`,
  `[tool.ruff.lint.per-file-ignores]` — все функциональные пути обновлены
  (не только косметика: mypy override на `gestures.py` перестал бы
  применяться без этого изменения — strict-режим снова показал бы
  ~28 ошибок untyped Selenium Actions API)
- `mobius/logging_config.py`: root-логгер `logging.getLogger("framework")`
  → `logging.getLogger("mobius")` — функциональное изменение, не
  косметика: без этого дочерние логгеры модулей (`mobius.utils.device`
  и т.д.) перестали бы быть потомками правильного root-логгера,
  `propagate=False` и кастомный handler бы не применились
- `mobius/__init__.py`: полноценный публичный API — `__version__`,
  `__github__`, 40+ экспортов через `__all__`
- Pact contract consumer name: `mobile-qa-framework` → `mobius`
- Все GitHub URL, git clone инструкции, ADR путевые ссылки

### Verified
- Чистая установка в новом venv: `pip install -e ".[test]"` — 0 ошибок
- Импорт `from mobius import DevicePool` из внешней (не source) директории
- `mypy mobius/` — 0 ошибок (43 файла), включая проверку что gestures.py
  override реально применился под новым путём
- `ruff check mobius/ tests/ apps/` — 0 ошибок
- `bandit -r mobius/ -c pyproject.toml` — 0 High/Medium
- Полный тестовый прогон (584 passed + 2 skipped) — из venv, установленного
  под новым именем пакета, не из старой рабочей директории

### Исторические записи ниже
Версии 1.0.0–2.1.0 описывают состояние проекта КАК ОНО БЫЛО на момент
тех релизов — то есть под именем `framework/`. Записи не переписаны
задним числом, это исторически точный snapshot.

## [2.1.0] — 2026-05-05 — Production-readiness pass

Критичный проход: "должен ли фреймворк быть таким, чтобы им реально
пользовалась команда" — а не только "проходит собственные тесты".

### Fixed (критично)
- **Пакет физически не устанавливался.** `pip install -e .` падал —
  hatchling не мог определить какую директорию паковать. Добавлен
  `[tool.hatch.build.targets.wheel] packages = ["framework"]`.
- **Ядро не импортировалось после установки.** Runtime-зависимости
  (selenium, Appium-Python-Client, Pillow, pyyaml, requests) были в
  `[test]` extras вместе с pytest-инструментами — `pip install
  mobius` без extras ставил нерабочую пустышку.
- **`allure-pytest` в core тянул весь pytest транзитивно** — заменён на
  `allure-python-commons` (лёгкий пакет, даёт `import allure` без
  pytest). Команды на unittest/Robot Framework больше не вынуждены
  тащить чужой test runner.
- **`RetryDecorator.retry(times=0)`** кидал непонятный `TypeError:
  exceptions must derive from BaseException` вместо внятной ошибки —
  найдено через `mypy --strict`. Теперь явный `ValueError` при times<1.
- **`create_driver()` использовал несуществующий параметр
  `desired_capabilities`** — Appium-Python-Client 5.x убрал его из
  `webdriver.Remote()`. Баг никогда не проявлялся в тестах (весь путь
  был помечен `pragma: no cover`). Исправлено на
  `AppiumOptions().load_capabilities()`.
- Забытый закоммитить файл `test_universal_advanced.py` (926 строк, 100+
  тестов) — существовал только в рабочей директории, `git clone` не
  получил бы эти тесты вообще.
- Fabricated verification claims в докстрингах `test_login.py` /
  `test_ios_smoke.py` ("локаторы проверены против APK v2.5.0") — заменены
  на честное раскрытие: локаторы НЕ верифицированы против реального
  бинарника, референсный SUT (`my-demo-app-rn`) архивирован Sauce Labs
  8 мая 2024.

### Added
- `framework/logging_config.py` — структурированное логирование вместо
  61 места `except Exception: return False` без единой диагностики.
  WARNING для реальных сбоев, DEBUG для ожидаемых негативных исходов.
- `tests/wire_protocol/` — новый тестовый слой: реальный HTTP через
  настоящий Appium-Python-Client против локального fake WebDriver
  сервера. Проверяет байты на проводе, не поведение мока.
- `mypy --strict` теперь чист по всему `framework/` (было 76 ошибок).
- Параллельное выполнение (`pytest -n auto`) верифицировано — 3 повтора
  без flaky-тестов от общего состояния.

### Changed
- `framework/types.py` — общий `Locator = tuple[str, str]` alias вместо
  голого `tuple` по всему коду.

## [2.0.0] — 2026-04-23 — Universal device-level layer

Framework перестал быть завязан на один референсный SUT.

### Added
- `framework/utils/device.py` — rotation, hardware keys, app lifecycle,
  геолокация.
- `framework/utils/alerts.py`, `permissions.py` — системные диалоги и
  разрешения.
- `framework/utils/clipboard.py`, `locale.py`, `notifications.py`.
- `framework/utils/universal_finder.py` — поиск элементов без знания
  локаторов конкретного приложения.
- `framework/utils/webview.py` — native ↔ WebView context switching для
  гибридных приложений.
- `framework/utils/visual_regression.py` — pixel-diff против baseline.
- `framework/utils/biometrics.py` — Face ID/Touch ID/fingerprint
  симуляция.
- `framework/utils/interruptions.py` — входящий звонок/SMS/battery во
  время теста.
- `framework/utils/file_transfer.py`, `device_logs.py`,
  `app_lifecycle.py`, `screen_recording.py`.
- `framework/utils/app_config.py` + `apps/*.yaml` — config-driven
  тестирование нового приложения без правки кода.
- Каждый `BaseScreen` теперь содержит `self.device`, `self.alerts`,
  `self.clipboard`, `self.finder`.

## [1.0.0] — 2026-04-11 — Initial release

- `framework/driver/` — Appium driver factory, device capabilities
  (Pixel 6/7, iPhone 15).
- `framework/screens/` — Screen Object Model, референс: Sauce Labs My
  Demo App RN.
- `framework/elements/mobile_element.py` — StaleElement-safe wrapper.
- `framework/utils/gestures.py` — W3C Actions (swipe/pinch/long_press).
- `framework/utils/wait_utils.py` — explicit + fluent waits.
- CI: Android эмулятор matrix (API 33/34) в GitHub Actions.

[2.1.0]: https://github.com/ssrjkk/mobius/releases/tag/v2.1.0
[2.0.0]: https://github.com/ssrjkk/mobius/releases/tag/v2.0.0
[1.0.0]: https://github.com/ssrjkk/mobius/releases/tag/v1.0.0
