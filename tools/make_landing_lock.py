"""Генератор docs/assets/lock.json: чем страницу наполняем и какими байтами."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"

ENTRIES = [
    ("fonts/manrope-latin-wght-normal.woff2", "@fontsource-variable/manrope", "5.3.0",
     "files/manrope-latin-wght-normal.woff2", "SIL OFL 1.1", "Manrope Variable 200-800, latin"),
    ("fonts/manrope-cyrillic-wght-normal.woff2", "@fontsource-variable/manrope", "5.3.0",
     "files/manrope-cyrillic-wght-normal.woff2", "SIL OFL 1.1", "Manrope Variable 200-800, cyrillic"),
    ("fonts/jetbrains-mono-latin-wght-normal.woff2", "@fontsource-variable/jetbrains-mono", "5.3.0",
     "files/jetbrains-mono-latin-wght-normal.woff2", "SIL OFL 1.1", "JetBrains Mono Variable 100-800, latin"),
    ("fonts/jetbrains-mono-cyrillic-wght-normal.woff2", "@fontsource-variable/jetbrains-mono", "5.3.0",
     "files/jetbrains-mono-cyrillic-wght-normal.woff2", "SIL OFL 1.1", "JetBrains Mono Variable 100-800, cyrillic"),
    ("vendor/gsap.min.js", "gsap", "3.12.5", "dist/gsap.min.js",
     "GreenSock standard license", "GSAP core; версия та же, что была на CDN до self-hosting"),
    ("vendor/ScrollTrigger.min.js", "gsap", "3.12.5", "dist/ScrollTrigger.min.js",
     "GreenSock standard license", "ScrollTrigger"),
    ("vendor/lenis.min.js", "lenis", "1.3.27", "dist/lenis.min.js", "MIT", "инерционный скролл"),
]

data = {"note": "docs/index.html отдаётся GitHub Pages как есть, без сборки: эти файлы и есть сборка.",
        "files": []}
for rel, pkg, ver, upstream, license_, purpose in ENTRIES:
    raw = (ASSETS / rel).read_bytes()
    data["files"].append({
        "path": rel,
        "package": pkg,
        "version": ver,
        "upstream_path": upstream,
        "license": license_,
        "purpose": purpose,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    })

(ASSETS / "lock.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote", ASSETS / "lock.json", sum(f["bytes"] for f in data["files"]), "bytes of assets")
