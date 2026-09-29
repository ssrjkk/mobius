# Mobius

<p align="center">
  <a href="https://github.com/ssrjkk/mobius/actions/workflows/ci.yml">
    <img src="https://github.com/ssrjkk/mobius/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" />
  </a>
  <a href="https://codecov.io/gh/ssrjkk/mobius">
    <img src="https://codecov.io/gh/ssrjkk/mobius/branch/main/graph/badge.svg" alt="Codecov" />
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12" />
  </a>
  <a href="https://appium.io/">
    <img src="https://img.shields.io/badge/Appium-2.x-green.svg" alt="Appium 2.x" />
  </a>
  <a href="https://docs.pytest.org/">
    <img src="https://img.shields.io/badge/pytest-8.x-blue.svg" alt="pytest" />
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" />
  </a>
</p>

<p align="center">
  <strong>Universal QA Automation Framework for Android & iOS</strong><br/>
  Built on Appium 2.x and pytest with security hardening
</p>

---

## Overview

Mobius is a production-grade, SUT-agnostic mobile testing framework that provides a robust foundation for Android and iOS automation. Features parallel execution, config-driven testing, StaleElement-safe Screen Object Model, and 24+ built-in utilities.

## Key Features

- **Zero Device Dependency** — 567+ unit tests run in <20s without emulator
- **Parallel Execution** — DevicePool for concurrent testing across multiple devices
- **StaleElement-Safe** — Automatic 3x retry mechanism for DOM refreshes
- **Config-Driven** — YAML-based app configuration, no boilerplate code
- **Security Hardened** — bandit + pip-audit scanning, strict typing with mypy
- **24+ Utilities** — Gestures, biometrics, network simulation, visual regression, and more

## Quick Start

```bash
# Install with test dependencies
pip install -e ".[test]"

# Install with linting tools
pip install -e ".[test,lint]"

# Run all tests (no device required)
make test-all

# Run with coverage
make cov

# Run security scan
make security
```

## Architecture

```
mobius/
├── driver/          # Device capabilities, driver factory, device pool
├── elements/        # MobileElement with StaleElement-safe retry
├── screens/         # Screen Object Model (BaseScreen)
└── utils/           # 24+ utilities (gestures, waits, device, alerts, etc.)

tests/
├── unit/            # 567 unit tests (no device required)
├── api/             # Backend API tests with mocking
├── wire_protocol/   # Real HTTP via fake WebDriver server
└── ui/              # E2E tests (requires Appium + device)
```

## Public API

```python
from mobius import (
    DevicePool, Device,
    create_driver, DeviceCapabilities, Platform,
    AppResetHelper, ResetStrategy,
    Gestures, SwipeDirection,
    UniversalFinder,
    AppConfig, ConfigDrivenScreen,
    AccessibilityChecker,
    VisualRegression,
    NetworkSimulator, NetworkProfile,
)
```

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — Version history
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guidelines
- [docs/adr/](docs/adr/) — Architecture Decision Records
- [LICENSE](LICENSE) — MIT License

## Author

**Sergey Sitnikov**
GitHub: [@ssrjkk](https://github.com/ssrjkk)
