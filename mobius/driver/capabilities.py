"""Device capabilities — Appium 2.x."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Platform(str, Enum):
    ANDROID = "Android"
    IOS = "iOS"


class AutomationName(str, Enum):
    UIAUTOMATOR2 = "UiAutomator2"
    XCUITEST = "XCUITest"
    ESPRESSO = "Espresso"


class ResetStrategy(str, Enum):
    """
    Стратегия сброса состояния приложения между тест-сессиями.

    NONE       — не трогать. Быстро, но тесты влияют друг на друга
                 через shared state (логин, корзина, настройки).
    NO_RESET   — сохранить данные, сбросить Appium-сессию (noReset=true).
    FULL_RESET — полная переустановка. Медленно, гарантированная изоляция.
    TERMINATE  — завершить и перезапустить приложение программно.
                 Компромисс: чисто как FULL_RESET, быстрее чем reinstall.
                 Рекомендуется для большинства тест-сьютов.
    """

    NONE = "none"
    NO_RESET = "no_reset"
    FULL_RESET = "full_reset"
    TERMINATE = "terminate"


@dataclass
class DeviceCapabilities:
    platform: Platform
    device_name: str
    platform_version: str
    automation_name: AutomationName
    app: str | None = None
    app_package: str | None = None
    app_activity: str | None = None
    bundle_id: str | None = None
    udid: str | None = None
    no_reset: bool = False
    full_reset: bool = False
    new_command_timeout: int = 300
    auto_grant_permissions: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        caps: dict[str, Any] = {
            "platformName": self.platform.value,
            "appium:deviceName": self.device_name,
            "appium:platformVersion": self.platform_version,
            "appium:automationName": self.automation_name.value,
            "appium:noReset": self.no_reset,
            "appium:fullReset": self.full_reset,
            "appium:newCommandTimeout": self.new_command_timeout,
            "appium:autoGrantPermissions": self.auto_grant_permissions,
        }
        if self.app:
            caps["appium:app"] = str(Path(self.app).resolve())
        if self.app_package:
            caps["appium:appPackage"] = self.app_package
        if self.app_activity:
            caps["appium:appActivity"] = self.app_activity
        if self.bundle_id:
            caps["appium:bundleId"] = self.bundle_id
        if self.udid:
            caps["appium:udid"] = self.udid
        caps.update(self.extra)
        return caps


def pixel_6_api33() -> DeviceCapabilities:
    """Google Pixel 6 — Android 13 (API 33). Типичный CI эмулятор."""
    return DeviceCapabilities(
        platform=Platform.ANDROID,
        device_name="Pixel 6",
        platform_version="13.0",
        automation_name=AutomationName.UIAUTOMATOR2,
        extra={"appium:uiautomator2ServerInstallTimeout": 60000},
    )


def pixel_7_api34() -> DeviceCapabilities:
    """Google Pixel 7 — Android 14 (API 34)."""
    return DeviceCapabilities(
        platform=Platform.ANDROID,
        device_name="Pixel 7",
        platform_version="14.0",
        automation_name=AutomationName.UIAUTOMATOR2,
    )


def iphone_15_ios17() -> DeviceCapabilities:
    """iPhone 15 Simulator — iOS 17."""
    return DeviceCapabilities(
        platform=Platform.IOS,
        device_name="iPhone 15",
        platform_version="17.0",
        automation_name=AutomationName.XCUITEST,
    )


def from_env() -> DeviceCapabilities:
    """Собирает capabilities из переменных окружения — для CI."""
    platform = Platform(os.environ.get("MOBILE_PLATFORM", "Android"))
    if platform == Platform.ANDROID:
        return DeviceCapabilities(
            platform=platform,
            device_name=os.environ.get("DEVICE_NAME", "Pixel 6"),
            platform_version=os.environ.get("PLATFORM_VERSION", "13.0"),
            automation_name=AutomationName.UIAUTOMATOR2,
            app_package=os.environ.get("APP_PACKAGE"),
            app_activity=os.environ.get("APP_ACTIVITY"),
            app=os.environ.get("APP_PATH"),
            udid=os.environ.get("DEVICE_UDID"),
        )
    return DeviceCapabilities(
        platform=Platform.IOS,
        device_name=os.environ.get("DEVICE_NAME", "iPhone 15"),
        platform_version=os.environ.get("PLATFORM_VERSION", "17.0"),
        automation_name=AutomationName.XCUITEST,
        bundle_id=os.environ.get("BUNDLE_ID"),
        udid=os.environ.get("DEVICE_UDID"),
    )
