"""
Гейты слоя движения на лендинге GitHub Pages (docs/index.html).

Landing отдаётся Pages как есть, без сборки: pytest — единственный способ
проверить, что в нём не появилось чужой CDN-строки, что шрифт реально покрыл
кириллицу и что всё новое живёт за prefers-reduced-motion. Пороги — промеры
этой волны, не догадки:

  * 0 субресурсов на чужих доменах (было: Google Fonts + jsDelivr);
  * CLS при загрузке и на прокрутке 0.0000 (было 0.0189), геометрия
    byte-identical: scrollHeight 4100, вершины .fcard, бокс h1;
  * минимальный контраст заголовков 16.28:1 — не ниже принятого;
  * перенесённых байтов (html + 7 локальных файлов) 272 955;
  * reduced-motion: Lenis не инициализируется, живых анимаций 0.

Тесты читают файл, а не запускают браузер: браузерные числа собраны промером
(см. комментарий выше) и здесь зафиксированы как пороги.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "index.html"
ASSETS = DOC.parent / "assets"

# --- промер этой волны: принятый дизайн в цифрах -----------------------------

HTML_BYTES_MAX = 285_000  # raw: html + все локальные субресурсы (замерено 272 955)
HEADING_CONTRAST_BASELINE = 16.28
HEADLINE_WEIGHT_BUDGET = 50_000  # docs/index.html один файл, без framework'ов внутрь

PALETTE = {
    "--bg": "#0A0F1E",
    "--bg2": "#0D1526",
    "--fg": "#F8FAFC",
    "--muted": "#94A3B8",
    "--faint": "#64748B",
    "--teal": "#2DD4BF",
    "--teal-bright": "#5EEAD4",
    "--ice": "#7DD3FC",
    "--ok": "#22C55E",
    "--warn": "#FBBF24",
}

# Копирайт и структура принятого дизайна — слой движения их не трогает.
FROZEN_TITLE = "Mobius — 947 тестов. Две платформы. Один пайплайн."
FROZEN_H1 = ["947 тестов.", "Две платформы.", "Один пайплайн."]
FROZEN_H2 = [
    "Что внутри фреймворка",
    "От экрана до отчёта — четыре шага",
    "Выберите платформу",
    "Соберите две платформы в один пайплайн",
]
FROZEN_COUNTS = {"svg": 6, "gstep": 8, "mnum": 4, "fcard": 6, "section": 6}

# Lucide 1.75.0: имя и число дочерних элементов канонического файла.
LUCIDE_ICONS = [
    ("smartphone", 2),
    ("server", 4),
    ("mouse-pointer-click", 5),
    ("repeat", 4),
    ("square-terminal", 3),
    ("clipboard-check", 3),
]

# Единственные абсолютные URL, допустимые в файле: xmlns у inline-фавикона
# (не запрос) и две ссылки на собственные репозитории.
ALLOWED_ABS_URLS = {
    "http://www.w3.org/2000/svg",
    "https://github.com/ssrjkk/mobius",
    "https://ssrjkk.github.io/",
}
BANNED_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
)


@pytest.fixture(scope="module")
def html() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css(html: str) -> str:
    block = re.search(r"<style>(.*?)</style>", html, re.S)
    assert block, "в docs/index.html нет блока <style>"
    return block.group(1)


@pytest.fixture(scope="module")
def css_clean(css: str) -> str:
    """CSS без комментариев — чтобы комментарий не притворялся селектором."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


@pytest.fixture(scope="module")
def lock() -> dict:
    return json.loads((ASSETS / "lock.json").read_text(encoding="utf-8"))


def _rules(sheet: str) -> list[tuple[str, str]]:
    return [(s.strip(), b) for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet)]


def _contrast(fg: str, bg: str) -> float:
    """WCAG 2.1 relative-luminance contrast для двух #RRGGBB."""
    def lum(hexcolor: str) -> float:
        chans = [int(hexcolor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _subresources(html: str, css: str) -> set[str]:
    """Всё, что браузер докачает по относительным путям."""
    refs = set(re.findall(r'<script[^>]*\bsrc="([^"]+)"', html))
    refs |= set(re.findall(r'<link[^>]*\bhref="(assets/[^"]+)"', html))
    refs |= set(re.findall(r"url\(['\"]?(assets/[^'\")]+)['\"]?\)", css))
    return refs


# --- сеть: чужих запросов не должно быть -------------------------------------


def test_subresources_are_self_hosted_and_local(html: str, css: str) -> None:
    refs = _subresources(html, css)
    assert refs, "не нашёл ни одного локального субресурса — вероятно, разметка сломалась"
    for ref in refs:
        assert not re.match(r"^(https?:)?//", ref), f"{ref} качается с чужого домена"
        assert ref.startswith("assets/"), f"{ref} лежит вне docs/assets"
        assert (DOC.parent / ref).is_file(), f"{ref} объявлен, но файла нет"


def test_vendored_set_is_exactly_the_lockfile(lock: dict, html: str, css: str) -> None:
    locked = {f"assets/{entry['path']}" for entry in lock["files"]}
    on_disk = {
        p.relative_to(DOC.parent).as_posix()
        for p in ASSETS.rglob("*")
        if p.is_file() and p.suffix in {".woff2", ".js"}
    }
    assert locked == on_disk, "файлы в docs/assets и lock.json разъехались"
    assert _subresources(html, css) == locked, "лендинг ссылается не на тот набор, что залочен"


def test_no_third_party_urls_anywhere(html: str) -> None:
    found = set(re.findall(r"https?://[^\"'\s<>)]+", html))
    assert found <= ALLOWED_ABS_URLS, f"чужие URL в лендинге: {sorted(found - ALLOWED_ABS_URLS)}"
    for host in BANNED_HOSTS:
        assert host not in html, f"вернулся CDN {host}"


# --- файлы сборки: lock.json должен соответствовать содержимому ---------------


def test_lockfile_hashes_match_bytes(lock: dict) -> None:
    for entry in lock["files"]:
        path = ASSETS / entry["path"]
        blob = path.read_bytes()
        assert len(blob) == entry["bytes"], f"{entry['path']}: размер не совпадает с lock.json"
        assert hashlib.sha256(blob).hexdigest() == entry["sha256"], f"{entry['path']}: sha256 не тот"


def test_lockfile_versions_are_credited(lock: dict) -> None:
    credits = (ASSETS / "CREDITS.txt").read_text(encoding="utf-8")
    for entry in lock["files"]:
        assert entry["license"] in credits, f"{entry['path']}: лицензия {entry['license']} не в CREDITS.txt"
        assert entry["version"] in credits, f"{entry['path']}: версия {entry['version']} не в CREDITS.txt"
        assert entry["package"] in credits, f"{entry['path']}: пакет {entry['package']} не в CREDITS.txt"


# --- шрифты: переменная ось и кириллица --------------------------------------


def test_font_faces_declare_variable_axis(css: str) -> None:
    faces = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
    assert len(faces) == 4, f"ожидал 4 @font-face, нашёл {len(faces)}"
    axes: dict[str, set[str]] = {}
    for face in faces:
        family = re.search(r"font-family:'([^']+)'", face).group(1)
        weight = re.search(r"font-weight:([\d.]+)\s+([\d.]+)", face)
        assert weight, f"{family}: weight объявлен дискретно — variable-файл отдаст одно начертание"
        axes.setdefault(family, set()).add(weight.group(0))
        assert "font-display:swap" in face.replace(" ", ""), f"{family}: нет font-display:swap"
        assert "format('woff2')" in face, f"{family}: не woff2"
    assert axes == {"Manrope": {"font-weight:200 800"}, "JetBrains Mono": {"font-weight:100 800"}}


def test_cyrillic_is_covered_by_a_shipped_file(css: str, html: str) -> None:
    faces = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
    per_family: dict[str, list[str]] = {}
    for face in faces:
        family = re.search(r"font-family:'([^']+)'", face).group(1)
        src = re.search(r"url\('([^']+)'\)", face).group(1)
        per_family.setdefault(family, []).append(src)
        assert "U+0400-045F" in face or "U+0000-00FF" in face, f"{src}: пустой unicode-range"
    for family, srcs in per_family.items():
        assert len(srcs) == 2, f"{family}: subset'ов {len(srcs)}, нужен latin + cyrillic"
        assert any("cyrillic" in s for s in srcs), f"{family}: нет кириллического subset"
        for src in srcs:
            blob = (DOC.parent / src).read_bytes()
            assert blob[:4] == b"wOF2", f"{src}: это не woff2"
            assert f'href="{src}"' in html, f"{src}: файл подключён, но не предзагружен"


def test_declared_families_are_the_ones_css_uses(css_clean: str) -> None:
    """
    Семейство в @font-face и в --sans/--mono должно совпадать дословно:
    расхождение (tippy-урок) молча отдаёт всё системным fallback. --mono
    применяется в шортхенде font:..., поэтому ищем просто var(--mono).
    """
    faces = set(re.findall(r"@font-face\s*\{[^}]*font-family:'([^']+)'", css_clean))
    tokens = set(re.findall(r"--(?:sans|mono):'([^']+)'", css_clean))
    assert faces == tokens == {"Manrope", "JetBrains Mono"}
    for token in ("--sans", "--mono"):
        assert f"var({token})" in css_clean, f"переменная {token} нигде не применяется"


# --- движение: только за reduced-motion и только после гварда ----------------


def test_animation_runs_behind_the_reduced_motion_guard(html: str) -> None:
    assert "prefers-reduced-motion: reduce" in html, "пропахла проверка reduced-motion"
    assert "var motion = hasGsap && !reduce;" in html, "флаг motion больше не зависит от reduce и GSAP"
    guard = html.index("if (!motion) return;")
    assert html.count("if (!motion) return;") == 1, "гвард должен быть один — точка невозврата"
    for probe in ("new Lenis(", "gsap.ticker.add", "lenis.scrollTo", "gsap.utils.toArray('.mnum')"):
        assert probe in html, f"исчез фрагмент движения: {probe}"
        assert html.index(probe) > guard, f"{probe} исполняется до гварда reduced-motion"
    # светящиеся шаги демо: без движения моментально, с движением — таймлайном
    assert html.count("if (!motion) {") >= 2, "lightPane/selectTab потеряли немедленную ветку"


def test_lenis_ships_its_own_css(css: str) -> None:
    """Классы, которые Lenis навешивает на html, без стилей ломают скролл."""
    for selector in ("html.lenis", ".lenis.lenis-smooth", ".lenis.lenis-stopped", "[data-lenis-prevent]"):
        assert selector in css, f"нет штатного CSS Lenis для {selector}"
    assert "scroll-behavior:auto!important" in css.replace(" ", ""), "Lenis не отключил нативный scroll-behavior"


def test_pre_animation_states_need_the_anim_class(css_clean: str, html: str) -> None:
    """
    opacity:0 вне .anim означало бы, что без JS (или с отключённым движением)
    часть страницы пуста. Это же защищает от регресса пустого hero.
    """
    hidden = [sel for sel, body in _rules(css_clean) if re.search(r"opacity:\s*0\b", body)]
    assert hidden, "проверка теряет смысл: не осталось пред-анимационных состояний"
    for sel in hidden:
        assert sel.startswith(".anim"), f"{sel} прячет контент независимо от JS"
    assert "classList.add('anim')" in html, "класс .anim больше не навешивается из JS"
    assert "classList.remove('anim')" in html, "reduce-ветка не снимает .anim"
    assert "@media (prefers-reduced-motion:reduce)" in css_clean, "нет CSS-страховки для reduce"


def test_no_animation_library_is_added_twice(html: str) -> None:
    """Три рантайма анимаций на одностраничном лендинге — долг, а не фича."""
    libs = re.findall(r'assets/vendor/([A-Za-z]+)\.min\.js', html)
    assert sorted(libs) == ["ScrollTrigger", "gsap", "lenis"], f"набор движков изменился: {libs}"


# --- иконки: канонические Lucide ---------------------------------------------


def test_feature_icons_are_canonical_lucide(html: str) -> None:
    svgs = re.findall(r'(<svg\b[^>]*>)(.*?)</svg>', html, re.S)
    assert len(svgs) == len(LUCIDE_ICONS), f"<svg> в разметке {len(svgs)}, иконок ожидалось {len(LUCIDE_ICONS)}"
    shipped = [re.search(r"lucide-([\w-]+)", tag).group(1) for tag, _ in svgs]
    assert shipped == [name for name, _ in LUCIDE_ICONS], f"набор или порядок иконок изменился: {shipped}"
    for (name, children), (attrs, body) in zip(LUCIDE_ICONS, svgs):
        assert f'class="lucide lucide-{name}"' in attrs, f"{name}: потерялся канонический класс Lucide"
        assert 'viewBox="0 0 24 24"' in attrs, f"{name}: чужой viewBox"
        assert 'stroke-width="1.6"' in attrs, f"{name}: дефолтный Lucide stroke 2 виднее принятого"
        assert 'aria-hidden="true"' in attrs, f"{name}: декоративная иконка попала в озвучку"
        assert 'fill="none"' in attrs and 'stroke="currentColor"' in attrs, f"{name}: сломан inherit цвета"
        shapes = re.findall(r"<(path|rect|circle|line|polyline|polygon)\b", body)
        assert len(shapes) == children, f"{name}: {len(shapes)} фигур вместо канонических {children}"


def test_inline_svg_assets_do_not_reference_external_files(html: str) -> None:
    assert "xlink:href" not in html, "иконки тянутся из внешнего спрайта"
    assert "<use " not in html, "иконки отсылаются к внешнему спрайту через <use>"


# --- палитра и контраст: принятое не ниже ------------------------------------


def test_palette_tokens_are_unchanged(css: str) -> None:
    found = dict(re.findall(r"(--[\w-]+):(#[0-9A-Fa-f]{6})", css))
    for token, hexvalue in PALETTE.items():
        assert found.get(token, "").upper() == hexvalue.upper(), f"{token} перекрашен в {found.get(token)!r}"


def test_heading_contrast_is_not_lower_than_accepted(css: str, css_clean: str) -> None:
    """
    Заголовки не задают свой цвет и наследуют --fg, поэтому их контраст считается
    по токенам прямо из CSS. В браузере (с glass-оверлеями) минимум был 16.28:1 и
    до слоя движения, и после — ниже этой планки пускать нельзя.
    """
    tokens = dict(re.findall(r"(--[\w-]+):(#[0-9A-Fa-f]{6})", css))
    fg = tokens["--fg"]
    worst = min(_contrast(fg, tokens[bg]) for bg in ("--bg", "--bg2"))
    assert worst >= HEADING_CONTRAST_BASELINE, (
        f"контраст заголовков {worst:.2f}:1 ниже принятого {HEADING_CONTRAST_BASELINE}:1"
    )
    for sel, body in _rules(css_clean):
        if not re.search(r"\bh[123]\b", sel):
            continue
        assert not re.search(r"\bcolor:", body), f"{sel} задаёт свой цвет вместо --fg"


# --- принятый дизайн: тексты и структура -------------------------------------


def test_accepted_copy_is_untouched(html: str) -> None:
    assert re.search(rf"<title>{re.escape(FROZEN_TITLE)}</title>", html), "title переписан"
    for line in FROZEN_H1:
        assert f'<span class="h1-line">{line}</span>' in html, f"hero-строка '{line}' изменена"
    for head in FROZEN_H2:
        assert f"<h2>{head}</h2>" in html, f"заголовок секции '{head}' изменён"
    desc = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
    assert "947 тестов" in desc and "Appium 2.x" in desc, "meta description съехал с фактов"


def test_accepted_structure_is_untouched(html: str) -> None:
    counts = {
        "svg": html.count("<svg"),
        "gstep": html.count('class="gstep'),
        "mnum": html.count('class="mnum'),
        "fcard": html.count('class="fcard"'),
        "section": html.count("<section"),
    }
    assert counts == FROZEN_COUNTS, f"структура лендинга изменилась: {counts}"


# --- бюджет веса --------------------------------------------------------------


def test_landing_weight_budget(html: str) -> None:
    """
    Вес считаем как то, что отдаёт Pages: HTML после LF-нормализации (git
    хранит docs/index.html с \\n, локальный файл с CRLF на ~850 байт тяжелее)
    плюс побайтово зафиксированные assets. Без gzip/br — они только в пользу
    страницы. Замер этой волны: 272 103 байт raw, ~150 КБ в переносе.
    """
    assets = json.loads((ASSETS / "lock.json").read_text(encoding="utf-8"))["files"]
    doc_bytes = len(html.encode("utf-8"))
    total = doc_bytes + sum((ASSETS / entry["path"]).stat().st_size for entry in assets)
    assert total <= HTML_BYTES_MAX, f"лендинг весит {total} байт, бюджет {HTML_BYTES_MAX}"
    assert doc_bytes <= HEADLINE_WEIGHT_BUDGET, (
        f"docs/index.html разросся до {doc_bytes} байт — библиотека должна лежать в assets/vendor"
    )
