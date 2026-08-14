"""
Permission handling — универсальное управление системными разрешениями.

Почти каждое мобильное приложение на старте запрашивает permissions
(камера, геолокация, уведомления). Этот модуль работает с любым SUT,
не завязан на конкретные локаторы приложения.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from mobius.logging_config import get_logger
from mobius.utils.alerts import SystemAlertHandler

logger = get_logger(__name__)


class Permission(str, Enum):
    CAMERA = "camera"
    LOCATION = "location"
    MICROPHONE = "microphone"
    CONTACTS = "contacts"
    STORAGE = "storage"
    NOTIFICATIONS = "notifications"
    PHOTOS = "photos"


class PermissionAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PermissionsManager:
    """
    Управление разрешениями приложения.
    Android: 'mobile: changePermissions' (UiAutomator2 driver команда).
    Диалоги (runtime permission prompt) обрабатываются через SystemAlertHandler.
    """

    def __init__(self, driver: Any, app_package: str | None = None) -> None:
        self._driver = driver
        self._package = app_package
        self._alerts = SystemAlertHandler(driver)

    def grant(self, permission: Permission) -> None:
        """Программно выдаёт разрешение — без прохождения UI диалога."""
        try:
            self._driver.execute_script(
                "mobile: changePermissions",
                {
                    "permissions": [permission.value],
                    "appPackage": self._package,
                    "action": "grant",
                },
            )
        except Exception as e:
            logger.warning(
                "grant(%s): mobile: changePermissions failed for package='%s' "
                "— this command is Android/UiAutomator2-only: %s",
                permission.value,
                self._package,
                e,
            )

    def revoke(self, permission: Permission) -> None:
        """Программно отзывает разрешение."""
        try:
            self._driver.execute_script(
                "mobile: changePermissions",
                {
                    "permissions": [permission.value],
                    "appPackage": self._package,
                    "action": "revoke",
                },
            )
        except Exception as e:
            logger.warning(
                "revoke(%s): mobile: changePermissions failed for package='%s': %s",
                permission.value,
                self._package,
                e,
            )

    def handle_permission_dialog(self, action: PermissionAction) -> bool:
        """
        Обрабатывает системный permission dialog если он появился на экране.
        Возвращает True если диалог был обработан, False если его не было.
        """
        if not self._alerts.is_present():
            return False
        if action == PermissionAction.DENY:
            self._alerts.dismiss()
        else:
            self._alerts.accept()
        return True
