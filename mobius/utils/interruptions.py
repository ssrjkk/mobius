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
from mobius.utils.capability import read_capability
from mobius.utils.driver_health import rethrow_if_driver_dead
from mobius.utils.shell_safety import checked_console_text, checked_package, checked_phone

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
        number = checked_phone(phone_number, caller="incoming_call")
        return self._emu("gsm", "call", number, label="gsm call")

    def end_call(self, phone_number: str = "5551234567") -> bool:
        """Завершает симулированный звонок."""
        number = checked_phone(phone_number, caller="end_call")
        return self._emu("gsm", "cancel", number, label="gsm cancel")

    def incoming_sms(self, phone_number: str = "5551234567", message: str = "Test SMS") -> bool:
        """Симулирует входящее SMS."""
        return self._emu(
            "sms",
            "send",
            checked_phone(phone_number, caller="incoming_sms"),
            checked_console_text(message, caller="incoming_sms"),
            label="sms send",
        )

    def set_battery_level(self, percent: int) -> bool:
        """Симулирует уровень заряда батареи (0-100) — для low-battery сценариев."""
        percent = max(0, min(100, percent))
        return self._emu("power", "capacity", str(percent), label="power capacity")

    def set_battery_status_charging(self, charging: bool = True) -> bool:
        status = "charging" if charging else "discharging"
        return self._emu("power", "status", status, label="power status")

    def simulate_low_memory(self) -> bool:
        """Триггерит onTrimMemory/onLowMemory в приложении — тест устойчивости к OOM."""
        package = self._capabilities_package()
        if not package:
            logger.warning(
                "simulate_low_memory: no appium:appPackage in capabilities "
                "— can't target a specific app",
            )
            return False
        # Проверяем до try: падение из-за битого имени пакета — не «команда не
        # поддержана эмулятором», а ошибка конфигурации, и глотать её нельзя.
        checked_package(package, caller="simulate_low_memory")
        try:
            self._driver.execute_script(
                "mobile: shell",
                {
                    "command": "am",
                    "args": ["send-trim-memory", package, "RUNNING_CRITICAL"],
                },
            )
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning(
                "simulate_low_memory: 'am send-trim-memory' failed — "
                "requires Android emulator with shell access: %s",
                e,
            )
            return False

    def _capabilities_package(self) -> str:
        return read_capability(
            self._driver, "appium:appPackage", "appPackage", caller="simulate_low_memory"
        )

    def _emu(self, *args: str, label: str) -> bool:
        """
        Выполняет команду emulator console через 'mobile: shell'.

        Аргументы передаются списком: старый вариант склеивал команду в строку
        и резал её обратно через split(), из-за чего многословный текст SMS
        распадался на отдельные аргументы. `label` — только имя команды, чтобы
        номер телефона и тело SMS не попадали в логи и в Allure.
        """
        try:
            self._driver.execute_script(
                "mobile: shell",
                {"command": "emu", "args": list(args)},
            )
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning(
                "_emu(%s) failed — requires Android AVD emulator "
                "(not a real device, not iOS Simulator): %s",
                label,
                e,
            )
            return False
