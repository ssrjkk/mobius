"""
WebView / Hybrid context switching — критично для гибридных приложений
(React Native с embedded WebView, Cordova, Ionic, банковские SDK для оплаты).

Без этого framework может тестировать только чистый native UI. Половина
приложений на рынке используют WebView хотя бы для одного экрана
(checkout, T&C, support chat) — этот модуль даёт доступ к ним.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)

NATIVE_CONTEXT = "NATIVE_APP"


class WebViewContext:
    """Управление переключением между native и webview контекстами."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def get_contexts(self) -> list[str]:
        """Все доступные контексты, например ['NATIVE_APP', 'WEBVIEW_com.app']."""
        try:
            return list(self._driver.contexts)
        except Exception as e:
            logger.warning(
                "get_contexts: driver doesn't support contexts (webview "
                "not available on this driver/platform): %s",
                e,
            )
            return [NATIVE_CONTEXT]

    def get_current_context(self) -> str:
        try:
            return self._driver.context or NATIVE_CONTEXT
        except Exception as e:
            logger.warning("get_current_context: failed to read context: %s", e)
            return NATIVE_CONTEXT

    def has_webview(self) -> bool:
        return any(c != NATIVE_CONTEXT for c in self.get_contexts())

    def switch_to_webview(self, name: str | None = None) -> bool:
        """
        Переключается на WebView контекст.
        name: конкретное имя контекста, или None — берёт первый WEBVIEW_*.
        Возвращает True если переключение удалось.
        """
        contexts = self.get_contexts()
        target = name
        if target is None:
            webviews = [c for c in contexts if c != NATIVE_CONTEXT]
            if not webviews:
                return False
            target = webviews[0]
        if target not in contexts:
            logger.warning(
                "switch_to_webview: context '%s' not in available contexts %s",
                target,
                contexts,
            )
            return False
        try:
            self._driver.switch_to.context(target)
            return True
        except Exception as e:
            logger.warning("switch_to_webview: switch_to.context('%s') failed: %s", target, e)
            return False

    def switch_to_native(self) -> bool:
        try:
            self._driver.switch_to.context(NATIVE_CONTEXT)
            return True
        except Exception as e:
            logger.warning("switch_to_native: failed to switch back to native context: %s", e)
            return False

    def wait_for_webview(self, timeout: int = 10, poll_frequency: float = 0.5) -> bool:
        """Ждёт появления WebView контекста — актуально сразу после навигации."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.has_webview():
                return True
            time.sleep(poll_frequency)
        return False

    @contextmanager
    def in_webview(self, name: str | None = None) -> Generator[bool, None, None]:
        """
        Context manager — переключается в webview, гарантированно
        возвращается в native даже если внутри блока было исключение.

        Использование:
            with webview_ctx.in_webview() as switched:
                if switched:
                    driver.find_element(By.CSS_SELECTOR, "#pay-button").click()
        """
        switched = self.switch_to_webview(name)
        try:
            yield switched
        finally:
            self.switch_to_native()

    def get_page_source_in_webview(self, name: str | None = None) -> str:
        """Возвращает HTML текущей WebView — полезно для дебага."""
        with self.in_webview(name) as switched:
            if not switched:
                return ""
            try:
                return str(self._driver.page_source)
            except Exception as e:
                logger.warning("get_page_source_in_webview: page_source read failed: %s", e)
                return ""
