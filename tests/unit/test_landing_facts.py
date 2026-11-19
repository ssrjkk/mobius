"""Гейты достоверности витрины: напечатанные цифры обязаны совпадать с фактом.

Зачем: 947 на витрине прожило полтора месяца после того, как сватьй вырос, а
«99% покрытия экранных объектов» вообще не имело измеримого знаменателя —
меряется покрытие кода (98.58% по CI-команде), а не доля описанных экранов.
Оба числа теперь выводятся из прогона, а не из памяти: счётчик тестов берётся
живым collect-only ровно той командой, что в .github/workflows/ci.yml, поэтому
добавленный тест без обновления витрины валит этот гейт.

og:image проверяется побайтово по заголовку PNG: Pillow в test-extras нет, а
гейт должен работать и в CI, где его не ставят.
"""

from __future__ import annotations

import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "index.html"
OG = DOC.parent / "assets" / "og.png"
CANON = "https://ssrjkk.github.io/mobius/"


@pytest.fixture(scope="module")
def html() -> str:
    return DOC.read_text(encoding="utf-8")


def _ci_collected() -> int:
    """Сколько тестов реально исполнит CI: та же выборка, что в ci.yml."""
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit/", "tests/api/",
         "-m", "unit or api", "--collect-only", "-q", "--no-cov",
         "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=240,
    )
    assert proc.returncode == 0, f"collect-only упал:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}"
    ids = [ln for ln in proc.stdout.splitlines() if "::" in ln]
    if ids:
        return len(ids)
    total = 0
    for ln in proc.stdout.splitlines():
        m = re.match(r"^(tests/\S+\.py): (\d+)\s*$", ln.strip())
        if m:
            total += int(m.group(2))
    assert total > 0, f"не разобрал вывод collect-only:\n{proc.stdout[-1500:]}"
    return total


def _printed_counts(html: str) -> dict[str, int]:
    spots = {
        "title": re.search(r"<title>Mobius — (\d+) тестов\.", html),
        "description": re.search(r'<meta name="description" content="[^"]*?(\d+) тестов', html),
        "chip": re.search(r"<b>(\d+)</b>&nbsp;тестов", html),
        "h1": re.search(r'<span class="h1-line">(\d+) тестов\.</span>', html),
        "mnum": re.search(r'<div class="mnum">(\d+)</div>', html),
    }
    out = {}
    for name, m in spots.items():
        assert m, f"на витрине не нашлось места цифры: {name}"
        out[name] = int(m.group(1))
    lanes = re.findall(r"<span>(\d+)/(\d+)</span>", html)
    assert len(lanes) == 2, f"полос потоков должно быть две, найдено {len(lanes)}"
    for i, (a, b) in enumerate(lanes):
        assert a == b, f"поток {i}: числитель и знаменатель разошлись"
        out[f"lane{i}"] = int(a)
    return out


def test_printed_test_count_equals_ci_collection(html: str) -> None:
    collected = _ci_collected()
    printed = _printed_counts(html)
    bad = {k: v for k, v in printed.items() if v != collected}
    assert not bad, (
        f"витрина печатает {printed}, а CI-команда собирает {collected} тестов. "
        f"Расхождение: {bad}. Обнови цифры в docs/index.html (title, description, "
        f"chip, h1, полосы потоков, mnum) и FROZEN_* в test_landing_motion_layer.py."
    )


def test_readmes_print_the_same_ci_count() -> None:
    collected = _ci_collected()
    for name, pattern in (
        ("README.md", rf"\*\*{collected} tests\*\*"),
        ("README.ru.md", rf"\*\*{collected} тестов\*\*"),
    ):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert re.search(pattern, text), (
            f"{name} печатает не {collected} тестов — цифра разъехалась с CI-выборкой"
        )
        assert "947" not in text, f"{name} всё ещё несёт устаревшие 947"


def test_coverage_claim_is_code_and_labelled_as_code(html: str) -> None:
    assert "<b>99%</b>&nbsp;покрытия кода" in html, "chip покрытия потерял слово «кода»"
    assert '<div class="mlabel">покрытие кода тестами</div>' in html, (
        "подпись метрики снова обещает покрытие экранов — у него нет знаменателя"
    )
    assert "покрытия экранов" not in html and "покрытие экранных объектов" not in html


def test_sharing_metadata_is_complete_and_consistent(html: str) -> None:
    title = re.search(r"<title>([^<]+)</title>", html).group(1)
    need = {
        "canonical": f'<link rel="canonical" href="{CANON}">',
        "og:url": f'<meta property="og:url" content="{CANON}">',
        "og:title": f'<meta property="og:title" content="{title}">',
        "og:type": '<meta property="og:type" content="website">',
        "og:image": f'<meta property="og:image" content="{CANON}assets/og.png">',
        "og:image:width": '<meta property="og:image:width" content="1200">',
        "og:image:height": '<meta property="og:image:height" content="630">',
        "twitter:card": '<meta name="twitter:card" content="summary_large_image">',
        "twitter:image": f'<meta name="twitter:image" content="{CANON}assets/og.png">',
    }
    for name, tag in need.items():
        assert tag in html, f"нет тега шеринга {name}"
    og_desc = re.search(r'<meta property="og:description" content="([^"]+)"', html)
    assert og_desc and "Appium 2.x" in og_desc.group(1), "og:description пуст или без стека"
    assert re.search(r'<meta property="og:image:alt" content="[^"]{10,}"', html), (
        "og:image без alt — скриншот витрины должен быть описан"
    )


def test_og_image_is_a_real_1200x630_png() -> None:
    blob = OG.read_bytes()
    assert blob[:8] == b"\x89PNG\r\n\x1a\n", "og:image не PNG"
    assert blob[12:16] == b"IHDR", "у PNG нет IHDR первым чанком"
    w, h = struct.unpack(">II", blob[16:24])
    assert (w, h) == (1200, 630), f"og:image {w}x{h}, соцсети ждут 1200x630"
    assert len(blob) < 400_000, f"og:image разросся до {len(blob)} байт"