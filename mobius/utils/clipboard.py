"""Clipboard — copy/paste тестирование, универсально для любого приложения."""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class ClipboardManager:
    """Работа с системным буфером обмена — общая ОС-функция, не завязана на SUT."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def set_text(self, text: str) -> None:
        self._driver.set_clipboard_text(text)

    def get_text(self) -> str:
        try:
            return self._driver.get_clipboard_text() or ""
        except Exception as e:
            logger.warning("get_text: driver doesn't support clipboard read: %s", e)
            return ""

    def clear(self) -> None:
        self.set_text("")
