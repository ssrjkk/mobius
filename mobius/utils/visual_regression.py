"""
Visual regression testing — pixel-diff между baseline и текущим скриншотом.

Функциональные тесты (find_element, assert text) не ловят "кнопка сместилась
на 20px" или "цвет фона изменился". Visual regression — отдельная категория
багов, критичная для UI-heavy приложений (e-commerce, банкинг, дизайн-системы).

Зависимость: Pillow (входит в pyproject.toml [test]).
"""

from __future__ import annotations

import base64
import functools
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from PIL import Image, ImageChops

from mobius.utils.screenshot import artifact_path

# Порог «шума»: пиксель считается изменённым, если максимальная поканальная
# |разница| >= 10 из 255 (antonim старого histogram[10:] по L-каналу).
_NOISE_FLOOR = 10


@dataclass
class VisualDiffResult:
    match: bool
    diff_percentage: float
    baseline_path: str
    actual_path: str
    diff_path: str | None = None
    reason: str | None = None

    def summary(self) -> str:
        if self.reason:
            return f"Visual diff skipped: {self.reason}"
        status = "MATCH" if self.match else "MISMATCH"
        return f"{status}: {self.diff_percentage:.2f}% pixels differ"


class VisualRegression:
    """
    Сравнивает текущий скриншот с сохранённым baseline.

    Первый прогон на новом экране создаёт baseline автоматически
    (типичный паттерн snapshot-тестирования) — сравнение начинается
    со второго прогона.

    Все caller-supplied имена (test id'ы, имена allure-вложений, baseline-ы,
    полученные с устройства) проходят через artifact_path — единственную
    точку нейтрализации path traversal.
    """

    def __init__(
        self,
        driver: Any,
        baseline_dir: str = "visual_baselines",
        diff_dir: str = "reports/visual_diffs",
        threshold_pct: float = 0.5,
    ) -> None:
        self._driver = driver
        self._baseline_dir = Path(baseline_dir)
        self._diff_dir = Path(diff_dir)
        self._threshold = threshold_pct
        self._baseline_dir.mkdir(parents=True, exist_ok=True)
        self._diff_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _open_rgb(source: str | Path | BinaryIO) -> Image.Image:
        """
        Открывает PNG и приводит его к 'RGB'.

        Защита для изображений из недоверенных источников (baseline-ы с
        устройства, base64 со скриншота):
          * Pillow-бюджет пикселей Image.MAX_IMAGE_PIXELS остаётся
            библиотечным default-ом — мы его НЕ повышаем;
          * DecompressionBombError НЕ глотается — поднимается как ValueError
            с понятным сообщением;
          * file handle гарантированно закрывается context manager-ом
            (без утечки дескрипторов на битых/огромных файлах).
        """
        try:
            with Image.open(source) as image:
                return image.convert("RGB")
        except Image.DecompressionBombError as exc:
            raise ValueError(f"image exceeds Pillow pixel budget MAX_IMAGE_PIXELS: {exc}") from exc

    def _take_screenshot(self) -> Image.Image:
        png_bytes = base64.b64decode(self._driver.get_screenshot_as_base64())
        return self._open_rgb(io.BytesIO(png_bytes))

    def compare(self, name: str, threshold_pct: float | None = None) -> VisualDiffResult:
        """
        Сравнивает текущий экран с baseline/{name}.png.
        Если baseline не существует — создаёт его и возвращает match=True
        (первый прогон всегда проходит, как в snapshot-тестировании).
        """
        threshold = threshold_pct if threshold_pct is not None else self._threshold
        baseline_path = artifact_path(self._baseline_dir, name, ".png")
        actual_path = artifact_path(self._diff_dir, f"{name}_actual", ".png")

        current = self._take_screenshot()
        current.save(actual_path)

        if not baseline_path.exists():
            current.save(baseline_path)
            return VisualDiffResult(
                match=True,
                diff_percentage=0.0,
                baseline_path=str(baseline_path),
                actual_path=str(actual_path),
                reason="baseline created (first run)",
            )

        baseline = self._open_rgb(baseline_path)

        if baseline.size != current.size:
            return VisualDiffResult(
                match=False,
                diff_percentage=100.0,
                baseline_path=str(baseline_path),
                actual_path=str(actual_path),
                reason=f"size mismatch: baseline={baseline.size} actual={current.size}",
            )

        diff_pct, diff_image = self._pixel_diff(baseline, current)
        diff_path = None
        if diff_pct > 0:
            diff_path = artifact_path(self._diff_dir, f"{name}_diff", ".png")
            diff_image.save(diff_path)

        return VisualDiffResult(
            match=diff_pct <= threshold,
            diff_percentage=diff_pct,
            baseline_path=str(baseline_path),
            actual_path=str(actual_path),
            diff_path=str(diff_path) if diff_path else None,
        )

    def _pixel_diff(self, baseline: Image.Image, current: Image.Image) -> tuple[float, Image.Image]:
        """
        Возвращает (доля изменённых пикселей в процентах, карта-разница).

        Возвращаемое число: доля (0.0–100.0, округление до 4 знаков) пикселей,
        у которых МАКСИМАЛЬНАЯ поканальная |разница| >= _NOISE_FLOOR (10/255)
        от общего числа пикселей. Входные изображения сначала приводятся к
        общей моде (_common_mode), поэтому гистограмма всегда одноканальная
        (256 бинов), и срез histogram[_NOISE_FLOOR:] означает ровно то, что
        задумывалось: «пиксели, изменённые сверх порога шума».

        Старая реализация брала sum(histogram[10:]) от L-проекции RGB-карты
        разницы: изменения отдельных каналов взвешивались коэффициентами
        яркости Rec.601 (blue=0.114, red=0.299), из-за чего, например, чистое
        изменение синего канала на 86/255 давало L=9 и НЕ считалось изменением.
        """
        mode = self._common_mode(baseline, current)
        diff = ImageChops.difference(baseline.convert(mode), current.convert(mode))
        # diff.split() — по одному 'L'-каналу на канал изображения;
        # ImageChops.lighter — попиксельный максимум: получаем одну
        # одноканальную карту magnitude, её гистограмма — ровно 256 бинов.
        magnitude = functools.reduce(ImageChops.lighter, diff.split())
        histogram = magnitude.histogram()
        total_pixels = magnitude.width * magnitude.height
        changed_pixels = sum(histogram[_NOISE_FLOOR:])
        diff_pct = (changed_pixels / total_pixels) * 100
        return round(diff_pct, 4), diff

    @staticmethod
    def _common_mode(baseline: Image.Image, current: Image.Image) -> str:
        """
        Общая мода для поканального сравнения: одинаковые моды используются
        как есть; при расхождении любое изображение с альфа-каналом
        ('A'/'LA'/'RGBA'/'PA') сводится к 'RGBA', иначе — к 'RGB'.
        """
        if baseline.mode == current.mode:
            return baseline.mode
        if "A" in baseline.mode or "A" in current.mode:
            return "RGBA"
        return "RGB"

    def update_baseline(self, name: str) -> None:
        """Явно перезаписывает baseline текущим скриншотом — после review UI изменений."""
        current = self._take_screenshot()
        current.save(artifact_path(self._baseline_dir, name, ".png"))

    def assert_matches(self, name: str, threshold_pct: float | None = None) -> None:
        result = self.compare(name, threshold_pct)
        assert result.match, (
            f"Visual regression on '{name}': {result.summary()} "
            f"(baseline={result.baseline_path}, diff={result.diff_path})"
        )
