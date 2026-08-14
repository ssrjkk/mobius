"""
Install/uninstall/update — тестирование апгрейда приложения (v1 → v2,
миграция данных, сохранение сессии через обновление). Отдельная категория
от app lifecycle в device.py (тот работает с уже установленным приложением,
этот — с самим процессом установки).
"""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class AppInstaller:
    """Установка, удаление, обновление приложения — для тестирования миграций."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def install(self, apk_or_ipa_path: str) -> bool:
        try:
            self._driver.install_app(apk_or_ipa_path)
            return True
        except Exception as e:
            logger.warning("install('%s') failed: %s", apk_or_ipa_path, e)
            return False

    def uninstall(self, app_id: str) -> bool:
        try:
            self._driver.remove_app(app_id)
            return True
        except Exception as e:
            logger.warning("uninstall('%s') failed (app may not be installed): %s", app_id, e)
            return False

    def is_installed(self, app_id: str) -> bool:
        try:
            return bool(self._driver.is_app_installed(app_id))
        except Exception as e:
            logger.warning("is_installed('%s') check failed: %s", app_id, e)
            return False

    def update(self, app_id: str, new_apk_or_ipa_path: str) -> bool:
        """
        Обновление "поверх" — не удаляет приложение, данные пользователя сохраняются.
        Именно так ведут себя реальные апдейты через Play Store / App Store.
        """
        try:
            self._driver.install_app(new_apk_or_ipa_path, replace=True)
            return True
        except Exception as e:
            logger.warning(
                "update('%s', '%s') failed — check signing keys match "
                "(Android rejects install with replace=True if signatures differ): %s",
                app_id,
                new_apk_or_ipa_path,
                e,
            )
            return False

    def clean_install(self, app_id: str, apk_or_ipa_path: str) -> bool:
        """Полная переустановка: uninstall (если стоит) → install с чистого листа."""
        if self.is_installed(app_id):
            if not self.uninstall(app_id):
                logger.warning(
                    "clean_install('%s'): uninstall failed, aborting before install",
                    app_id,
                )
                return False
        return self.install(apk_or_ipa_path)

    def get_app_strings(self, language: str | None = None) -> dict[str, Any]:
        """Возвращает все строковые ресурсы приложения — для проверки локализации без UI-обхода."""
        try:
            if language:
                return dict(self._driver.app_strings(language))
            return dict(self._driver.app_strings())
        except Exception as e:
            logger.warning("get_app_strings(language=%s) failed: %s", language, e)
            return {}
