# Usage Guide

This guide explains how to use Mobius for mobile test automation and what problems it solves.

## What Is Mobius For

Mobius is a Python library for writing mobile UI tests on Android and iOS. It provides:

- **Screen Object Pattern** — organize tests by screens, not by locators
- **Device pooling** — run tests in parallel across multiple emulators/devices
- **Gesture helpers** — swipe, pinch, zoom without manual coordinate math
- **Auto-retry on flaky errors** — StaleElement, timeouts handled automatically
- **YAML-driven configuration** — one config file per app, no hardcoded capabilities
- **CI-ready infrastructure** — Allure reports, screenshots on failure, parallel execution

## When to Use Mobius

### Good fit

- You're writing Appium tests in Python and want less boilerplate
- You need to test on multiple devices in parallel
- You want structured tests (screen objects) without writing the infrastructure yourself
- You're tired of flaky tests failing on StaleElement or timeouts
- You need CI integration with reports and screenshots

### Not a fit

- You're testing web apps (use Selenium directly)
- You're using Java/Kotlin/Swift (Mobius is Python-only)
- You need native app development tools (Mobius is for testing, not development)
- You're doing performance profiling (Mobius is for functional testing)

## Installation

```bash
# Install from source
git clone git@github.com:ssrjkk/mobius.git
cd mobius
pip install -e ".[test]"

# Or install as a dependency in your project
pip install git+https://github.com/ssrjkk/mobius.git
```

## Basic Usage

### 1. Create capabilities

```python
from mobius import DeviceCapabilities, Platform

caps = DeviceCapabilities(
    platform=Platform.ANDROID,
    platform_version="14.0",
    device_name="Pixel 6",
    app="com.example.myapp",
)
```

### 2. Create driver

```python
from mobius import create_driver

driver = create_driver(caps.to_capabilities())
```

### 3. Write a screen object

```python
from appium.webdriver.common.appiumby import AppiumBy
from mobius.screens.base_screen import BaseScreen

class LoginScreen(BaseScreen):
    _USERNAME = (AppiumBy.ACCESSIBILITY_ID, "username_field")
    _PASSWORD = (AppiumBy.ACCESSIBILITY_ID, "password_field")
    _LOGIN_BTN = (AppiumBy.ACCESSIBILITY_ID, "login_button")

    def login(self, username: str, password: str) -> None:
        self.type_text(self._USERNAME, username)
        self.type_text(self._PASSWORD, password)
        self.tap(self._LOGIN_BTN)
```

### 4. Write a test

```python
import pytest

def test_login(driver):
    screen = LoginScreen(driver)
    screen.login("user@example.com", "password123")
    assert screen.is_element_visible((AppiumBy.ACCESSIBILITY_ID, "welcome_message"))
```

## Advanced Features

### Parallel Testing with DevicePool

Run tests across multiple devices simultaneously:

```python
from mobius import DevicePool, Platform

pool = DevicePool()
pool.register("emulator-5554", Platform.ANDROID, "13.0", "Pixel 6")
pool.register("emulator-5556", Platform.ANDROID, "14.0", "Pixel 7")
pool.register("emulator-5558", Platform.ANDROID, "15.0", "Pixel 8")
pool.assert_no_port_collisions()

# Each pytest-xdist worker gets its own device
device = pool.get_for_worker(os.environ.get("PYTEST_XDIST_WORKER"))
```

Run with:
```bash
pytest tests/ -n 3  # 3 parallel workers
```

### Test Isolation

Reset app state between tests automatically:

```python
import pytest
from mobius import AppResetHelper, ResetStrategy

@pytest.fixture(autouse=True)
def reset_app(driver):
    helper = AppResetHelper(driver, "com.example.myapp")
    helper.reset(ResetStrategy.TERMINATE)  # Kill and restart app
    yield
    helper.reset(ResetStrategy.CLEAR_DATA)  # Clear app data after test
```

### YAML-Driven Configuration

Define app config once, use everywhere:

```yaml
# apps/my_app.yaml
app:
  package: com.example.myapp
  activity: .MainActivity
  
capabilities:
  platform: android
  platform_version: "14.0"
  device_name: Pixel 6
  
screens:
  login:
    username_field: "username_field"
    password_field: "password_field"
    login_button: "login_button"
```

```python
from mobius import AppConfig, ConfigDrivenScreen

config = AppConfig.load("apps/my_app.yaml")
driver = create_driver(config.to_capabilities())
screen = ConfigDrivenScreen(driver, config)
screen.tap("login_button")  # Uses locator from YAML
```

### UniversalFinder (No Screen Objects Needed)

Quick element finding without defining screen classes:

```python
from mobius import UniversalFinder

finder = UniversalFinder(driver)

# Find and interact
finder.find_button_by_text("Sign In").click()
finder.find_element_by_id("username").send_keys("user@example.com")

# Check screen state
assert finder.screen_contains_text("Welcome")
assert finder.is_element_present("error_message")
```

### Gesture Helpers

Common gestures without coordinate math:

```python
from mobius import Gestures

gestures = Gestures(driver)

# Swipe
gestures.swipe_up()
gestures.swipe_down()
gestures.swipe_left()
gestures.swipe_right()

# Pinch/zoom
gestures.pinch(element)  # Zoom out
gestures.zoom(element)   # Zoom in

# Long press
gestures.long_press(element, duration=2.0)
```

### Network Conditions

Simulate different network states:

```python
from mobius import NetworkManager

network = NetworkManager(driver)

network.enable_airplane_mode()
network.disable_airplane_mode()

network.set_wifi(enabled=False)
network.set_data(enabled=True)
```

### Biometrics (Android)

Test fingerprint/face authentication:

```python
from mobius import Biometrics

biometrics = Biometrics(driver)

# Simulate successful fingerprint
biometrics.authenticate_fingerprint(success=True)

# Simulate failed attempt
biometrics.authenticate_fingerprint(success=False)
```

### App Interruptions

Test how app handles interruptions:

```python
from mobius import InterruptionManager

interruptions = InterruptionManager(driver)

# Simulate phone call
interruptions.simulate_incoming_call()
interruptions.end_call()

# Simulate notification
interruptions.send_notification("Test notification")

# Simulate low memory
interrutions.simulate_low_memory()
```

## Running Tests

### Without device (unit/API tests)

```bash
make test-all      # All non-UI tests
make test-parallel # Same, but 4 threads
```

### With device (UI tests)

```bash
# Start Appium server first
appium

# Run UI tests
make test-ui

# Run specific test
pytest tests/ui/test_login.py -v

# Run with Allure report
pytest tests/ui/ --alluredir=allure-results
allure serve allure-results
```

### Parallel UI tests

```bash
# Requires multiple emulators/devices running
make test-ui-parallel

# Or specify number of workers
pytest tests/ui/ -n 3 --alluredir=allure-results
```

## CI Integration

### GitHub Actions example

```yaml
name: Mobile Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -e ".[test]"
      
      - name: Run tests
        run: make test-all
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

### With Android emulator

```yaml
jobs:
  ui-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Enable KVM
        run: |
          echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm.rules
          sudo udevadm control --reload-rules
          sudo udevadm trigger --name-match=kvm
      
      - name: AVD cache
        uses: actions/cache@v4
        with:
          path: ~/.android/avd
          key: avd-cache
      
      - name: Create AVD and start emulator
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: 30
          arch: x86_64
          profile: Pixel 6
          script: |
            appium &
            pytest tests/ui/ --alluredir=allure-results
      
      - name: Upload Allure results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: allure-results
          path: allure-results
```

## Project Structure Recommendation

```text
your-project/
├── apps/
│   ├── android.yaml      # Android app config
│   └── ios.yaml          # iOS app config
├── screens/
│   ├── login_screen.py
│   ├── home_screen.py
│   └── profile_screen.py
├── tests/
│   ├── unit/             # Fast tests, no device
│   ├── api/              # Backend API tests
│   └── ui/               # E2E UI tests
├── conftest.py           # Fixtures, hooks
└── pytest.ini            # pytest config
```

## Common Patterns

### Wait for element

```python
from mobius import wait_for_element

element = wait_for_element(driver, (AppiumBy.ID, "loading_spinner"), timeout=10)
assert element.is_displayed()
```

### Scroll to element

```python
from mobius import scroll_to_element

element = scroll_to_element(driver, (AppiumBy.ACCESSIBILITY_ID, "submit_button"))
element.click()
```

### Take screenshot

```python
from mobius import take_screenshot

take_screenshot(driver, name="login_success")
# Saved to screenshots/login_success.png
```

### Handle alerts

```python
from mobius import handle_alert

# Accept alert
handle_alert(driver, accept=True)

# Dismiss alert
handle_alert(driver, accept=False)

# Get alert text
text = handle_alert(driver, accept=False, get_text=True)
```

## Troubleshooting

### Tests fail with "Appium server not reachable"

```bash
# Start Appium server
appium

# Or specify custom URL
export APPIUM_SERVER_URL=http://localhost:4723
```

### StaleElement errors

Mobius handles this automatically with MobileElement retry. If you still see errors:

```python
from mobius import MobileElement

element = MobileElement(driver, locator)
element.click()  # Auto-retries on StaleElement
```

### Slow tests

- Use `make test-parallel` for parallel execution
- Mock external dependencies in unit tests
- Reserve UI tests for critical paths only

### Flaky tests

Check if it's infrastructure or real failure:

```python
from mobius import is_infrastructure_error

try:
    do_something()
except Exception as e:
    if is_infrastructure_error(e):
        print("Infrastructure issue — retry makes sense")
    else:
        print("Real test failure — fix the bug")
```

## Next Steps

- Read [README.md](README.md) for project overview
- Check [docs/adr/](docs/adr/) for architecture decisions
- Look at [tests/](tests/) for real examples
- Review [CHANGELOG.md](CHANGELOG.md) for recent changes
