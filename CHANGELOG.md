# Changelog / Değişiklik günlüğü

## 1.0.0 — 2026-10-03

First public release. / İlk herkese açık sürüm.

**EN**
- Structure-preserving EPUB 2/3 reader and ZIP-level writer (XHTML, OPF language/title, nav + NCX labels; everything else byte-for-byte).
- Inline-markup placeholders (`<gN>…</gN>`, `<xN/>`) with lenient fallback that keeps anchors and links.
- Engines: OpenCode (free Zen models, automatic model switching on rate limits), Ollama, Google (free endpoints), Bing/Yandex/ModernMT (`translators`), MyMemory, Lingva, LibreTranslate, Argos (offline), OpenAI-compatible presets (OpenRouter, Gemini, Groq, Mistral, OpenAI).
- Literary LLM pipeline: chunking with stable segment ids, context window, running glossary, proper-name detection, Turkish literary prompt, dialogue style (`quotes`/`dash`), optional polish pass.
- Bilingual output, per-chunk fallback chain, retries, SQLite cache/resume, chapter/segment selection, stats and JSONL dumps.
- TOC harmonisation and re-wrapping of single-element segments; Gutenberg boilerplate skipped by default.
- Test report on two Project Gutenberg books (EPUBCheck: no new errors) and a survey of 15 open-source translators.

**TR**
- Yapıyı koruyan EPUB 2/3 okuyucu ve ZIP düzeyinde yazıcı (XHTML, OPF dil/başlık, nav + NCX etiketleri; geri kalan her şey bayt bayt).
- Satır içi biçim için yer tutucular (`<gN>…</gN>`, `<xN/>`) ve bağlantıları koruyan esnek geri dönüş.
- Motorlar: OpenCode (ücretsiz Zen modelleri, kota sınırında otomatik model değişimi), Ollama, Google (ücretsiz uç noktalar), Bing/Yandex/ModernMT (`translators`), MyMemory, Lingva, LibreTranslate, Argos (çevrimdışı), OpenAI uyumlu hazır ayarlar (OpenRouter, Gemini, Groq, Mistral, OpenAI).
- Edebi LLM hattı: kararlı kimlikli parçalama, bağlam penceresi, yürüyen sözlük, özel ad tespiti, Türkçe edebi istem, diyalog biçimi (`quotes`/`dash`), isteğe bağlı redaksiyon geçişi.
- İki dilli çıktı, parça başına yedek motor zinciri, yeniden deneme, SQLite önbellek/devam, bölüm/parça seçimi, istatistik ve JSONL döküm.
- İçindekiler uyumlaştırma, tek öğeli parçaların yeniden sarılması; Gutenberg başlık/lisans metni varsayılan olarak atlanır.
- İki Project Gutenberg kitabı üzerinde test raporu (EPUBCheck: yeni hata yok) ve 15 açık kaynak çevirmenin incelemesi.
