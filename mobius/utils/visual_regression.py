"""
Visual regression testing — pixel-diff между baseline и текущим скриншотом.

Функциональные тесты (find_element, assert text) не ловят "кнопка сместилась
на 20px" или "цвет фона изменился". Visual regression — отдельная категория
багов, критичная для UI-heavy приложений (e-commerce, банкинг, дизайн-системы).

Зависимость: Pillow (входит в pyproject.toml [test]).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops


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

    def _take_screenshot(self) -> Image.Image:
        png_bytes = base64.b64decode(self._driver.get_screenshot_as_base64())
        import io

        return Image.open(io.BytesIO(png_bytes)).convert("RGB")

    def compare(self, name: str, threshold_pct: float | None = None) -> VisualDiffResult:
        """
        Сравнивает текущий экран с baseline/{name}.png.
        Если baseline не существует — создаёт его и возвращает match=True
        (первый прогон всегда проходит, как в snapshot-тестировании).
        """
        threshold = threshold_pct if threshold_pct is not None else self._threshold
        baseline_path = self._baseline_dir / f"{name}.png"
        actual_path = self._diff_dir / f"{name}_actual.png"

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

        baseline = Image.open(baseline_path).convert("RGB")

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
            diff_path = self._diff_dir / f"{name}_diff.png"
            diff_image.save(diff_path)

        return VisualDiffResult(
            match=diff_pct <= threshold,
            diff_percentage=diff_pct,
            baseline_path=str(baseline_path),
            actual_path=str(actual_path),
            diff_path=str(diff_path) if diff_path else None,
        )

    def _pixel_diff(self, baseline: Image.Image, current: Image.Image) -> tuple[float, Image.Image]:
        diff = ImageChops.difference(baseline, current)
        bbox = diff.getbbox()
        if bbox is None:
            return 0.0, diff

        histogram = diff.convert("L").histogram()
        total_pixels = baseline.width * baseline.height
        # histogram[i] = количество пикселей с яркостью разницы == i.
        # Игнорируем яркость < 10 — типичный шум антиалиасинга/сжатия PNG.
        changed_pixels = sum(histogram[10:])
        diff_pct = (changed_pixels / total_pixels) * 100
        return round(diff_pct, 4), diff

    def update_baseline(self, name: str) -> None:
        """Явно перезаписывает baseline текущим скриншотом — после review UI изменений."""
        current = self._take_screenshot()
        current.save(self._baseline_dir / f"{name}.png")

    def assert_matches(self, name: str, threshold_pct: float | None = None) -> None:
        result = self.compare(name, threshold_pct)
        assert result.match, (
            f"Visual regression on '{name}': {result.summary()} "
            f"(baseline={result.baseline_path}, diff={result.diff_path})"
        )
