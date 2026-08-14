"""Deep link utilities — открытие экранов через URI схему."""

from __future__ import annotations

from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class DeepLink:
    def __init__(self, driver: Any, scheme: str = "myapp") -> None:
        self._driver = driver
        self._scheme = scheme

    def _get_package(self) -> str:
        """Безопасно получаем app package из capabilities."""
        try:
            caps = self._driver.capabilities or {}
            return caps.get("appium:appPackage") or caps.get("appPackage") or ""
        except Exception as e:
            logger.warning(
                "_get_package: couldn't read capabilities from driver — "
                "deep link will be sent without a package (may fail on Android): %s",
                e,
            )
            return ""

    def open(self, path: str, params: dict[str, Any] | None = None) -> None:
        """Открывает deep link через Appium mobile: deepLink команду."""
        url = self.build_url(path, params)
        package = self._get_package()
        self._driver.execute_script("mobile: deepLink", {"url": url, "package": package})

    def open_product(self, product_id: int) -> None:
        self.open(f"product/{product_id}")

    def open_cart(self) -> None:
        self.open("cart")

    def open_login(self) -> None:
        self.open("login")

    def open_checkout(self) -> None:
        self.open("checkout")

    def build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Строит URL без открытия — для юнит тестирования логики."""
        url = f"{self._scheme}://{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            url = f"{url}?{qs}"
        return url
