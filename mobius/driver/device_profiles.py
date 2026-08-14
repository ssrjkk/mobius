"""
Device capability profiles — загрузка из YAML/JSON без правки Python.

Проблема: pixel_6_api33() / iphone_15_ios17() хардкодят устройства в Python.
В реальном CI с матрицей из 10+ конфигураций это неудобно — нужно добавлять
функцию в Python каждый раз. С этим модулем достаточно добавить строку в YAML.

Использование:
    # devices/ci_matrix.yaml
    profiles:
      pixel_6_api33:
        platform: Android
        platform_version: "13.0"
        device_name: Pixel 6
        automation_name: UiAutomator2
        udid: emulator-5554

    # conftest.py
    from mobius.driver.device_profiles import DeviceProfileLoader
    loader = DeviceProfileLoader("devices/ci_matrix.yaml")
    caps = loader.get("pixel_6_api33")
    driver = create_driver(caps)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mobius.driver.capabilities import (
    AutomationName,
    DeviceCapabilities,
    Platform,
)
from mobius.logging_config import get_logger

logger = get_logger(__name__)


class DeviceProfileLoader:
    """Загружает device profiles из YAML или JSON файла."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._profiles: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(
                f"Device profiles file not found: {self._path}\n"
                f"Create it with 'profiles:' key — see devices/ci_matrix_example.yaml "
                f"for the expected format."
            )
        text = self._path.read_text(encoding="utf-8")
        if self._path.suffix in (".yaml", ".yml"):
            try:
                import yaml

                data = yaml.safe_load(text)
            except ImportError as e:
                raise ImportError("pip install pyyaml") from e
        else:
            data = json.loads(text)

        self._profiles = data.get("profiles", {})
        logger.debug(
            "DeviceProfileLoader: loaded %d profiles from %s: %s",
            len(self._profiles),
            self._path,
            list(self._profiles.keys()),
        )

    def available(self) -> list[str]:
        """Список доступных имён профилей."""
        return list(self._profiles.keys())

    def get(self, profile_name: str) -> DeviceCapabilities:
        """Возвращает DeviceCapabilities для именованного профиля."""
        if profile_name not in self._profiles:
            raise KeyError(
                f"Profile '{profile_name}' not found in {self._path}. Available: {self.available()}"
            )
        raw = self._profiles[profile_name]
        return self._to_capabilities(raw)

    def get_all(self) -> dict[str, DeviceCapabilities]:
        """Возвращает все профили как словарь name → DeviceCapabilities."""
        return {name: self.get(name) for name in self._profiles}

    def _to_capabilities(self, raw: dict[str, Any]) -> DeviceCapabilities:
        platform = Platform(raw.get("platform", "Android"))
        automation_str = raw.get("automation_name", "")
        if automation_str:
            automation = AutomationName(automation_str)
        else:
            automation = (
                AutomationName.UIAUTOMATOR2
                if platform == Platform.ANDROID
                else AutomationName.XCUITEST
            )
        return DeviceCapabilities(
            platform=platform,
            device_name=raw["device_name"],
            platform_version=str(raw.get("platform_version", "13.0")),
            automation_name=automation,
            app=raw.get("app"),
            app_package=raw.get("app_package"),
            app_activity=raw.get("app_activity"),
            bundle_id=raw.get("bundle_id"),
            udid=raw.get("udid"),
            no_reset=raw.get("no_reset", False),
            full_reset=raw.get("full_reset", False),
            new_command_timeout=int(raw.get("new_command_timeout", 300)),
            auto_grant_permissions=raw.get("auto_grant_permissions", True),
            extra=raw.get("extra", {}),
        )
