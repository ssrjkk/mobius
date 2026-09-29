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
from mobius.utils.capability import read_capability
from mobius.utils.driver_health import rethrow_if_driver_dead

logger = get_logger(__name__)


class Permission(str, Enum):
    CAMERA = "camera"
    LOCATION = "location"
    MICROPHONE = "microphone"
    CONTACTS = "contacts"
    STORAGE = "storage"
    NOTIFICATIONS = "notifications"
    PHOTOS = "photos"


# `mobile: changePermissions` понимает только настоящие имена разрешений
# Android (константы вида android.permission.*) либо псевдонимы 'all' /
# 'appops'. Отправить сюда "camera" — значит получить ошибку драйвера, которую
# best-effort хелпер проглотил бы: тест «с выданной камерой» запускался бы с
# невыданной. Поэтому семантическое имя enum переводится в список констант.
_ANDROID_PERMISSIONS: dict[Permission, tuple[str, ...]] = {
    Permission.CAMERA: ("android.permission.CAMERA",),
    Permission.LOCATION: (
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
    ),
    Permission.MICROPHONE: ("android.permission.RECORD_AUDIO",),
    Permission.CONTACTS: ("android.permission.READ_CONTACTS",),
    Permission.STORAGE: (
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
    ),
    Permission.NOTIFICATIONS: ("android.permission.POST_NOTIFICATIONS",),
    Permission.PHOTOS: ("android.permission.READ_MEDIA_IMAGES",),
}


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
        self._package = app_package or ""
        self._alerts = SystemAlertHandler(driver)

    def _resolve_package(self) -> str:
        """Пакет из аргумента конструктора, иначе из capabilities драйвера."""
        if self._package:
            return self._package
        return read_capability(
            self._driver, "appium:appPackage", "appPackage", caller="PermissionsManager"
        )

    def _change(self, permission: Permission, action: str) -> bool:
        package = self._resolve_package()
        if not package:
            logger.warning(
                "%s(%s): app package is unknown — pass app_package to PermissionsManager "
                "or set appium:appPackage in capabilities. Permission was NOT changed.",
                action,
                permission.value,
            )
            return False
        try:
            self._driver.execute_script(
                "mobile: changePermissions",
                {
                    "permissions": list(_ANDROID_PERMISSIONS[permission]),
                    "appPackage": package,
                    "action": action,
                },
            )
            return True
        except Exception as e:
            rethrow_if_driver_dead(e)
            logger.warning(
                "%s(%s): mobile: changePermissions failed for package='%s' "
                "— this command is Android/UiAutomator2-only: %s",
                action,
                permission.value,
                package,
                e,
            )
            return False

    def grant(self, permission: Permission) -> bool:
        """
        Программно выдаёт разрешение — без прохождения UI диалога.
        True только если драйвер подтвердил команду.
        """
        return self._change(permission, "grant")

    def revoke(self, permission: Permission) -> bool:
        """Программно отзывает разрешение. True только если драйвер подтвердил команду."""
        return self._change(permission, "revoke")

    def handle_permission_dialog(self, action: PermissionAction) -> bool:
        """
        Обрабатывает системный permission dialog если он появился на экране.
        Возвращает True только когда диалог был найден И обработан: False при
        отсутствующем диалоге и при потухшей кнопке — чтобы вызывающий код мог
        отличить «разрешили» от «нажали, но не вышло».
        """
        if not self._alerts.is_present():
            return False
        if action == PermissionAction.DENY:
            return self._alerts.dismiss()
        return self._alerts.accept()
