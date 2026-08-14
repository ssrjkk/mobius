"""
Screen recording — видео вместо скриншота при падении сложных сценариев.
Для многошаговых flow (checkout, onboarding) один скриншот на падении часто
не объясняет ЧТО пошло не так за 10 шагов до этого — видео решает эту
проблему полностью.
"""

from __future__ import annotations

import base64
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from mobius.logging_config import get_logger

logger = get_logger(__name__)


class ScreenRecorder:
    """Запись видео экрана через Appium 'start/stop_recording_screen'."""

    def __init__(self, driver: Any, output_dir: str = "reports/recordings") -> None:
        self._driver = driver
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._recording = False

    def start(self, max_duration_sec: int = 180) -> bool:
        if self._recording:
            logger.warning("start: already recording — call stop_and_save()/discard() first")
            return False
        try:
            self._driver.start_recording_screen(
                timeLimit=str(max_duration_sec),
                forceRestart=True,
            )
            self._recording = True
            return True
        except Exception as e:
            logger.warning("start: start_recording_screen failed: %s", e)
            return False

    def stop_and_save(self, filename: str) -> str | None:
        """Останавливает запись и сохраняет .mp4 файл. Возвращает путь или None."""
        if not self._recording:
            logger.warning("stop_and_save('%s'): no active recording to stop", filename)
            return None
        try:
            encoded = self._driver.stop_recording_screen()
            self._recording = False
            if isinstance(encoded, bytes):
                encoded = encoded.decode()
            data = base64.b64decode(encoded)
            path = self._dir / f"{filename}.mp4"
            path.write_bytes(data)
            return str(path)
        except Exception as e:
            logger.warning("stop_and_save('%s') failed: %s", filename, e)
            self._recording = False
            return None

    def discard(self) -> None:
        """Останавливает запись без сохранения — для успешных тестов (экономим место)."""
        if self._recording:
            try:
                self._driver.stop_recording_screen()
            except Exception as e:
                logger.debug("discard: stop_recording_screen failed (already stopped?): %s", e)
            self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    @contextmanager
    def record_test(self, test_name: str, save_on: bool = True) -> Generator[None, None, None]:
        """
        Context manager — записывает тест, сохраняет видео только если save_on=True
        (типичный паттерн: сохранять только при провале теста).

        Использование:
            with recorder.record_test("test_checkout", save_on=test_failed):
                run_test_steps()
        """
        self.start()
        try:
            yield
        finally:
            if save_on:
                self.stop_and_save(test_name)
            else:
                self.discard()
