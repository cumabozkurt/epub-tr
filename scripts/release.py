#!/usr/bin/env python3
"""One-command release: python scripts/release.py 1.1.0 [--dry-run] [--no-push]

Checks the tree, verifies CHANGELOG sections (EN + TR), bumps pyproject.toml and epub_tr/__init__.py,
runs lint + tests, commits, tags vX.Y.Z and pushes. The release workflow builds the wheel/sdist and
publishes the GitHub release with notes from both changelogs.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from release_notes import build  # noqa: E402


def sh(*cmd, check=True, capture=True):
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)
    if check and r.returncode:
        sys.exit(f"✗ {' '.join(cmd)} failed\n{r.stderr or ''}")
    return (r.stdout or "").strip()


def main():
    args = sys.argv[1:]
    dry, no_push = "--dry-run" in args, "--no-push" in args
    version = next((a for a in args if not a.startswith("--")), "").lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?", version):
        sys.exit("usage: python scripts/release.py <x.y.z> [--dry-run] [--no-push]")
    tag = "v" + version
    if sh("git", "rev-parse", "--abbrev-ref", "HEAD") != "main":
        sys.exit("✗ releases are cut from main")
    if sh("git", "tag", "-l", tag):
        sys.exit(f"✗ tag {tag} already exists")
    dirty = [line for line in sh("git", "status", "--porcelain", "--untracked-files=no").splitlines()
             if not line.endswith(("pyproject.toml", "epub_tr/__init__.py"))]
    if dirty and not dry:
        sys.exit("✗ uncommitted changes:\n" + "\n".join(dirty))
    build(tag)  # exits if a changelog section is missing
    print(f"✓ CHANGELOG sections found for {tag}")
    edits = {"pyproject.toml": (r'^version\s*=\s*"[^"]+"', f'version = "{version}"'),
             "epub_tr/__init__.py": (r'^__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"')}
    for f, (pat, rep) in edits.items():
        p = ROOT / f
        new = re.sub(pat, rep, p.read_text(encoding="utf-8"), count=1, flags=re.M)
        print(f"• {'would set' if dry else 'set'} {f} → {version}")
        if not dry:
            p.write_text(new, encoding="utf-8")
    print("• lint + tests …")
    sh(sys.executable, "-m", "ruff", "check", ".", capture=False)
    sh(sys.executable, "-m", "pytest", "-q", capture=False)
    if dry:
        print(f"dry run: would commit 'release: {tag}', tag {tag} and push main + tag")
        return
    sh("git", "add", *edits)
    if sh("git", "diff", "--cached", "--name-only"):
        sh("git", "commit", "-m", f"release: {tag}")
    sh("git", "tag", "-a", tag, "-m", tag)
    print(f"✓ tagged {tag}")
    if no_push:
        print(f"not pushed; run: git push origin main {tag}")
        return
    sh("git", "push", "origin", "main", capture=False)
    sh("git", "push", "origin", tag, capture=False)
    print(f"✓ pushed. The release workflow will build and publish {tag}.")


if __name__ == "__main__":
    main()
