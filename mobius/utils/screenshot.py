"""Screenshot utility — авто-скриншот при падении теста."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import allure

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class ScreenshotUtils:
    def __init__(self, driver: Any, output_dir: str = "reports/screenshots") -> None:
        self._driver = driver
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def take(self, name: str = "") -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.png" if name else f"screenshot_{ts}.png"
        path = self._dir / filename
        self._driver.save_screenshot(str(path))
        return path

    def take_allure(self) -> bytes:
        return base64.b64decode(self._driver.get_screenshot_as_base64())

    def attach_to_allure(self, name: str = "Screenshot") -> None:
        try:
            png = self._driver.get_screenshot_as_png()
            allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)
        except Exception as e:
            logger.warning(
                "attach_to_allure('%s'): get_screenshot_as_png/allure.attach failed, "
                "falling back to saving PNG file locally instead: %s",
                name,
                e,
            )
            self.take(name)

    def attach_page_source(self, name: str = "Page source") -> None:
        try:
            source = self._driver.page_source
            allure.attach(source, name=name, attachment_type=allure.attachment_type.XML)
        except Exception as e:
            logger.warning("attach_page_source('%s'): page_source read/attach failed: %s", name, e)
