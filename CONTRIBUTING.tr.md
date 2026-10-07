# epub-tr'ye katkıda bulunma

Yardımınız için teşekkürler. Hata bildirimleri, çeviri kalitesi örnekleri, yeni motorlar ve belge
düzeltmeleri memnuniyetle karşılanır. English: [CONTRIBUTING.md](CONTRIBUTING.md).

## Temel kurallar

- Nazik olun. Proje [Davranış Kuralları](CODE_OF_CONDUCT.md)'na uyar.
- Güvenlik sorunlarını gizli bildirin. Bkz. [SECURITY.md](SECURITY.md).
- Kitabı bozmayın. Bir değişiklik yeni EPUBCheck hatası eklememeli; biçimi, görselleri ya da
  bağlantıları kaybetmemeli; okuma sırasını (spine) değiştirmemeli.
- Varsayılan olarak ücretli hizmet yok. Her motor ücretli anahtar olmadan da çalışmaya devam etmeli.
- API anahtarı, çerez ya da telif hakkı süren kitap eklemeyin. `samples/` yalnızca kamu malı Project
  Gutenberg metinleri içerir.

## Geliştirme ortamı

```bash
git clone https://github.com/cumabozkurt/epub-tr.git && cd epub-tr
python3 -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install                                 # isteğe bağlı: her commit'te ruff, codespell, markdownlint
```

## Denetimler (CI'daki denetimlerin aynısı)

```bash
ruff check .                                  # lint
codespell                                     # yazım denetimi (Türkçe dosyalar atlanır)
python -m pytest -q --cov=epub_tr             # 120 çevrimdışı test, ağ gerekmez
python scripts/check_links.py --offline       # Markdown bağlantıları ve çapaları
npx markdownlint-cli2@0.23.3 "**/*.md"        # Markdown biçimi
python -m build && twine check --strict dist/*  # paketleme
python scripts/validate_epub.py               # örnek kitaplarda EPUBCheck (Java ve epubcheck gerekir)
```

Testler ağa çıkmaz. Motorlar taklit edilir (`tests/conftest.py`), HTTP motorları taklit bir `requests`
ile sınanır. Gerçekten internet gereken bir test `@pytest.mark.network` ile işaretlenmeli.

## Değişiklik yapma

1. Küçük bir düzeltmeden büyük her iş için önce bir sorun (issue) açın, yaklaşımda anlaşalım.
2. `main`'den dal açın, değişikliği odaklı tutun ve `tests/` altına bir test ekleyin ya da var olanı genişletin.
3. Çeviri kalitesini etkileyen değişikliklerde (istem, sözlük, redaksiyon) önce/sonra örneği ekleyin.
   `scripts/compare.py`, `--dump` dosyalarından yan yana bir tablo çıkarır.
4. Davranış ya da seçenek değiştiyse `README.md` **ve** `README.tr.md`'yi güncelleyin, `CHANGELOG.md`
   **ve** `CHANGELOG.tr.md` içinde `## [Unreleased]` altına bir satır ekleyin.
5. Çekme isteği (PR) açın. Şablon, yukarıdaki denetimleri sorar.

## Yeni motor ekleme

`epub_tr.engines.base.Engine` sınıfından türetin, sonra:

- makine çevirisi için `translate_one()` ya da `translate_batch()`, LLM için `complete(system, user)`
  yazın (LLM'de `is_llm = True` olmalı);
- `check()` kurulum ipucuyla birlikte `EngineUnavailable` fırlatmalı;
- motoru `epub_tr/engines/__init__.py` içindeki `ENGINES`'e kaydedin;
- taklit bir taşıma katmanıyla testler ekleyin, [docs/ENGINES.tr.md](docs/ENGINES.tr.md) ve iki
  README'ye birer satır ekleyin.

Parçaların, yer tutucuların ve çeviri hattının birbirine nasıl bağlandığı için:
[docs/ARCHITECTURE.tr.md](docs/ARCHITECTURE.tr.md).

## Sürüm yayımlama (bakımcı)

Sürümler etiketlerden çıkar. Bkz. [docs/AUTOMATION.tr.md](docs/AUTOMATION.tr.md):

```bash
python scripts/release.py 1.2.0 --dry-run   # dal, çalışma ağacı, changelog bölümleri ve testler denetlenir
python scripts/release.py 1.2.0             # sürüm yükseltilir, commit ve v1.2.0 etiketi itilir; iş akışı yayımlar
```
