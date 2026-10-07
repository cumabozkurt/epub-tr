#!/usr/bin/env python3
"""Build docs/images/banner.svg (and the 1280x640 social preview) from docs/images/banner.src.svg.

Every <text> is turned into outlined <path>s, so the banner looks the same everywhere: GitHub shows
README SVGs as images, which cannot load web fonts, and fallback fonts change widths.

    pip install fonttools && python scripts/outline_banner.py [--png]

Each <text> in the source needs x, y, font-size and data-font (one of FONTS below), and may have
letter-spacing, fill and data-max-width (the size shrinks until the text fits). A <g data-chips="x,y,h,gap">
holding <text data-font=…> children becomes a row of outlined pills. With --png, Google Chrome (headless)
renders docs/images/social-preview.png for GitHub's Settings → Social preview.
Fonts (SIL OFL): Gelasio, Inter, downloaded from Google Fonts into ~/.cache/epub-tr/fonts.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "images"
SRC, OUT = IMG / "banner.src.svg", IMG / "banner.svg"
SOCIAL_PNG = IMG / "social-preview.png"
FONTS = {
    "serif-700": "https://fonts.gstatic.com/s/gelasio/v14/cIfiMaFfvUQxTTqS3iKJkLGbI41wQL_vkCcs.ttf",
    "serif-400i": "https://fonts.gstatic.com/s/gelasio/v14/cIfsMaFfvUQxTTqS9Cu7b2nySBfeR6rA1M9v8zQ.ttf",
    "sans-400": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfMZg.ttf",
    "sans-600": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf",
}
CACHE = Path.home() / ".cache" / "epub-tr" / "fonts"


def load_fonts() -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, url in FONTS.items():
        f = CACHE / url.rsplit("/", 1)[1]
        if not f.exists():
            urllib.request.urlretrieve(url, f)
        out[key] = TTFont(f)
    return out


def attr(attrs: str, name: str, default=None):
    m = re.search(rf'\s{name}="([^"]*)"', attrs)
    return m.group(1) if m else default


def num(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Outliner:
    def __init__(self, fonts):
        self.fonts = fonts

    def width(self, font, text, size, tracking=0.0):
        cmap, hmtx, upm = font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm
        for ch in text:
            if ord(ch) not in cmap:
                raise SystemExit(f"missing glyph {ch!r} in {text!r}")
        return sum(hmtx[cmap[ord(c)]][0] for c in text) * size / upm + tracking * (len(text) - 1)

    def path(self, key, text, x, y, size, tracking=0.0):
        font = self.fonts[key]
        cmap, gs, hmtx, upm = font.getBestCmap(), font.getGlyphSet(), font["hmtx"], font["head"].unitsPerEm
        s, d = size / upm, []
        for ch in text:
            name = cmap[ord(ch)]
            pen = SVGPathPen(gs, ntos=num)
            gs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
            d.append(pen.getCommands())
            x += hmtx[name][0] * s + tracking
        return "".join(d), x


def build(fonts) -> tuple[str, list]:
    o, report = Outliner(fonts), []
    svg = SRC.read_text(encoding="utf-8")

    def chips(m):
        x, y, h, gap = (float(v) for v in m.group(1).split(","))
        g_attrs, body = m.group(2), m.group(3)
        size, fill = float(attr(g_attrs, "font-size")), attr(g_attrs, "fill", "#000")
        parts = []
        for cm in re.finditer(r"<text\b([^>]*)>(.*?)</text>", body, re.S):
            key, text = attr(cm.group(1), "data-font"), html.unescape(cm.group(2).strip())
            w = o.width(fonts[key], text, size) + 2 * 16
            d, _ = o.path(key, text, x + 16, y + h / 2 + size * 0.36, size)
            parts.append(f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" rx="{num(h / 2)}" '
                         f'fill="none" stroke="{fill}" stroke-opacity=".35" stroke-width="1.5"/>'
                         f'<path fill="{fill}" d="{d}"/>')
            x += w + gap
        report.append((f"chips ({len(parts)})", size, round(x - gap)))
        return "<g>" + "".join(parts) + "</g>"

    svg = re.sub(r'<g data-chips="([^"]+)"([^>]*)>(.*?)</g>', chips, svg, flags=re.S)

    def text(m):
        attrs, text_ = m.group(1), html.unescape(m.group(2).strip())
        key = attr(attrs, "data-font")
        if key not in fonts:
            raise SystemExit(f"<text> needs data-font (one of {list(fonts)}): {attrs}")
        x, y, size = float(attr(attrs, "x")), float(attr(attrs, "y")), float(attr(attrs, "font-size"))
        tracking, fill = float(attr(attrs, "letter-spacing", 0)), attr(attrs, "fill")
        max_w = float(attr(attrs, "data-max-width", "inf"))
        while o.width(fonts[key], text_, size, tracking) > max_w:
            size -= 0.5
        d, right = o.path(key, text_, x, y, size, tracking)
        report.append((text_, size, round(right)))
        return f'<path{f" fill={chr(34)}{fill}{chr(34)}" if fill else ""} d="{d}"/>'

    svg = re.sub(r"<text\b([^>]*)>(.*?)</text>", text, svg, flags=re.S)
    svg = re.sub(r"<!-- SOURCE:.*?-->",
                 "<!-- Generated by scripts/outline_banner.py from banner.src.svg: edit the source, not this file. -->",
                 svg, flags=re.S)
    return svg, report


def social(banner: str) -> str:
    """1280x640 card (GitHub's recommended size): the banner centred on the same paper background."""
    inner = re.search(r"<svg\b[^>]*>(.*)</svg>", banner, re.S).group(1)
    inner = re.sub(r"<title.*?</desc>", "", inner, flags=re.S)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640">\n'
            '  <rect width="1280" height="640" fill="#F6F1E7"/>\n'
            '  <defs><pattern id="ruled2" width="1280" height="26" patternUnits="userSpaceOnUse">'
            '<path d="M0 25.5H1280" stroke="#1B2A41" stroke-opacity=".05" stroke-width="1"/></pattern></defs>\n'
            '  <rect width="1280" height="640" fill="url(#ruled2)"/>\n'
            '  <rect width="12" height="640" fill="#E30A17"/>\n'
            f'  <g transform="translate(0 120)">{inner}</g>\n</svg>\n')


def render_png(svg_path: Path, png_path: Path):
    chrome = next((shutil.which(c) for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
    if not chrome:
        raise SystemExit("--png needs Google Chrome or Chromium on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "p.html"
        img = f'<img src="{svg_path.as_uri()}" width="1280" height="640">'
        page.write_text(f'<html><body style="margin:0">{img}</body></html>')
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
                        f"--screenshot={png_path}", "--window-size=1280,640", "--allow-file-access-from-files",
                        page.as_uri()], check=True, capture_output=True)


def main():
    fonts = load_fonts()
    svg, report = build(fonts)
    OUT.write_text(svg, encoding="utf-8")
    for t, size, right in report:
        print(f"  {right:>5}px right edge  {size:>5}px  {t}")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(svg) / 1024:.1f} KB)")
    if "--png" in sys.argv:
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / "social-preview.svg"
            card.write_text(social(svg), encoding="utf-8")
            render_png(card, SOCIAL_PNG)
        print(f"wrote {SOCIAL_PNG.relative_to(ROOT)} (1280x640)")


if __name__ == "__main__":
    main()
