"""
File push/pull — тестирование загрузки фото, экспорта документов, скачанных файлов.

Без этого нельзя протестировать ни один экран с картинками (аватар, галерея,
чат с вложениями) или файлами (экспорт PDF, скачанные документы) — типичный
слепой пробел в мобильных framework, которые фокусируются только на UI.

Appium методы push_file/pull_file реальны и проверены:
inspect.signature подтверждает сигнатуры на установленном клиенте.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class FileTransfer:
    """Копирование файлов между тестовой машиной и устройством/эмулятором."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def push_file(self, local_path: str, device_path: str) -> bool:
        """
        Загружает локальный файл на устройство.
        device_path (Android): '/sdcard/Download/photo.jpg'
        device_path (iOS): '@com.app.bundle:documents/photo.jpg' (app container путь)
        """
        try:
            data = Path(local_path).read_bytes()
            encoded = base64.b64encode(data).decode()
            self._driver.push_file(device_path, base64data=encoded)
            return True
        except Exception as e:
            logger.warning("push_file('%s' -> '%s') failed: %s", local_path, device_path, e)
            return False

    def push_test_image(self, device_path: str, width: int = 200, height: int = 200) -> bool:
        """
        Генерирует простое тестовое изображение и загружает его на устройство —
        удобно для тестов "загрузи фото" без необходимости держать fixture-файлы.
        """
        try:
            import io

            from PIL import Image

            img = Image.new("RGB", (width, height), color=(100, 150, 200))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            encoded = base64.b64encode(buf.getvalue()).decode()
            self._driver.push_file(device_path, base64data=encoded)
            return True
        except Exception as e:
            logger.warning("push_test_image('%s', %dx%d) failed: %s", device_path, width, height, e)
            return False

    def pull_file(self, device_path: str, local_path: str) -> bool:
        """Скачивает файл с устройства локально — проверить экспорт/скачанное."""
        try:
            encoded = self._driver.pull_file(device_path)
            data = base64.b64decode(encoded)
            Path(local_path).write_bytes(data)
            return True
        except Exception as e:
            logger.warning("pull_file('%s' -> '%s') failed: %s", device_path, local_path, e)
            return False

    def pull_folder(self, device_path: str, local_path: str) -> bool:
        """Скачивает содержимое папки устройства как zip и распаковывает локально."""
        try:
            import io
            import zipfile

            encoded = self._driver.pull_folder(device_path)
            data = base64.b64decode(encoded)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(local_path)
            return True
        except Exception as e:
            logger.warning("pull_folder('%s' -> '%s') failed: %s", device_path, local_path, e)
            return False

    def file_exists_on_device(self, device_path: str) -> bool:
        """Проверяет наличие файла попыткой pull — без записи на диск теста."""
        try:
            self._driver.pull_file(device_path)
            return True
        except Exception as e:
            logger.debug("file_exists_on_device('%s'): not found: %s", device_path, e)
            return False
