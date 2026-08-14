"""
Config-driven app targeting — превращает framework из "скопируй код под своё
приложение" в "укажи YAML файл и работай".

Без этого модуля: чтобы протестировать новое приложение, нужно менять Python
код (capabilities, package name, activity). С этим модулем: новое приложение
описывается декларативно в YAML, framework подхватывает конфиг по имени.

Использование:
    config = AppConfig.load("apps/my_bank_app.yaml")
    caps = config.to_capabilities()
    driver = create_driver(caps)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mobius.driver.capabilities import (
    AutomationName,
    DeviceCapabilities,
    Platform,
)
from mobius.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class LocatorSpec:
    """Один локатор из конфига: strategy + value."""

    strategy: str  # 'accessibility_id' | 'id' | 'xpath' | 'class_name'
    value: str

    def as_tuple(self) -> tuple[str, str]:
        from appium.webdriver.common.appiumby import AppiumBy

        strategy_map = {
            "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
            "id": AppiumBy.ID,
            "xpath": AppiumBy.XPATH,
            "class_name": AppiumBy.CLASS_NAME,
            "android_uiautomator": AppiumBy.ANDROID_UIAUTOMATOR,
            "ios_predicate": AppiumBy.IOS_PREDICATE,
        }
        by = strategy_map.get(self.strategy, AppiumBy.XPATH)
        return (by, self.value)


@dataclass
class AppConfig:
    """
    Декларативное описание тестируемого приложения.
    Загружается из YAML/JSON — новое приложение не требует изменений кода.
    """

    name: str
    platform: str = "Android"
    platform_version: str = "13.0"
    device_name: str = "Pixel 6"
    app_package: str | None = None
    app_activity: str | None = None
    bundle_id: str | None = None
    app_path: str | None = None
    base_url: str | None = None
    locators: dict[str, LocatorSpec] = field(default_factory=dict)
    extra_capabilities: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> AppConfig:
        """Загружает конфиг из .yaml/.yml или .json файла."""
        p = Path(path)
        text = p.read_text()

        if p.suffix in (".yaml", ".yml"):
            try:
                import yaml

                data = yaml.safe_load(text)
            except ImportError as exc:
                raise ImportError(
                    "PyYAML не установлен. Используй .json конфиг или установи: pip install pyyaml"
                ) from exc
        else:
            data = json.loads(text)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        locators_raw = data.get("locators", {})
        locators = {
            key: LocatorSpec(strategy=v["strategy"], value=v["value"])
            for key, v in locators_raw.items()
        }
        return cls(
            name=data["name"],
            platform=data.get("platform", "Android"),
            platform_version=data.get("platform_version", "13.0"),
            device_name=data.get("device_name", "Pixel 6"),
            app_package=data.get("app_package"),
            app_activity=data.get("app_activity"),
            bundle_id=data.get("bundle_id"),
            app_path=data.get("app_path"),
            base_url=data.get("base_url"),
            locators=locators,
            extra_capabilities=data.get("extra_capabilities", {}),
        )

    def to_capabilities(self) -> DeviceCapabilities:
        """Конвертирует конфиг в DeviceCapabilities для create_driver()."""
        platform = Platform.ANDROID if self.platform.lower() == "android" else Platform.IOS
        automation = (
            AutomationName.UIAUTOMATOR2 if platform == Platform.ANDROID else AutomationName.XCUITEST
        )
        return DeviceCapabilities(
            platform=platform,
            device_name=self.device_name,
            platform_version=self.platform_version,
            automation_name=automation,
            app=self.app_path,
            app_package=self.app_package,
            app_activity=self.app_activity,
            bundle_id=self.bundle_id,
            extra=self.extra_capabilities,
        )

    def get_locator(self, key: str) -> tuple[str, str]:
        """Возвращает локатор по имени из конфига — используй в generic Screen Object."""
        if key not in self.locators:
            raise KeyError(
                f"Locator '{key}' not defined in config '{self.name}'. "
                f"Available: {list(self.locators.keys())}"
            )
        return self.locators[key].as_tuple()


class ConfigDrivenScreen:
    """
    Generic Screen Object управляемый конфигом — альтернатива написанию
    отдельного Python класса под каждый экран каждого приложения.

    Использование:
        config = AppConfig.load("apps/my_app.yaml")
        screen = ConfigDrivenScreen(driver, config)
        screen.tap("login_button")
        screen.type_text("username_field", "user@test.com")
    """

    def __init__(self, driver: Any, config: AppConfig) -> None:
        self._driver = driver
        self._config = config

    def find(self, locator_key: str) -> Any:
        by, value = self._config.get_locator(locator_key)
        return self._driver.find_element(by, value)

    def tap(self, locator_key: str) -> None:
        self.find(locator_key).click()

    def type_text(self, locator_key: str, text: str) -> None:
        elem = self.find(locator_key)
        elem.clear()
        elem.send_keys(text)

    def get_text(self, locator_key: str) -> str:
        return str(self.find(locator_key).text)

    def is_present(self, locator_key: str, timeout: int = 5) -> bool:
        by, value = self._config.get_locator(locator_key)
        try:
            WebDriverWait(self._driver, timeout).until(EC.presence_of_element_located((by, value)))
            return True
        except Exception as e:
            logger.debug("is_present('%s'): not found within %ss: %s", locator_key, timeout, e)
            return False
