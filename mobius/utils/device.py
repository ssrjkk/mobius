"""
Device-level actions — универсальные, не зависят от тестируемого приложения.

В отличие от Screen Objects (которые знают конкретные локаторы одного SUT),
эти действия работают с ЛЮБЫМ Android/iOS приложением: rotation, lock screen,
hardware keys, app lifecycle, geolocation. Это база для AQA smoke-проверок
на новом/незнакомом приложении.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class Orientation(str, Enum):
    PORTRAIT = "PORTRAIT"
    LANDSCAPE = "LANDSCAPE"


class HardwareKey(int, Enum):
    """Android KeyEvent коды — https://developer.android.com/reference/android/view/KeyEvent"""

    BACK = 4
    HOME = 3
    MENU = 82
    VOLUME_UP = 24
    VOLUME_DOWN = 25
    POWER = 26
    CAMERA = 27
    ENTER = 66
    APP_SWITCH = 187


class DeviceActions:
    """Универсальные действия с устройством — работают с любым SUT."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    # ── Orientation ──────────────────────────────────────────────────────────

    def get_orientation(self) -> str:
        return str(self._driver.orientation)

    def set_orientation(self, orientation: Orientation) -> None:
        self._driver.orientation = orientation.value

    def rotate_to_landscape(self) -> None:
        self.set_orientation(Orientation.LANDSCAPE)

    def rotate_to_portrait(self) -> None:
        self.set_orientation(Orientation.PORTRAIT)

    def is_landscape(self) -> bool:
        return self.get_orientation() == Orientation.LANDSCAPE.value

    # ── Lock screen ──────────────────────────────────────────────────────────

    def lock(self, seconds: int = 0) -> None:
        self._driver.lock(seconds)

    def unlock(self) -> None:
        self._driver.unlock()

    def is_locked(self) -> bool:
        return bool(self._driver.is_locked())

    # ── Hardware keys (Android) ─────────────────────────────────────────────

    def press_key(self, key: HardwareKey) -> None:
        self._driver.press_keycode(key.value)

    def press_back(self) -> None:
        self.press_key(HardwareKey.BACK)

    def press_home(self) -> None:
        self.press_key(HardwareKey.HOME)

    def press_app_switch(self) -> None:
        self.press_key(HardwareKey.APP_SWITCH)

    # ── App lifecycle ────────────────────────────────────────────────────────

    def background_app(self, seconds: int = 2) -> None:
        """Сворачивает приложение на N секунд, затем возвращает на передний план."""
        self._driver.background_app(seconds)

    def activate_app(self, package: str) -> None:
        self._driver.activate_app(package)

    def terminate_app(self, package: str) -> bool:
        return bool(self._driver.terminate_app(package))

    def is_app_installed(self, package: str) -> bool:
        return bool(self._driver.is_app_installed(package))

    def reset_app(self, package: str) -> None:
        """Полный сброс состояния: terminate + relaunch. Полезно между тестами."""
        try:
            self._driver.terminate_app(package)
        except Exception as e:
            logger.warning(
                "reset_app: terminate_app('%s') failed (app likely wasn't "
                "running) — proceeding to activate_app anyway: %s",
                package,
                e,
            )
        self._driver.activate_app(package)

    # ── Geolocation ──────────────────────────────────────────────────────────

    def set_location(self, latitude: float, longitude: float, altitude: float = 0.0) -> None:
        self._driver.set_location(latitude, longitude, altitude)

    def get_location(self) -> dict[str, Any]:
        loc = self._driver.location or {}
        return {
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
        }

    # ── Misc ─────────────────────────────────────────────────────────────────

    def shake(self) -> None:
        """iOS-only — эмулирует встряхивание устройства. No-op на Android."""
        try:
            self._driver.shake()
        except Exception as e:
            logger.warning(
                "shake() failed — likely called on Android where this "
                "command doesn't exist (iOS-only): %s",
                e,
            )

    def get_device_time(self) -> str:
        return str(self._driver.device_time)

    def get_current_activity(self) -> str:
        """Android-only — текущая Activity. Полезно для проверки навигации."""
        try:
            return self._driver.current_activity or ""
        except Exception as e:
            logger.warning(
                "get_current_activity() failed — likely called on iOS "
                "where Activity concept doesn't exist: %s",
                e,
            )
            return ""
