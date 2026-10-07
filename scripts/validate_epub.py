#!/usr/bin/env python3
"""Translate a sample offline and check the output with EPUBCheck: no error may be added.

usage: python scripts/validate_epub.py [book.epub ...]   (default: samples/*.epub)
Runs the `echo` engine (monolingual) and a bilingual run, then compares EPUBCheck error counts of
source and outputs. Needs `epubcheck` on PATH (or EPUBCHECK_JAR + java).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def epubcheck_cmd():
    if shutil.which("epubcheck"):
        return ["epubcheck"]
    jar = os.environ.get("EPUBCHECK_JAR")
    if jar and shutil.which("java"):
        return ["java", "-jar", jar]
    sys.exit("epubcheck not found: install it or set EPUBCHECK_JAR")


def errors(path: str, workdir: str) -> list[str]:
    report = os.path.join(workdir, "report.json")
    subprocess.run(epubcheck_cmd() + [path, "--json", report], capture_output=True, text=True)
    with open(report, encoding="utf-8") as f:
        data = json.load(f)
    return sorted(f"{m['ID']} {m['message']}" for m in data.get("messages", []) if m["severity"] in ("ERROR", "FATAL"))


def main() -> int:
    books = sys.argv[1:] or sorted(glob.glob(str(ROOT / "samples" / "*.epub")))
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        for book in books:
            base = errors(book, tmp)
            for label, extra in (("monolingual", []), ("bilingual", ["--bilingual"])):
                out = os.path.join(tmp, f"{label}.epub")
                r = subprocess.run([sys.executable, "-m", "epub_tr.cli", "translate", book, "-e", "echo", "-o", out,
                                    "--no-cache", "-q", *extra], capture_output=True, text=True, encoding="utf-8")
                if r.returncode:
                    print(f"✗ {book} {label}: translate failed\n{r.stderr}")
                    failed = True
                    continue
                new = [e for e in errors(out, tmp) if e not in base]
                status = "✓" if not new else "✗"
                print(f"{status} {os.path.basename(book)} {label}: source errors {len(base)}, new errors {len(new)}")
                for e in new:
                    print("   ", e)
                failed |= bool(new)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
