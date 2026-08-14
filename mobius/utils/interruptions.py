"""
Interruption testing — входящий звонок/SMS во время выполнения теста.

Классический AQA-сценарий: "что произойдёт с заполненной формой если во
время ввода позвонили" или "сохранится ли черновик сообщения при входящем
SMS". Приложения часто падают или теряют данные именно на interruption —
это отдельный класс багов, который обычный функциональный тест не найдёт.

Работает через emulator console команды (Android AVD) — 'mobile: shell'
с adb emu commands. Требует эмулятор, не работает на реальном устройстве
и не работает на iOS Simulator (нет аналога телефонных прерываний).
"""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class InterruptionSimulator:
    """
    Симулирует системные прерывания на Android эмуляторе через adb emu команды.
    Требует запущенный AVD (Android Virtual Device), недоступно на реальных
    устройствах и на iOS.
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def incoming_call(self, phone_number: str = "5551234567") -> bool:
        """Симулирует входящий звонок с указанного номера."""
        return self._shell(f"gsm call {phone_number}")

    def end_call(self, phone_number: str = "5551234567") -> bool:
        """Завершает симулированный звонок."""
        return self._shell(f"gsm cancel {phone_number}")

    def incoming_sms(self, phone_number: str = "5551234567", message: str = "Test SMS") -> bool:
        """Симулирует входящее SMS."""
        return self._shell(f'sms send {phone_number} "{message}"')

    def set_battery_level(self, percent: int) -> bool:
        """Симулирует уровень заряда батареи (0-100) — для low-battery сценариев."""
        percent = max(0, min(100, percent))
        return self._shell(f"power capacity {percent}")

    def set_battery_status_charging(self, charging: bool = True) -> bool:
        status = "charging" if charging else "discharging"
        return self._shell(f"power status {status}")

    def simulate_low_memory(self) -> bool:
        """Триггерит onTrimMemory/onLowMemory в приложении — тест устойчивости к OOM."""
        try:
            package = self._driver.capabilities.get("appium:appPackage", "")
            if not package:
                logger.warning(
                    "simulate_low_memory: no appium:appPackage in capabilities "
                    "— can't target a specific app",
                )
                return False
            self._driver.execute_script(
                "mobile: shell",
                {"command": "am", "args": ["send-trim-memory", package, "RUNNING_CRITICAL"]},
            )
            return True
        except Exception as e:
            logger.warning(
                "simulate_low_memory: 'am send-trim-memory' failed — "
                "requires Android emulator with shell access: %s",
                e,
            )
            return False

    def _shell(self, emu_command: str) -> bool:
        """Выполняет emulator console команду через 'mobile: shell'."""
        try:
            self._driver.execute_script(
                "mobile: shell",
                {"command": "emu", "args": emu_command.split()},
            )
            return True
        except Exception as e:
            logger.warning(
                "_shell('%s') failed — requires Android AVD emulator "
                "(not a real device, not iOS Simulator): %s",
                emu_command,
                e,
            )
            return False
