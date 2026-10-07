#!/usr/bin/env python3
"""Check Markdown links: relative files/anchors always, external URLs unless --offline.

usage: python scripts/check_links.py [--offline] [files...]   (default: every tracked *.md)
Exit code 1 if anything is broken. Standard library only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)|(?:href|src)=\"([^\"]+)\"")
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
SKIP_HOSTS = ("localhost", "127.0.0.1", "example.com", "example.org")
# API base URLs that answer 404 on GET / by design
SKIP_URLS = ("https://openrouter.ai/api/v1", "https://api.groq.com/openai/v1", "https://api.mistral.ai/v1",
             "https://api.openai.com/v1", "https://generativelanguage.googleapis.com")


def slug(heading: str) -> str:
    """GitHub-style anchor for a heading."""
    h = re.sub(r"<[^>]+>", "", heading).strip().lower()
    h = "".join(c for c in h if unicodedata.category(c)[0] in "LNPZ" or c in "-_ ")
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = CODE_RE.sub("", path.read_text(encoding="utf-8"))
    seen: dict[str, int] = {}
    out = set()
    for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*$", text, re.M):
        s = slug(m.group(1))
        n = seen.get(s, 0)
        out.add(s if n == 0 else f"{s}-{n}")
        seen[s] = n + 1
    out.update(re.findall(r'id="([^"]+)"', text))
    return out


def md_files(args) -> list[Path]:
    if args:
        return [Path(a).resolve() for a in args]
    files = subprocess.run(["git", "ls-files", "*.md", "**/*.md"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    return sorted({ROOT / f for f in files if not f.startswith(("out/", "samples/"))})


def check_url(url: str) -> str | None:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 epub-tr-link-check"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return None if r.status < 400 else f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):  # bot protection / rate limits are not broken links
                return None
            if attempt:
                return f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            if attempt:
                return type(e).__name__
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip external URLs")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    errors, external = [], {}
    for f in md_files(a.files):
        text = CODE_RE.sub("", f.read_text(encoding="utf-8"))
        for m in LINK_RE.finditer(text):
            target = m.group(1) or m.group(2)
            line = text.count("\n", 0, m.start()) + 1
            where = f"{f.relative_to(ROOT)}:{line}"
            if target.startswith(("http://", "https://")):
                host = urllib.parse.urlparse(target).hostname or ""
                if not host.endswith(SKIP_HOSTS) and not target.startswith(SKIP_URLS):
                    external.setdefault(target, where)
                continue
            if target.startswith(("mailto:", "data:")):
                continue
            path, _, frag = target.partition("#")
            dest = (f.parent / urllib.parse.unquote(path)).resolve() if path else f
            if not dest.exists():
                errors.append(f"{where}: missing file {target}")
            elif frag and dest.suffix == ".md" and frag not in anchors(dest):
                errors.append(f"{where}: missing anchor #{frag} in {dest.relative_to(ROOT)}")
    if not a.offline:
        with cf.ThreadPoolExecutor(8) as ex:
            for url, err in zip(external, ex.map(check_url, external)):
                if err:
                    errors.append(f"{external[url]}: {url} ({err})")
    for e in errors:
        print("ERROR", e)
    print(f"{len(external)} external URL(s){' (not checked, --offline)' if a.offline else ''} · {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
