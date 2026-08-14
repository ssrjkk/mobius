"""
Биометрическая аутентификация — Face ID / Touch ID / fingerprint симуляция
на эмуляторе/симуляторе. Почти каждое банковское, платёжное или health
приложение использует биометрию как основной или дополнительный auth —
без этого framework не может протестировать значительную часть таких
приложений вообще.

iOS: 'mobile: sendBiometricMatch' — стандартная XCUITest driver команда
     (требует Simulator, не работает на реальном устройстве).
Android: биометрия эмулируется через enrollment + 'mobile: fingerprint'
     (UiAutomator2 driver, тоже только на эмуляторе с включенным Fingerprint).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from mobius.logging_config import get_logger
from mobius.utils.platform_info import is_android, is_ios

logger = get_logger(__name__)


class BiometricType(str, Enum):
    FACE_ID = "faceId"
    TOUCH_ID = "touchId"
    FINGERPRINT = "fingerprint"


class BiometricSimulator:
    """
    Симулирует биометрическую аутентификацию на эмуляторе/симуляторе.
    Работает только в CI/локальной разработке с эмулятором — на реальных
    устройствах ОС не позволяет программно подделать биометрию (это фича
    безопасности, а не ограничение framework).
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def is_enrolled(self) -> bool:
        """iOS Simulator — проверяет включена ли биометрия в настройках симулятора."""
        try:
            result = self._driver.execute_script("mobile: isBiometricEnrolled")
            return bool(result)
        except Exception as e:
            logger.warning(
                "is_enrolled: mobile: isBiometricEnrolled failed — iOS Simulator-only command: %s",
                e,
            )
            return False

    def enroll(self, enrolled: bool = True) -> bool:
        """iOS Simulator — программно включает/выключает биометрию в Settings."""
        try:
            self._driver.execute_script("mobile: enrollBiometric", {"isEnabled": enrolled})
            return True
        except Exception as e:
            logger.warning("enroll(%s): mobile: enrollBiometric failed: %s", enrolled, e)
            return False

    def send_match(self, match: bool = True) -> bool:
        """
        Симулирует успешную (match=True) или неуспешную (match=False)
        попытку биометрической аутентификации.
        """
        try:
            if is_ios(self._driver):
                self._driver.execute_script(
                    "mobile: sendBiometricMatch",
                    {
                        "type": "faceId",
                        "match": match,
                    },
                )
            elif is_android(self._driver):
                self._driver.execute_script(
                    "mobile: fingerprint",
                    {
                        "fingerprintId": 1 if match else 0,
                    },
                )
            else:
                logger.warning(
                    "send_match: unknown platform (not android/ios) — "
                    "cannot determine which biometric command to use",
                )
                return False
            return True
        except Exception as e:
            logger.warning("send_match(match=%s): biometric command failed: %s", match, e)
            return False

    def simulate_success(self) -> bool:
        return self.send_match(match=True)

    def simulate_failure(self) -> bool:
        return self.send_match(match=False)
