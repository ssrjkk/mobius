
# Mobius

A universal, SUT-agnostic QA automation framework for Android and iOS built on Appium 2.x and pytest. 

Mobius is designed to provide a robust, highly concurrent, and strictly typed foundation for mobile UI testing. The core architecture is completely decoupled from any specific System Under Test (SUT), allowing teams to write stable, maintainable, and fast tests without boilerplate.

## Engineering Standards & Quality Assurance

- **Zero Device Dependency for Core Testing:** 567 unit tests, API mocks, and wire protocol tests run in under 20 seconds without requiring an emulator or physical device.
- **Strict Typing & Linting:** Enforced via `mypy` and `ruff`.
- **Security Scanning:** Automated vulnerability checks using `bandit` and `pip-audit`.
- **Pre-commit Hooks:** Prevent poorly formatted or insecure code from entering the repository.
- **Architecture Decision Records (ADR):** Core architectural choices and accepted risks are documented in `docs/adr/`.

---

## Project Architecture

```text
mobius/              <- Public core (SUT-agnostic)
├── driver/
│   ├── capabilities.py   DeviceCapabilities, Platform, ResetStrategy
│   ├── appium_driver.py  create_driver(), is_appium_available()
│   └── device_pool.py    DevicePool for parallel execution
├── elements/
│   └── mobile_element.py MobileElement (StaleElement-safe, 3x retry mechanism)
├── screens/              Example Screen Object Model (Sauce Labs Demo App)
│   ├── base_screen.py    BaseScreen (wait -> MobileElement -> interact)
│   ├── login_screen.py
│   ├── home_screen.py
│   └── product_screen.py
└── utils/                24+ universal modules (no SUT dependencies)
    ├── gestures.py        W3C Actions: swipe, pinch, long_press, drag
    ├── wait_utils.py      WaitUtils, RetryDecorator
    ├── device.py          Rotation, hardware keys, lifecycle, geolocation
    ├── alerts.py          System dialog handling
    ├── permissions.py     Grant/revoke app permissions
    ├── clipboard.py       Copy/paste operations
    ├── locale.py          Runtime language switching
    ├── notifications.py   Push notification handling
    ├── universal_finder.py Element discovery without explicit locators
    ├── webview.py         Native <-> WebView context switching
    ├── visual_regression.py Pixel-diff against baselines
    ├── biometrics.py      Face ID / Fingerprint simulation
    ├── interruptions.py   Incoming call/SMS simulation during tests
    ├── file_transfer.py   Push/pull files to/from device
    ├── device_logs.py     Logcat capture and crash detection
    ├── app_lifecycle.py   Install, uninstall, and update flows
    ├── screen_recording.py Video recording on test failure
    ├── network.py         WiFi/LTE/3G/2G/Offline simulation
    ├── performance.py     RAIL threshold validations
    ├── accessibility.py   WCAG 2.1 Mobile compliance checks
    ├── deeplink.py        URI scheme navigation
    ├── app_config.py      YAML config-driven testing
    └── test_isolation.py  AppResetHelper, ResetStrategy

tests/
├── unit/           567 tests (MagicMock driver, execution < 20s)
├── api/            respx / dummyjson.com (mobile backend mocking)
├── wire_protocol/  Real HTTP via fake WebDriver server
└── ui/             E2E tests (requires Appium + emulator/device)
```

---

## Key Capabilities

### 1. DevicePool: Parallel CI Execution
Manage and distribute tests across multiple physical devices or emulators without port collisions. Integrates seamlessly with `pytest-xdist`.

```python
# conftest.py
pool = DevicePool()
pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
pool.register("emulator-5556", Platform.ANDROID, "14.0", "Pixel 7")
pool.assert_no_port_collisions()

# pytest -n 2 -> each worker gets a dedicated device
device = pool.get_for_worker(os.environ.get("PYTEST_XDIST_WORKER"))
caps = DeviceCapabilities(..., extra=pool.to_capabilities_extra(device))
```

### 2. AppResetHelper: Strict Test Isolation
Ensure a clean application state between tests by terminating processes or clearing data, preventing flaky UI tests caused by residual state.

```python
# tests/ui/conftest.py
@pytest.fixture(autouse=True)
def auto_reset(driver):
    AppResetHelper(driver, "com.example.app").reset(ResetStrategy.TERMINATE)
```

### 3. UniversalFinder: Screen Object Bypass
Perform rapid assertions and interactions without defining strict Screen Object classes for edge cases or simple validations.

```python
finder = UniversalFinder(driver)
finder.find_button_by_text("Sign In").click()
finder.screen_contains_text("Welcome")
finder.get_all_texts_on_screen()
```

### 4. Config-Driven Testing
Define application capabilities and UI elements via YAML. Deploy tests for a new application without writing boilerplate Python code.

```python
config = AppConfig.load("apps/my_app.yaml")
driver = create_driver(config.to_capabilities())
screen = ConfigDrivenScreen(driver, config)
screen.tap("login_button")
```

### 5. BaseScreen: Fluent & StaleElement-Safe
The `BaseScreen` and `MobileElement` classes implement automatic wait conditions and a 3x retry mechanism to handle DOM refreshes natively.

```python
class LoginScreen(BaseScreen):
    _USERNAME = (AppiumBy.ACCESSIBILITY_ID, "Username input field")
    _LOGIN_BTN = (AppiumBy.ACCESSIBILITY_ID, "Login button")

    def login(self, user: str, password: str) -> None:
        # wait_for_visible -> MobileElement.clear_and_type (retry x3)
        self.type_text(self._USERNAME, user)
        # wait_for_clickable -> MobileElement.click (retry x3)
        self.tap(self._LOGIN_BTN)
```

---

## Quick Start & Local Development

### Installation

```bash
# Standard installation for running tests
pip install -e ".[test]"

# Installation with development tools (mypy, ruff, bandit, pip-audit)
pip install -e ".[test,lint]"
```

### Execution Commands

All commands are managed via `Makefile`. Run `make help` to see all available targets.

| Command | Description |
| :--- | :--- |
| `make test-all` | Run unit, API, and wire protocol tests. (No device required, CI-ready). |
| `make test-parallel` | Run the same suite in parallel across 4 cores. Validates thread-safety. |
| `make test-ui` | Run E2E UI tests. Requires a running Appium server and connected device/emulator. |
| `make test-ui-parallel` | Run E2E tests in parallel using `DevicePool`. |
| `make lint` | Execute static analysis via `ruff` and `mypy`. |
| `make security` | Run security vulnerability scans via `bandit` and `pip-audit`. |
| `make cov` | Generate and display the test coverage report. |
| `make ci` | Pre-merge validation pipeline: `lint` + `test-all` + `security`. |

---

## Public API

```python
from framework import (
    # DevicePool for parallel execution
    DevicePool, Device,

    # Capabilities and Driver Factory
    create_driver, DeviceCapabilities, Platform,
    pixel_6_api33, iphone_15_ios17, from_env,

    # Test Isolation
    AppResetHelper, ResetStrategy,

    # Universal Utilities
    Gestures, SwipeDirection,
    UniversalFinder,
    AppConfig, ConfigDrivenScreen,
    AccessibilityChecker,
    VisualRegression,
    NetworkSimulator, NetworkProfile,
)
```

---

## Documentation & Resources

- **[CHANGELOG.md](CHANGELOG.md)**: Version history and release notes.
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Guidelines for code contribution and PR standards.
- **[docs/adr/](docs/adr/)**: Architecture Decision Records detailing core engineering choices and accepted technical debt.
- **[LICENSE](LICENSE)**: MIT License.

## Author

**Sergey Sitnikov**  
GitHub: [@ssrjkk](https://github.com/ssrjkk)
```
