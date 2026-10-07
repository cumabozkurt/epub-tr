## What & why / Ne ve neden

<!-- Short description. Link the issue: Closes #123 -->

## Type / Tür

- [ ] Bug fix / Hata düzeltme
- [ ] New engine or engine fix / Yeni motor ya da motor düzeltmesi
- [ ] Translation pipeline or prompts / Çeviri hattı ya da istemler
- [ ] EPUB reading/writing / EPUB okuma/yazma
- [ ] Docs / Belgeler
- [ ] CI / tooling

## Checklist / Kontrol listesi

- [ ] `ruff check .` and `python -m pytest -q` pass (no test may need the network)
- [ ] New behaviour has a test in `tests/` (use the fake engines in `tests/conftest.py`)
- [ ] Prompt changes include a before/after sample (`scripts/compare.py`)
- [ ] `python scripts/validate_epub.py` adds no EPUBCheck errors (if EPUB I/O changed)
- [ ] README.md **and** README.tr.md updated if user-facing behaviour changed
- [ ] CHANGELOG.md **and** CHANGELOG.tr.md have an entry under `[Unreleased]`
