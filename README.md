# Mobius

> Универсальный Android/iOS QA automation framework — Appium 2.x + pytest
> **Ситников Сергей** · [@ssrjkk](https://github.com/ssrjkk)

[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Appium](https://img.shields.io/badge/appium-2.x-purple)](https://appium.io)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Установка

```bash
pip install -e ".[test]"          # для запуска тестов
pip install -e ".[test,lint]"     # + mypy, ruff, bandit, pip-audit
```

## Архитектура

```
mobius/              ← публичное ядро — не знает о конкретном SUT
├── driver/
│   ├── capabilities.py   DeviceCapabilities, Platform, ResetStrategy
│   ├── appium_driver.py  create_driver(), is_appium_available()
│   └── device_pool.py    DevicePool — параллельное выполнение
├── elements/
│   └── mobile_element.py MobileElement — StaleElement-safe, retry×3
├── screens/              ПРИМЕР Screen Object Model (Sauce Labs Demo App)
│   ├── base_screen.py    BaseScreen — wait → MobileElement → interact
│   ├── login_screen.py
│   ├── home_screen.py
│   └── product_screen.py
└── utils/                24 universal-модуля, ни один не привязан к SUT
    ├── gestures.py        W3C Actions: swipe/pinch/long_press/drag
    ├── wait_utils.py      WaitUtils, RetryDecorator
    ├── device.py          rotation, hardware keys, lifecycle, geo
    ├── alerts.py          системные диалоги
    ├── permissions.py     grant/revoke разрешений
    ├── clipboard.py       copy/paste
    ├── locale.py          runtime смена языка
    ├── notifications.py   push-уведомления
    ├── universal_finder.py find без знания локаторов
    ├── webview.py         native ↔ WebView switching
    ├── visual_regression.py pixel-diff против baseline
    ├── biometrics.py      Face ID / fingerprint симуляция
    ├── interruptions.py   входящий звонок/SMS во время теста
    ├── file_transfer.py   push/pull файлов
    ├── device_logs.py     logcat + crash detection
    ├── app_lifecycle.py   install/uninstall/update
    ├── screen_recording.py видео при падении
    ├── network.py         WiFi/LTE/3G/2G/Offline
    ├── performance.py     RAIL thresholds
    ├── accessibility.py   WCAG 2.1 Mobile
    ├── deeplink.py        URI scheme навигация
    ├── app_config.py      YAML config-driven testing
    └── test_isolation.py  AppResetHelper, ResetStrategy

tests/
├── unit/           567 тестов — MagicMock driver, < 20s
├── api/            respx / dummyjson.com — мобильный backend
├── wire_protocol/  реальный HTTP через fake WebDriver server
└── ui/             E2E — требует Appium + эмулятор/устройство
```

## Быстрый старт

```bash
# Всё без устройства — CI-ready
make test-all             # unit + api + wire_protocol

# Параллельно на 4 ядрах (проверяет thread-safety)
make test-parallel

# С реальным Appium + эмулятором
appium --base-path /wd/hub
make test-ui-smoke
```

## Публичный API

```python
from framework import (
    # DevicePool — параллельное выполнение
    DevicePool, Device,

    # Capabilities
    create_driver, DeviceCapabilities, Platform,
    pixel_6_api33, iphone_15_ios17, from_env,

    # Изоляция тестов
    AppResetHelper, ResetStrategy,

    # Универсальные утилиты
    Gestures, SwipeDirection,
    UniversalFinder,
    AppConfig, ConfigDrivenScreen,
    AccessibilityChecker,
    VisualRegression,
    NetworkSimulator, NetworkProfile,
)
```

### DevicePool — параллельный CI с N устройствами

```python
# conftest.py
pool = DevicePool()
pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
pool.register("emulator-5556", Platform.ANDROID, "14.0", "Pixel 7")
pool.assert_no_port_collisions()

# pytest -n 2 → каждый worker получает своё устройство
device = pool.get_for_worker(os.environ.get("PYTEST_XDIST_WORKER"))
caps = DeviceCapabilities(..., extra=pool.to_capabilities_extra(device))
```

### AppResetHelper — изоляция между тестами

```python
# tests/ui/conftest.py — autouse fixture
@pytest.fixture(autouse=True)
def auto_reset(driver):
    AppResetHelper(driver, "com.example.app").reset(ResetStrategy.TERMINATE)
```

### UniversalFinder — тестирование без Screen Object

```python
finder = UniversalFinder(driver)
finder.find_button_by_text("Sign In").click()
finder.screen_contains_text("Welcome")
finder.get_all_texts_on_screen()
```

### Config-driven — новое приложение без кода

```python
config = AppConfig.load("apps/my_app.yaml")
driver = create_driver(config.to_capabilities())
screen = ConfigDrivenScreen(driver, config)
screen.tap("login_button")
```

### BaseScreen — fluent + StaleElement-safe

```python
class LoginScreen(BaseScreen):
    _USERNAME = (AppiumBy.ACCESSIBILITY_ID, "Username input field")
    _LOGIN_BTN = (AppiumBy.ACCESSIBILITY_ID, "Login button")

    def login(self, user: str, password: str) -> None:
        # wait_for_visible → MobileElement.clear_and_type (retry×3)
        self.type_text(self._USERNAME, user)
        # wait_for_clickable → MobileElement.click (retry×3)
        self.tap(self._LOGIN_BTN)
```

## Команды

```
make help              # все команды
make test-all          # unit + api + wire (без устройства)
make test-parallel     # то же параллельно -n 4
make test-ui           # E2E (нужен Appium)
make test-ui-parallel  # E2E параллельно через DevicePool
make lint              # ruff + mypy
make security          # bandit + pip-audit
make cov               # coverage report
make ci                # lint + test-all + security (pre-merge)
```

## Документация

- [`CHANGELOG.md`](CHANGELOG.md) — история версий
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — как добавлять код
- [`docs/adr/`](docs/adr/) — 7 ADR, включая честные открытые риски
- [`LICENSE`](LICENSE) — MIT

## Автор

**Ситников Сергей** · [GitHub @ssrjkk](https://github.com/ssrjkk) · [Telegram @ssrjkk](https://t.me/ssrjkk)
