"""Браузерные гейты отказоустойчивости лендинга: отказ своего бандла и посадка якорей.

Появились после суровой проверки слоя движения, где нашли два реальных дефекта:

1. `new Lenis(...)` стоял без проверки. Бандл свой, в `docs/assets/vendor/`,
   но если он не приедет (404, кэш, блокировщик), присваивание бросало
   «Lenis is not defined» внутри IIFE — обрыв до каскада хиро, класс `.anim`
   не снят, и 129 текстовых элементов (включая h1) оставались с opacity:0:
   полностью пустой экран при коде, который должен был только украшать.
   GSAP и ScrollTrigger такой проверки не требовали — их отсутствие
   обрабатывалось веткой `if (!motion)`, промер это подтвердил (0 невидимых).
2. Якорь открывался как `lenis.scrollTo(element)`. Lenis для элемента считает
   цель как `rect.top + this.animatedScroll`, то есть складывает живую
   геометрию со своим внутренним положением. Если перед кликом браузер
   прыгнул мгновенно, слагаемые расходятся: промер давал посадку на 663 px
   ниже цели и, наоборот, полное игнорирование клика. 31 гонка «клавиатурный
   прыжок + клик по видимой ссылке» прошла чисто, поэтому достижимо это
   глазом вряд ли — но автопрокрутка перед кликом это штатное поведение
   браузера (фокус по Tab, переход по хэшу), и чинится одной строкой.

Гейт запускается только явно: нужен Playwright + Chromium.

    MOBIUS_LANDING_BROWSER=1 pytest -q -m browser tests/unit/test_landing_resilience.py

URL берётся из локальной раздачи docs/, но MOBIUS_LANDING_URL позволяет прогнать
его по живой странице — так проверяли, что гейт красный на версии до правки.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "index.html"

VENDOR = {
    "lenis": "**/lenis.min.js",
    "gsap": "**/gsap.min.js",
    "scrolltrigger": "**/ScrollTrigger.min.js",
    "весь vendor": "**/assets/vendor/**",
}

# Невидимым считается элемент, который виден геометрически, но погашен по
# прозрачности: ровно тот способ, каким слой движения прячет контент до анимации.
# [hidden]/display:none не считаем — это штатно скрытые панели демо.
INVISIBLE = """() => {
  const out = [];
  for (const el of document.querySelectorAll('a,button,p,h1,h2,h3,li,span,nav,footer,section,div')) {
    if (!el.textContent.trim()) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    let a = 1, n = el, skipped = false;
    while (n && n.nodeType === 1) {
      const s = getComputedStyle(n);
      if (s.display === 'none' || n.hasAttribute('hidden')) { skipped = true; break; }
      if (s.visibility === 'hidden') { a = 0; break; }
      a *= parseFloat(s.opacity || '1');
      n = n.parentElement;
    }
    if (skipped) continue;
    if (a < 0.05) out.push(el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0]);
  }
  return {count: out.length, sample: out.slice(0, 6)};
}"""

SETTLED = """() => ({
  scrollH: document.documentElement.scrollHeight,
  anim: document.documentElement.classList.contains('anim'),
  heroOpacity: +getComputedStyle(document.querySelector('h1')).opacity,
})"""

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.environ.get("MOBIUS_LANDING_BROWSER") != "1",
                       reason="браузерный гейт: MOBIUS_LANDING_BROWSER=1 и установленный Playwright"),
]

_HTTPD: socketserver.TCPServer | None = None
_LOCAL: str | None = None


def _url() -> str:
    override = os.environ.get("MOBIUS_LANDING_URL")
    if override:
        return override
    global _HTTPD, _LOCAL
    if _LOCAL is not None:
        return _LOCAL

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DOC.parent), **kw)

        def log_message(self, *a):
            pass

    _HTTPD = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=_HTTPD.serve_forever, daemon=True).start()
    _LOCAL = f"http://127.0.0.1:{_HTTPD.server_address[1]}/index.html"
    return _LOCAL


def _scroll_through(page) -> None:
    """Прокрутить до конца шажками, чтобы ревилы с once:true сработали."""
    height = page.evaluate("() => document.documentElement.scrollHeight")
    for y in range(0, height + 900, 700):
        page.evaluate(f"() => window.scrollTo(0, {y})")
        page.wait_for_timeout(160)
    page.wait_for_timeout(900)


@pytest.mark.parametrize("name", list(VENDOR))
def test_page_is_readable_without_a_vendor_bundle(name: str) -> None:
    """Без любого из своих бандлов страница обязана остаться читаемой."""
    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route(VENDOR[name], lambda route: route.abort())
        page.goto(_url(), wait_until="load")
        page.wait_for_timeout(3_000)
        _scroll_through(page)
        state = page.evaluate(SETTLED)
        hidden = page.evaluate(INVISIBLE)
        ctx.close()
        browser.close()

    fatal = [e for e in errors if "is not defined" in e]
    assert not fatal, f"{name}: отказ бандла уронил инициализацию — {fatal[0]}"
    assert state["heroOpacity"] > 0.9, (
        f"{name}: h1 с opacity {state['heroOpacity']} — без этого бандла хиро не виден"
    )
    assert hidden["count"] == 0, (
        f"{name}: {hidden['count']} элементов остались погашенными, примеры {hidden['sample']}. "
        f"Класс .anim снят: {not state['anim']}"
    )
    assert state["scrollH"] == 4100, (
        f"{name}: высота документа {state['scrollH']} != 4100 — без бандла геометрия поехала"
    )


def test_anchor_clicks_land_on_the_native_position() -> None:
    """Клик по каждой якорной ссылке с двух концов страницы.

    Нижняя точка старта обязательна: ссылка хиро тогда не в зоне видимости, и
    браузер сам мгновенно прокручивает к ней перед кликом — это тот самый
    мгновенный прыжок, на котором Lenis складывал живую rect.top со своим
    отстающим animatedScroll. Без неё гейт проверяет только тривиальный случай.
    """
    from playwright.sync_api import sync_playwright

    rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(_url(), wait_until="load")
        page.wait_for_timeout(3_000)
        links = page.evaluate("""() => [...document.querySelectorAll('a[href^="#"]')]
            .map((a, i) => ({i, href: a.getAttribute('href'), cls: a.className}))
            .filter(x => x.href.length > 1 && !x.cls.includes('skip'))""")
        assert links, "на странице не нашлось ни одной якорной ссылки — гейт пустой"
        for start in ("top", "bottom"):
            for link in links:
                if start == "top":
                    page.evaluate("() => window.scrollTo(0, 0)")
                else:
                    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(1_800)
                want = page.evaluate(
                    """(frag) => {const t = document.getElementById(frag); const r = t.getBoundingClientRect();
                       return Math.round(r.top + window.scrollY - parseFloat(getComputedStyle(t).scrollMarginTop));}""",
                    link["href"][1:],
                )
                page.locator('a[href^="#"]').nth(link["i"]).click()
                page.wait_for_timeout(2_600)
                got = page.evaluate("() => Math.round(window.scrollY)")
                rows.append({"start": start, "href": link["href"], "i": link["i"],
                             "want": want, "got": got, "err": got - want})
        ctx.close()
        browser.close()

    bad = [r for r in rows if abs(r["err"]) > 3]
    assert not bad, (
        f"якоря сажают не туда: {bad}. Ожидалась штатная позиция с учётом "
        f"scroll-margin-top; прогоняли {len(rows)} кликов."
    )


def test_demo_tab_lights_first_row_in_the_same_frame() -> None:
    """Клик по табу обязан зажигать первую строку сразу, а не через lead.

    Промер до правки: через 120 мс после переключения платформы горело 0 из 4
    строк — панель выглядела мёртвой ровно в момент клика. Первая строка теперь
    стоит на нулевой позиции таймлайна, каденс остальных сохранён.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(_url(), wait_until="load")
        page.wait_for_timeout(2_500)
        page.locator("#demo").scroll_into_view_if_needed()
        page.wait_for_timeout(1_200)
        page.locator('.tab[data-platform="ios"]').click()
        page.wait_for_timeout(100)
        early = page.evaluate(
            "() => document.querySelectorAll('#pane-ios .gstep.lit').length"
        )
        page.wait_for_timeout(1_500)
        settled = page.evaluate(
            """() => ({lit: document.querySelectorAll('#pane-ios .gstep.lit').length,
                       total: document.querySelectorAll('#pane-ios .gstep').length,
                       transforms: [...document.querySelectorAll('#pane-ios .gstep')]
                         .filter(s => getComputedStyle(s).transform !== 'none').length})"""
        )
        ctx.close()
        browser.close()

    assert early >= 1, (
        f"через 100 мс после клика по табу горит {early} строк — панель отвечает "
        f"с задержкой, как до правки (0 из 4 на 120 мс)"
    )
    assert settled["lit"] == settled["total"] == 4, f"демо не догорело: {settled}"
    assert settled["transforms"] == 0, f"на строках остались transform: {settled}"
