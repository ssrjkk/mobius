"""Screenshot utility — авто-скриншот при падении теста."""

from __future__ import annotations

import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import allure

from mobius.logging_config import get_logger

logger = get_logger(__name__)

# Разделители путей (прямые/обратные слеши), по которым имя режется на сегменты
# перед проверкой на traversal. Обратный слэш нейтрализуется и на POSIX — он
# входит в allowlist-замену ниже.
_PATH_SEPARATORS = re.compile(r"[/\\]")

# Allowlist безопасных символов имени файла: латиница, цифры, '_', '-' и
# пробел. Всё остальное (разделители, drive-буквы 'C:', ':' из UNC/ADS,
# точки, кавычки, '*?<>|', управляющие символы, non-ASCII) заменяется на '_'.
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_ -]+")


def artifact_path(base_dir: Path, name: str, suffix: str) -> Path:
    """
    Единственная точка сборки путей артефактов для всего mobius.utils
    (скриншоты, видео, baseline-ы, diff-изображения).

    Аргумент `name` приходит из недоверенных источников (test id'ы, имена
    allure-вложений, имена файлов, полученные с устройства), поэтому это
    граница безопасности. Правила:

      1. сегмент, ровно равный '..' (по любому разделителю путей), → ValueError;
      2. ведущие '.'-сегменты и любые символы вне allowlist нейтрализуются
         заменой на '_' (гасятся '/', '\\', ':', drive-буквы, UNC-префиксы,
         точки, управляющие символы);
      3. пустое после очистки имя → ValueError;
      4. финальный путь после resolve() обязан оставаться внутри base_dir —
         иначе ValueError вместо молчаливой записи наружу (защита от
         symlink/junction, созданного внутри base_dir).

    Обычные имена остаются пригодными: 'login_screen' → 'login_screen',
    'catalog/item 5' → '<base>/catalog_item 5<suffix>'.
    """
    for segment in _PATH_SEPARATORS.split(name):
        if segment == "..":
            raise ValueError(f"artifact name {name!r} contains '..' traversal segment")
    safe = _UNSAFE_CHARS.sub("_", name).strip()
    if not safe:
        raise ValueError(f"artifact name {name!r} is empty after sanitization")
    base = base_dir.resolve()
    path = (base / f"{safe}{suffix}").resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"artifact path {path} escapes base dir {base}")
    return path


class ScreenshotUtils:
    def __init__(self, driver: Any, output_dir: str = "reports/screenshots") -> None:
        self._driver = driver
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def take(self, name: str = "") -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{name}_{ts}" if name else f"screenshot_{ts}"
        path = artifact_path(self._dir, stem, ".png")
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
