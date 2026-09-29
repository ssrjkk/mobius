"""Deep link utilities — открытие экранов через URI схему."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mobius.utils.capability import read_capability


class DeepLink:
    def __init__(self, driver: Any, scheme: str = "myapp") -> None:
        self._driver = driver
        self._scheme = scheme

    def _get_package(self) -> str:
        """Пакет из capabilities сессии; '' если его нечем прочитать."""
        return read_capability(self._driver, "appium:appPackage", "appPackage", caller="DeepLink")

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
        """
        Строит URL без открытия — для юнит тестирования логики.

        Путь и параметры кодируются в percent-encoding: без этого `&`, `=`,
        `#` или пробел в значении молча ломают либо переопределяют весь query,
        и открывается не тот экран, который запрашивали.
        """
        url = f"{self._scheme}://{quote(path, safe='/')}"
        if params:
            qs = "&".join(
                f"{quote(str(k), safe='')}={quote(str(v), safe='')}"
                for k, v in sorted(params.items())
            )
            url = f"{url}?{qs}"
        return url
