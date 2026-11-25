"""Statistical CLS gate for the Mobius landing; run with MOBIUS_LANDING_BROWSER=1."""

from __future__ import annotations

import contextlib
import http.server
import json
import os
import socketserver
import statistics
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "index.html"

RUNS = 5
THROUGHPUT_BPS = 65_536  # ~64 КБ/с: html за ~0.7 с, четыре woff2 за ~1.5 с
CLS_WORST_MAX = 0.05  # промер принятой страницы: 0.0334 (5/5 прогонов)
CLS_MEDIAN_MAX = 0.04

OBSERVER = """
window.__ls = [];
new PerformanceObserver(l => {
  for (const e of l.getEntries()) if (!e.hadRecentInput) window.__ls.push(e.value);
}).observe({type: 'layout-shift', buffered: true});
"""

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("MOBIUS_LANDING_BROWSER") != "1",
                       reason="браузерный гейт: MOBIUS_LANDING_BROWSER=1 и установленный Playwright"),
]


_HTTPD: socketserver.TCPServer | None = None
_URL: str | None = None


def _serve() -> str:
    """docs/ отдаётся локальным сервером: file:// не годится, там шрифты
    успевают до первой отрисовки и CLS всегда нулевой — гейт стал бы пустым."""
    global _HTTPD, _URL
    if _URL is not None:
        return _URL

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DOC.parent), **kw)

        def log_message(self, *a):  # тишина в выводе pytest
            pass

    _HTTPD = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=_HTTPD.serve_forever, daemon=True).start()
    _URL = f"http://127.0.0.1:{_HTTPD.server_address[1]}/index.html"
    return _URL


def _measure() -> list[float]:
    from playwright.sync_api import sync_playwright

    url = _serve()
    scores: list[float] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for _ in range(RUNS):
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(OBSERVER)
            page = ctx.new_page()
            cdp = ctx.new_cdp_session(page)
            cdp.send("Network.emulateNetworkConditions", {
                "offline": False, "latency": 0,
                "downloadThroughput": THROUGHPUT_BPS, "uploadThroughput": 16_384,
            })
            page.goto(url, wait_until="commit")
            with contextlib.suppress(Exception):
                page.wait_for_load_state("load", timeout=30_000)
            page.wait_for_timeout(6_000)
            shifts = page.evaluate("() => window.__ls")
            assert shifts is not None, "наблюдатель layout-shift не поставился — замер пустой"
            scores.append(round(sum(shifts), 6))
            ctx.close()
        browser.close()
    return scores


def test_cold_load_cls_stays_within_measured_band() -> None:
    """Ни один холодный прогон не должен вылезать за промеренную полосу."""
    scores = _measure()
    worst, med = max(scores), statistics.median(scores)
    assert worst <= CLS_WORST_MAX, (
        f"CLS {worst} выше {CLS_WORST_MAX}: страница при загрузке дёргается сильнее, "
        f"чем принято. Прогоны: {scores}. Прогоны 0.08 были у варианта с "
        f"size-adjust на фолбэке — см. докстринг."
    )
    assert med <= CLS_MEDIAN_MAX, f"медиана CLS {med} выше {CLS_MEDIAN_MAX}: прогоны {scores}"


def test_landing_is_not_blank_under_throttle() -> None:
    """
    Самый простой способ получить нулевой CLS — ничего не нарисовать. Проверяем,
    что за то же время страница действительно собралась: hero виден, высота
    документа совпадает с промеренной, шрифты приехали.
    """
    from playwright.sync_api import sync_playwright

    url = _serve()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.emulateNetworkConditions", {
            "offline": False, "latency": 0,
            "downloadThroughput": THROUGHPUT_BPS, "uploadThroughput": 16_384,
        })
        page.goto(url, wait_until="commit")
        with contextlib.suppress(Exception):
            page.wait_for_load_state("load", timeout=30_000)
        page.wait_for_timeout(6_000)
        state = json.loads(page.evaluate("""() => JSON.stringify({
            heroVisible: [...document.querySelectorAll('[data-hero]')]
              .every(e => +getComputedStyle(e).opacity > .9),
            heroCount: document.querySelectorAll('[data-hero]').length,
            scrollH: document.documentElement.scrollHeight,
            faces: [...document.fonts].filter(f => f.status === 'loaded').length,
            gsap: !!window.gsap && !!window.ScrollTrigger && !!window.Lenis,
        })"""))
        ctx.close()
        browser.close()

    assert state["heroCount"] == 6, f"в хиро {state['heroCount']} блоков data-hero, ожидалось 6"
    assert state["heroVisible"], "хиро остался невидимым через 6 с — страница «не дёргается», потому что пуста"
    assert state["gsap"], "движки не дошли до страницы под троттлингом"
    assert state["faces"] == 4, f"загружено начертаний {state['faces']}, ожидалось 4"
    assert state["scrollH"] == 4602, (
        f"высота документа {state['scrollH']} != 4602 — геометрия принятой витрины изменилась"
    )
