#!/usr/bin/env python3
"""Build GitHub release notes for a version from CHANGELOG.md (EN) and CHANGELOG.tr.md (TR).

usage: python scripts/release_notes.py v1.1.0 > notes.md   (default: version from pyproject.toml)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "cumabozkurt/epub-tr"


def version_from_pyproject() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1)


def section(md: str, version: str) -> str | None:
    v = version.lstrip("v")
    m = re.search(rf"^## \[{re.escape(v)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else None


def build(version: str) -> str:
    tag = "v" + version.lstrip("v")
    en = section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), tag)
    tr = section((ROOT / "CHANGELOG.tr.md").read_text(encoding="utf-8"), tag)
    if not en or not tr:
        raise SystemExit(f"CHANGELOG.md / CHANGELOG.tr.md need a '## [{tag[1:]}]' section")
    install = (f"```bash\npip install epub-tr=={tag[1:]}\n# or the wheel attached to this release\n"
               f"pip install \"epub-tr @ https://github.com/{REPO}/releases/download/{tag}/epub_tr-{tag[1:]}-py3-none-any.whl\"\n"
               f"# or from source\npip install \"git+https://github.com/{REPO}@{tag}\"\n```")
    return "\n".join([
        "## English", "", en, "", "### Install", "", install, "",
        "Assets: wheel, source distribution and `SHA256SUMS.txt` (verify with `sha256sum -c SHA256SUMS.txt`).", "",
        "---", "", "## Türkçe", "", tr, "", "### Kurulum", "", install, "",
        "Dosyalar: wheel, kaynak paketi ve `SHA256SUMS.txt` (`sha256sum -c SHA256SUMS.txt` ile doğrulayın).", "",
    ])


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else version_from_pyproject()))
