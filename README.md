
# Mobius

<p align="center">
  <a href="https://github.com/ssrjkk/mobius/actions/workflows/ci.yml">
    <img src="https://github.com/ssrjkk/mobius/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" />
  </a>
  <a href="https://ssrjkk.github.io/mobius/allure">
    <img src="https://img.shields.io/badge/Allure-Report-orange" alt="Allure Report" />
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12" />
  </a>
  <a href="https://appium.io/">
    <img src="https://img.shields.io/badge/Appium-2.x-green.svg" alt="Appium 2.x" />
  </a>
  <a href="https://codecov.io/gh/ssrjkk/mobius">
    <img src="https://codecov.io/gh/ssrjkk/mobius/branch/main/graph/badge.svg" alt="Codecov" />
  </a>
</p>

Мобильные тесты для Android и iOS на Appium 2.x + pytest.

## Быстрый старт

```bash
# Клонировать и установить
git clone git@github.com:ssrjkk/mobius.git
cd mobius
pip install -e ".[test]"

# Запустить тесты (без устройства)
make test-all

# Проверить код
make lint
```

## Что внутри

- **567 unit-тестов** — идут < 20 секунд без эмулятора
- **Строгая типизация** — mypy + ruff
- **Security scanning** — bandit + pip-audit
- **Параллельный запуск** — pytest-xdist + DevicePool
- **Allure-отчёты** — автоматически в CI

## Структура

```text
mobius/
├── driver/          Драйвер, капабилити, пул устройств
├── elements/        MobileElement (retry при StaleElement)
├── screens/         Screen Object Model
└── utils/           24+ модуля: жесты, сеть, биометрия, прерывания, ...

tests/
├── unit/            567 тестов (mock driver)
├── api/             Backend mocking (respx)
├── wire_protocol/   HTTP через fake WebDriver server
└── ui/              E2E (нужен Appium + устройство)
```

## Возможности

### Параллельный запуск на разных устройствах

```python
pool = DevicePool()
pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
pool.register("emulator-5556", Platform.ANDROID, "14.0", "Pixel 7")
pool.assert_no_port_collisions()

device = pool.get_for_worker(os.environ.get("PYTEST_XDIST_WORKER"))
```

### Изоляция тестов

```python
@pytest.fixture(autouse=True)
def auto_reset(driver):
    AppResetHelper(driver, "com.example.app").reset(ResetStrategy.TERMINATE)
```

### Поиск элементов без Screen Object

```python
finder = UniversalFinder(driver)
finder.find_button_by_text("Sign In").click()
finder.screen_contains_text("Welcome")
```

### Конфиги через YAML

```python
config = AppConfig.load("apps/my_app.yaml")
driver = create_driver(config.to_capabilities())
screen = ConfigDrivenScreen(driver, config)
screen.tap("login_button")
```

### Screen Object с авто-retry

```python
class LoginScreen(BaseScreen):
    _USERNAME = (AppiumBy.ACCESSIBILITY_ID, "Username input field")
    _LOGIN_BTN = (AppiumBy.ACCESSIBILITY_ID, "Login button")

    def login(self, user: str, password: str) -> None:
        self.type_text(self._USERNAME, user)
        self.tap(self._LOGIN_BTN)
```

## Пример теста

```python
import pytest
from mobius import create_driver, DeviceCapabilities, Platform
from mobius.screens.login_screen import LoginScreen

@pytest.fixture
def driver():
    caps = DeviceCapabilities(
        platform=Platform.ANDROID,
        platform_version="14.0",
        device_name="Pixel 6",
        app="com.example.app",
    )
    driver = create_driver(caps.to_capabilities())
    yield driver
    driver.quit()

def test_login(driver):
    screen = LoginScreen(driver)
    screen.login("user@example.com", "password123")
    assert screen.is_logged_in()
```

## Запуск

```bash
pip install -e ".[test]"
```

| Команда | Что делает |
| :--- | :--- |
| `make test-all` | Unit + API + wire protocol (без устройства) |
| `make test-parallel` | То же в 4 потока |
| `make test-ui` | E2E UI тесты (нужен Appium + устройство) |
| `make lint` | ruff + mypy |
| `make security` | bandit + pip-audit |
| `make ci` | lint + test-all + security |

## Документация

- **[CHANGELOG.md](CHANGELOG.md)** — история версий
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — как контрибьютить
- **[docs/adr/](docs/adr/)** — архитектурные решения
- **[LICENSE](LICENSE)** — MIT

## Автор

**Sergey Sitnikov**
GitHub: [@ssrjkk](https://github.com/ssrjkk)
