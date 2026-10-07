# Otomasyon: CI, denetimler ve sürümler

English: [AUTOMATION.md](AUTOMATION.md) · [README](../README.tr.md)'ye dön

## İş akışları

| iş akışı | tetikleyici | ne yapar |
|---|---|---|
| [CI](../.github/workflows/ci.yml) | `main`'e push ve PR, elle | **lint**: ruff, codespell, markdownlint, göreli bağlantılar ve çapalar, sürüm notu derleme · **test**: Ubuntu, Windows ve macOS × Python 3.10, 3.11, 3.12, 3.13 üzerinde kapsama ölçümlü pytest, ayrıca CLI duman testi · **package**: sdist ve wheel, `twine check --strict`, sürüm tutarlılığı, temiz bir venv'e kurulan wheel ile çevrimdışı örnek çeviri · **epubcheck**: iki örnek kitabın tek dilli ve iki dilli çıktılarında EPUBCheck 5.4.0; bir çıktıda kaynağından fazla hata varsa başarısız olur |
| [CodeQL](../.github/workflows/codeql.yml) | push, PR, haftalık | Python ve GitHub Actions için `security-and-quality` sorguları |
| [Links](../.github/workflows/links.yml) | Markdown değişiklikleri, haftalık | izlenen tüm Markdown dosyalarında göreli bağlantılar, çapalar ve dış adresler |
| [Release](../.github/workflows/release.yml) | `v*` etiketi, elle (etiketle) | etiket = `pyproject.toml` = `epub_tr.__version__` denetimi, ruff, pytest, derleme, `twine check`, `SHA256SUMS.txt`, iki changelog'dan notlar, ardından wheel, sdist ve sağlama dosyasıyla `gh release create --verify-tag`; en sonda üç dosyanın da sürümde olduğunu denetler |
| [Dependabot](../.github/dependabot.yml) | haftalık | pip bağımlılıklarını ve GitHub Actions'ı günceller |

Testler ağa çıkmaz. Motorlar taklit edilir, HTTP isteklerinin yerine sahteleri geçer. Bu sayede CI
belirleyici kalır ve ücretsiz kotalara bağlı olmaz. Gerçek motor sonuçları [TEST_REPORT.md](../TEST_REPORT.md) içinde.

## Yerel karşılıkları

```bash
pip install -e ".[dev]"
ruff check . && codespell && python -m pytest -q --cov=epub_tr
python scripts/check_links.py            # dış adresleri atlamak için --offline ekleyin
npx markdownlint-cli2@0.23.3 "**/*.md"
python -m build && twine check --strict dist/*
python scripts/validate_epub.py          # Java ve epubcheck (ya da EPUBCHECK_JAR) gerekir
python scripts/release_notes.py v1.1.0   # sürüm notlarını önizleyin
```

## Sürüm yayımlama

1. Değişiklikleri hem `CHANGELOG.md` hem de `CHANGELOG.tr.md` içinde yeni bir `## [X.Y.Z] - YYYY-AA-GG`
   başlığı altına yazın ve commit'leyin.
2. Önce `python scripts/release.py X.Y.Z --dry-run`, sonra `python scripts/release.py X.Y.Z`. Betik;
   `main` dalında ve temiz bir çalışma ağacında değilseniz, etiket zaten varsa ya da changelog bölümlerinden
   biri eksikse çalışmaz. Koşullar uygunsa `pyproject.toml` ile `epub_tr/__init__.py`'yi yükseltir, ruff ve
   pytest'i çalıştırır, `release: vX.Y.Z` commit'ini ve açıklamalı etiketi oluşturur, `main` ile etiketi
   iter. Asla zorla itmez (force-push).
3. **Release** iş akışı derler ve yayımlar. Dosyaları `sha256sum -c SHA256SUMS.txt` ile doğrulayın.

PyPI yayını henüz kurulu değil. Bunun için PyPI'da güvenilir yayıncı (trusted publisher) ya da bir
belirteç gerekiyor. Şimdilik kurulum, GitHub sürümüne eklenen wheel'den ya da `git+https://…@vX.Y.Z`
adresinden yapılıyor.

## Sürüm kanıtları

| sürüm | tarih | sürüm sayfası | iş akışı | dosyalar |
|---|---|---|---|---|
| v1.0.0 | 2026-10-03 | [sürüm](https://github.com/cumabozkurt/epub-tr/releases/tag/v1.0.0) | iş akışı yokken `gh release create` ile elle oluşturuldu | – |
