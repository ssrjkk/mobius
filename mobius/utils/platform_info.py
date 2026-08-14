"""Platform detection helper — используется другими universal-модулями."""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


def get_platform_name(driver: Any) -> str:
    """Возвращает 'android' / 'ios' / '' — безопасно, не падает."""
    try:
        caps = driver.capabilities or {}
        return str(caps.get("platformName", "")).lower()
    except Exception as e:
        # DEBUG, не WARNING: вызывается на каждый gesture/finder вызов —
        # WARNING на каждый такой вызов завалит логи при реальной проблеме.
        logger.debug("get_platform_name: driver.capabilities unavailable: %s", e)
        return ""


def is_android(driver: Any) -> bool:
    return get_platform_name(driver) == "android"


def is_ios(driver: Any) -> bool:
    return get_platform_name(driver) == "ios"
