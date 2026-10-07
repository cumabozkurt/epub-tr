# Değişiklik günlüğü

Bu projedeki önemli değişiklikler burada tutulur. Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/)
kurallarına uyar, sürümler [Anlamsal Sürümleme](https://semver.org/lang/tr/) ile numaralanır.
English: [CHANGELOG.md](CHANGELOG.md).

## [Unreleased]

### Eklendi

- Proje afişi (`docs/images/banner.svg`; metinler eğriye çevrildiği için her yerde aynı görünür) iki
  README'nin en üstünde, 1280×640 sosyal önizleme görseli (`docs/images/social-preview.png`) ve ikisini de
  `docs/images/banner.src.svg` kaynağından üreten `scripts/outline_banner.py`.
- Sürüm iş akışı: `PYPI_API_TOKEN` sırrı tanımlıysa `pypi` işi wheel ve sdist dosyalarını `twine` ile PyPI'a
  yükler ve `pip install epub-tr==X.Y.Z` ile doğrular; sır yoksa bir bildirimle atlanır. Güvenilir yayıncı
  (trusted publishing) alternatif olarak belgelendi.

## [1.1.0] - 2026-10-08

### Eklendi

- Test takımı: 120 çevrimdışı test (sahte motorlar ve taklit HTTP ile, ağ yok). Yer tutucu kodlamayı,
  EPUB okuma ve yazmayı, çeviri hattını, tüm motor bağdaştırıcılarını, istemleri ve CLI'yi kapsıyor.
  Kapsama oranı %93.
- Ubuntu, Windows ve macOS'ta, Python 3.10–3.13 ile CI. Ayrıca ruff, codespell, markdownlint,
  çevrimdışı bağlantı denetimi, `twine check` ile paket derleme, temiz bir venv'de wheel kurulumu ve
  bir EPUBCheck 5.4.0 işi.
- CodeQL (Python ve Actions), haftalık bağlantı denetimi, Dependabot (pip ve GitHub Actions) ve
  pre-commit kancaları.
- Etiketle tetiklenen sürüm iş akışı: etiketin sürümle eşleştiğini denetler, testleri çalıştırır,
  sdist ve wheel derler, `SHA256SUMS.txt` yazar ve İngilizce ile Türkçe notlu bir GitHub sürümü yayımlar.
- Sürüm araçları: `scripts/release.py` ve `scripts/release_notes.py`. Doğrulama araçları:
  `scripts/validate_epub.py` (EPUBCheck JSON) ve `scripts/check_links.py` (Markdown bağlantıları ve çapaları).
- Topluluk dosyaları: CONTRIBUTING (EN/TR), CODE_OF_CONDUCT, SECURITY, iki dilli sorun formları (hata,
  çeviri kalitesi, özellik isteği) ve bir çekme isteği şablonu.
- Belgeler: `docs/ARCHITECTURE.md`, `docs/ENGINES.md` ve `docs/AUTOMATION.md`; her birinin Türkçesi de var.
- *The Gift of the Magi* üzerinde gerçek OpenCode sonuçları: ham, redaksiyonlu ve iki dilli EPUB'lar,
  çalışma günlükleri, yan yana karşılaştırma ve EPUBCheck çıktısı. Hepsi `out/` altında depoda.
- Çalışma özetine `engine_models` eklendi. Her motorun sonunda gerçekten kullandığı modeli kaydeder;
  OpenCode çalışma sırasında model değiştirebiliyor.

### Değişti

- OpenCode artık boş çıktı veren bir modelde de sıradaki ücretsiz modele geçiyor. Önceden bunu yalnızca
  kota sınırında yapıyordu. Gerçek çalıştırmada bir model art arda boş yanıt döndürdü.
- Çalıştırma başlığındaki motor listesi `opencode/opencode/big-pickle` yerine `opencode/big-pickle` yazıyor.
- En düşük Python sürümü artık 3.10. Paket üst verisi tamamlandı: sınıflandırıcılar, bağlantılar,
  anahtar sözcükler ve `dev` ekleri.

### Düzeltildi

- İki dilli çıktı: yeniden kurulan satır içi çapalar `id` özniteliğini koruyordu, bu yüzden EPUB'da
  yinelenen kimlikler oluşabiliyordu.
- Yürüyen sözlük, modelin bildirdiği ters ya da uydurma girdileri kabul ediyordu (örneğin
  `Hediyenin Getirdiği Mutluluk => The Gift of the Magi`). Artık kaynak terim yalnızca o parçada geçiyorsa saklanıyor; önceki çalıştırmalardan kalan geçersiz girdiler yok sayılıyor.
- MyMemory, 500 bayt sınırını aşan tek bir cümlede sonsuz özyinelemeye giriyordu. Metin artık önce
  cümleye, sonra sözcüğe, en son karaktere göre bölünüyor.
- Bir parçadan alınan düz metinde `<br/>` iki yanındaki sözcükler birleşiyordu.
- Son denemeden sonra gereksiz bekleme yapılmıyor.
- Windows'ta OpenCode ajan yapılandırması UTF-8 olmadan yazılıyordu. Zaman aşımına uğrayan OpenCode
  süreçleri artık düzgünce sonlandırılıyor.
- Türkçe karakterleri kodlayamayan konsollarda CLI artık çökmüyor.
- EPUB dosyaları ve önbellek artık düzgünce kapatılıyor.

## [1.0.0] - 2026-10-03

### Eklendi

- Yapıyı koruyan EPUB 2/3 okuyucu ve ZIP düzeyinde yazıcı: XHTML, OPF dili ve başlığı ile nav ve NCX
  etiketleri yeniden yazılır, geri kalan her şey bayt bayt kopyalanır.
- Satır içi biçim için yer tutucular (`<gN>…</gN>`, `<xN/>`) ve bağlantıları koruyan esnek bir geri dönüş.
- Motorlar:
  - OpenCode: ücretsiz Zen modelleri, kota sınırında otomatik model değişimi.
  - Ollama.
  - Google: ücretsiz uç noktalar.
  - Bing, Yandex ve ModernMT, `translators` üzerinden.
  - MyMemory, Lingva ve LibreTranslate.
  - Argos: çevrimdışı.
  - OpenAI uyumlu hazır ayarlar: OpenRouter, Gemini, Groq, Mistral ve OpenAI.
- Edebi LLM hattı:
  - kararlı kimlikli parçalama, bağlam penceresi ve yürüyen sözlük;
  - özel ad tespiti;
  - Türkçe edebi istem ve diyalog biçimi seçimi (`quotes` ya da `dash`);
  - isteğe bağlı redaksiyon geçişi.
- İki dilli çıktı, her parça için yedek motor zinciri, yeniden deneme, SQLite önbellek ve kaldığı yerden
  devam, bölüm ve parça seçimi, istatistik ve JSONL dökümleri.
- İçindekiler uyumlaştırma ve tek öğeli parçaların yeniden sarılması. Gutenberg başlık ve lisans metni
  varsayılan olarak atlanır.
- İki Project Gutenberg kitabı üzerinde test raporu (EPUBCheck: yeni hata yok) ve 15 açık kaynak çevirmenin incelemesi.

[Unreleased]: https://github.com/cumabozkurt/epub-tr/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/cumabozkurt/epub-tr/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/cumabozkurt/epub-tr/releases/tag/v1.0.0
