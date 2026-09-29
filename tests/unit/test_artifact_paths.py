"""
Безопасность и корректность записи артефактов: artifact_path (нейтрализация
path traversal в name/filename у ScreenshotUtils / ScreenRecorder /
VisualRegression), защита Pillow от decompression bomb и точная формула
_pixel_diff. Файловые проверки — реальные записи на диск в tmp_path;
мокируются только I/O-границы (driver).
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from mobius.utils.screen_recording import ScreenRecorder
from mobius.utils.screenshot import ScreenshotUtils, artifact_path
from mobius.utils.visual_regression import VisualRegression

pytestmark = pytest.mark.unit

_TRAVERSAL_NAMES = ["../../escape", "..\\..\\escape", "a/../../b", "..", "../.."]


def _fs_snapshot(root: Path) -> set[Path]:
    """Все файлы/каталоги под root — для проверки 'ничего не появилось наружу'."""
    return {p.resolve() for p in root.rglob("*") if p.is_file()}


def _png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _writing_driver() -> MagicMock:
    """Драйвер, у которого save_screenshot реально пишет файл по переданному пути."""
    d = MagicMock()
    d.save_screenshot.side_effect = lambda p: Path(p).write_bytes(b"PNG")
    return d


def _dir_link(link: Path, target: Path) -> None:
    """Настоящая директория-ссылка (junction на Windows, symlink на POSIX)."""
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        os.symlink(target, link, target_is_directory=True)


def _vr(tmp_path: Path, img: Image.Image | None = None) -> VisualRegression:
    d = MagicMock()
    d.get_screenshot_as_base64.return_value = _png_b64(img or Image.new("RGB", (10, 10), (5, 5, 5)))
    return VisualRegression(d, baseline_dir=str(tmp_path / "b"), diff_dir=str(tmp_path / "d"))


# ── artifact_path: правила санитайзинга ─────────────────────────────────────


class TestArtifactPathRules:
    def test_rejects_dotdot_segments(self, tmp_path):
        for name in _TRAVERSAL_NAMES:
            with pytest.raises(ValueError, match=r"\.\."):
                artifact_path(tmp_path, name, ".png")

    def test_neutralizes_embedded_separators(self, tmp_path):
        path = artifact_path(tmp_path, "catalog/item 5", ".png")
        assert path.parent == tmp_path.resolve()
        assert path.name == "catalog_item 5.png"

    def test_neutralizes_drive_letter_and_unc(self, tmp_path):
        path = artifact_path(tmp_path, r"C:\Windows\evil.exe", ".png")
        assert path.parent == tmp_path.resolve()
        assert ":" not in path.name and "\\" not in path.name
        unc = artifact_path(tmp_path, "\\\\server\\share\\x", ".png")
        assert unc.parent == tmp_path.resolve()

    def test_ordinary_names_unchanged(self, tmp_path):
        assert artifact_path(tmp_path, "login_screen", ".png").name == "login_screen.png"

    def test_leading_dot_segment_neutralized(self, tmp_path):
        path = artifact_path(tmp_path, ".hidden", ".png")
        assert path.parent == tmp_path.resolve()
        assert not path.name.startswith(".")

    def test_rejects_name_empty_after_sanitization(self, tmp_path):
        for name in ["", "   "]:
            with pytest.raises(ValueError, match="empty after sanitization"):
                artifact_path(tmp_path, name, ".png")


# ── ScreenshotUtils.take ─────────────────────────────────────────────────────


class TestScreenshotTraversal:
    def test_take_traversal_raises_and_nothing_written_outside(self, tmp_path):
        shots = tmp_path / "shots"
        ss = ScreenshotUtils(_writing_driver(), str(shots))
        before = _fs_snapshot(tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            ss.take("../../escape")
        assert _fs_snapshot(tmp_path) == before

    def test_take_sanitizes_separators_into_usable_file(self, tmp_path):
        shots = tmp_path / "shots"
        ss = ScreenshotUtils(_writing_driver(), str(shots))
        path = ss.take("catalog/item 5")
        assert path.parent == shots.resolve()
        assert path.name.startswith("catalog_item 5_") and path.name.endswith(".png")
        assert path.exists()

    def test_take_ordinary_and_default_names(self, tmp_path):
        shots = tmp_path / "shots"
        ss = ScreenshotUtils(_writing_driver(), str(shots))
        named = ss.take("login_screen")
        default = ss.take()
        assert named.exists()
        assert default.name.startswith("screenshot_")
        assert named.parent == shots.resolve() == default.parent


# ── ScreenRecorder.stop_and_save ─────────────────────────────────────────────


class TestRecorderTraversal:
    def _recorder(self, tmp_path: Path, out: str = "recs") -> tuple[ScreenRecorder, MagicMock]:
        d = MagicMock()
        d.stop_recording_screen.return_value = base64.b64encode(b"fake-mp4").decode()
        rec = ScreenRecorder(d, output_dir=str(tmp_path / out))
        assert rec.start()
        return rec, d

    def test_traversal_raises_and_nothing_written_outside(self, tmp_path):
        rec, _d = self._recorder(tmp_path)
        before = _fs_snapshot(tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            rec.stop_and_save("../../escape")
        assert _fs_snapshot(tmp_path) == before
        assert list((tmp_path / "recs").iterdir()) == []

    def test_ordinary_name_writes_inside_base(self, tmp_path):
        rec, _d = self._recorder(tmp_path)
        path = rec.stop_and_save("checkout flow")
        assert path is not None
        written = Path(path)
        assert written.parent == (tmp_path / "recs").resolve()
        assert written.read_bytes() == b"fake-mp4"

    def test_symlink_inside_base_dir_is_rejected(self, tmp_path):
        """Файл-ловушка ВНУТРИ base_dir — containment-check обязан дать ValueError."""
        rec, _d = self._recorder(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        _dir_link(tmp_path / "recs" / "trap.mp4", outside / "stolen.mp4")
        with pytest.raises(ValueError, match="escapes base dir"):
            rec.stop_and_save("trap")
        assert list(outside.iterdir()) == []


# ── VisualRegression: traversal на baseline-чтении и report-записи ───────────


class TestVisualRegressionTraversal:
    def test_compare_traversal_raises_and_nothing_written(self, tmp_path):
        vr = _vr(tmp_path)
        before = _fs_snapshot(tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            vr.compare("../../escape")
        assert _fs_snapshot(tmp_path) == before

    def test_update_baseline_traversal_raises(self, tmp_path):
        vr = _vr(tmp_path)
        before = _fs_snapshot(tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            vr.update_baseline("../..//escape")
        assert _fs_snapshot(tmp_path) == before

    def test_compare_separators_produce_usable_files(self, tmp_path):
        vr = _vr(tmp_path)
        result = vr.compare("catalog/item 5")
        baseline = tmp_path / "b" / "catalog_item 5.png"
        assert result.reason == "baseline created (first run)"
        assert baseline.resolve() == Path(result.baseline_path)
        assert baseline.exists()
        assert (tmp_path / "d" / "catalog_item 5_actual.png").exists()

    def test_baseline_name_from_device_cannot_climb_out(self, tmp_path):
        vr = _vr(tmp_path)
        vr.compare("login_screen")
        before = _fs_snapshot(tmp_path)
        with pytest.raises(ValueError, match=r"\.\."):
            vr.compare("../evil")
        assert _fs_snapshot(tmp_path) == before


# ── Pillow: decompression bomb и корректное закрытие handle ──────────────────


class TestPillowHardening:
    def test_decompression_bomb_baseline_raises_valueerror(self, tmp_path, monkeypatch):
        # Бюджет пикселей Pillow (Image.MAX_IMAGE_PIXELS) остаётся default-ом
        # продукта; в тесте ВРЕМЕННО задираем его вниз (monkeypatch вернёт),
        # чтобы 50x50 baseline считался бомбой — сценарий «baseline с устройства».
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
        vr = _vr(tmp_path, Image.new("RGB", (2, 2), (1, 2, 3)))
        big = Image.new("RGB", (50, 50), (9, 9, 9))
        big.save(tmp_path / "b" / "screen.png")
        with pytest.raises(ValueError, match="pixel budget"):
            vr.compare("screen")

    def test_bomb_image_handle_is_closed(self, tmp_path, monkeypatch):
        """Утечка fp на битом/огромном PNG проявилась бы нестираемым файлом."""
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
        vr = _vr(tmp_path, Image.new("RGB", (2, 2), (1, 2, 3)))
        big = Image.new("RGB", (50, 50), (9, 9, 9))
        baseline = tmp_path / "b" / "screen.png"
        big.save(baseline)
        with pytest.raises(ValueError, match="pixel budget"):
            vr.compare("screen")
        baseline.unlink()  # на Windows упало бы с PermissionError при живом handle

    def test_small_baseline_still_opens_with_default_budget(self, tmp_path):
        """MAX_IMAGE_PIXELS не понижен и не повышен нашим модулем."""
        vr = _vr(tmp_path)
        result = vr.compare("screen")
        assert result.match is True  # первый прогон создал baseline


# ── _pixel_diff: точная формула ──────────────────────────────────────────────


class TestPixelDiffFormula:
    def test_blue_only_change_is_counted_exactly(self, tmp_path):
        """
        ПинRegression: RGB-пиксель (0,0,0) -> (0,0,86). Старый sum(L-histogram[10:])
        давал 0.0 (L=9 от 86*0.114 — ниже порога), честный максимум по каналам
        даёт ровно 1 из 2 пикселей = 50.0.
        """
        vr = _vr(tmp_path)
        baseline = Image.new("RGB", (2, 1), (0, 0, 0))
        current = Image.new("RGB", (2, 1), (0, 0, 0))
        current.putpixel((0, 0), (0, 0, 86))
        pct, diff = vr._pixel_diff(baseline, current)
        assert pct == 50.0
        assert diff.mode == "RGB"

    def test_per_channel_max_not_luma_projection(self, tmp_path):
        """Пиксель меняется, если ХОТЬ ОДИН канал сдвинул >= 10 (без L-веса 0.114)."""
        vr = _vr(tmp_path)
        baseline = Image.new("RGB", (2, 1), (0, 0, 80))
        current = Image.new("RGB", (2, 1), (0, 0, 80))
        current.putpixel((0, 0), (80, 0, 0))
        pct, _diff = vr._pixel_diff(baseline, current)
        assert pct == 50.0  # пиксель 0: |80| по R и B; пиксель 1 идентичен

    def test_noise_floor_boundary(self, tmp_path):
        vr = _vr(tmp_path)
        below = vr._pixel_diff(Image.new("L", (1, 1), 0), Image.new("L", (1, 1), 9))[0]
        at_floor = vr._pixel_diff(Image.new("L", (1, 1), 0), Image.new("L", (1, 1), 10))[0]
        assert below == 0.0
        assert at_floor == 100.0

    def test_identical_images_zero(self, tmp_path):
        vr = _vr(tmp_path)
        a = Image.new("RGB", (4, 4), (7, 7, 7))
        assert vr._pixel_diff(a, a.copy())[0] == 0.0

    def test_rgba_alpha_channel_change_counted(self, tmp_path):
        vr = _vr(tmp_path)
        baseline = Image.new("RGBA", (2, 1), (0, 0, 0, 255))
        current = Image.new("RGBA", (2, 1), (0, 0, 0, 255))
        current.putpixel((0, 0), (0, 0, 0, 0))
        pct, diff = vr._pixel_diff(baseline, current)
        assert pct == 50.0
        assert diff.mode == "RGBA"

    def test_mixed_modes_without_alpha_converge_to_rgb(self, tmp_path):
        vr = _vr(tmp_path)
        baseline = Image.new("L", (2, 1), 0)
        current = Image.new("RGB", (2, 1), (0, 0, 0))
        current.putpixel((0, 0), (200, 0, 0))
        pct, diff = vr._pixel_diff(baseline, current)
        assert pct == 50.0
        assert diff.mode == "RGB"

    def test_mixed_modes_with_alpha_converge_to_rgba(self, tmp_path):
        vr = _vr(tmp_path)
        baseline = Image.new("RGB", (2, 1), (0, 0, 0))
        current = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
        current.putpixel((0, 0), (0, 0, 0, 255))
        pct, diff = vr._pixel_diff(baseline, current)
        assert pct == 50.0
        assert diff.mode == "RGBA"

    def test_half_changed_image_is_exactly_50_percent(self, tmp_path):
        vr = _vr(tmp_path)
        baseline = Image.new("RGB", (50, 50), (0, 0, 0))
        current = baseline.copy()
        for x in range(25, 50):
            for y in range(50):
                current.putpixel((x, y), (255, 255, 255))
        assert vr._pixel_diff(baseline, current)[0] == 50.0
