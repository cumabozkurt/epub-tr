# epub-tr — edebi kalitede EPUB çevirmeni (önce Türkçe)

[English README](README.md) · MIT Lisansı

`epub-tr`, EPUB kitapları **doğal ve edebi bir Türkçeye** çevirir; kitabın yapısını bozmaz:
HTML biçimlendirmesi, görseller, CSS, yazı tipleri, içindekiler (nav + NCX), üst veriler ve
kitap içi bağlantılar korunur. Tüm motorlar **ücretsizdir** (ücretli API anahtarı gerekmez).

## Özellikler

* **Yapıyı koruyan EPUB okuma/yazma** – `ebooklib` + `lxml` ile okuma; yazma ZIP düzeyinde yapılır:
  orijinal dosyalar bayt bayt kopyalanır, yalnızca çevrilen XHTML'ler, OPF (`dc:language` → `tr`,
  çevrilmiş başlık) ve NCX/nav etiketleri değiştirilir. Çıktı EPUBCheck'ten girdi kadar temiz geçer.
* **Satır içi biçim korunur** – `<i>`, `<em>`, `<a id=…>`, `<br/>`, dipnot bağlantıları motor için
  `<g1>…</g1>`, `<x2/>` yer tutucularına çevrilir ve sonra tüm öznitelikleriyle geri kurulur.
* **İki dilli mod** (`--bilingual`) – her paragrafın altına çevirisi eklenir.
* **Edebi LLM hattı**
  * paragraflar `<seg id>` kimlikli parçalara bölünür (`--chunk-chars`),
  * **bağlam penceresi**: önceki paragraflar (kaynak + çeviri) her istekle gönderilir,
  * **yürüyen sözlük**: model ad/terim kararlarını bildirir, kitabın geri kalanında aynen kullanılır
    (önbellekte saklanır → devam ettirmede tutarlılık); `--glossary` ile kendi sözlüğünüzü verin,
  * otomatik **özel ad tespiti** (adlar korunur, ekler kesme işaretiyle: *Della'nın*, *Jim'e*),
  * Türkçe edebi sistem istemi: deyimsel anlatım, üslup/ton/dönem korunur, TDK yazımı, sen/siz
    tutarlılığı, diyalog noktalaması (`--dialogue quotes|dash` → tırnak ya da uzun çizgi),
  * isteğe bağlı **ikinci gözden geçirme/redaksiyon geçişi** (`--polish`, istenirse başka motorla
    `--polish-engine`).
* **Hız ve dayanıklılık** – eşzamanlılık (LLM'de bölümler paralel), SQLite önbellek = **kaldığı yerden
  devam**, yeniden deneme, parça bazında **yedek motor zinciri** (`--fallback google,argos`), OpenCode
  ücretsiz kota sınırında hızlı hata ve diğer ücretsiz modellere otomatik geçiş.

## Motorlar

| motor | tür | gereksinim |
|---|---|---|
| `opencode` | `opencode run` ile LLM (OpenCode Zen **ücretsiz** modelleri) | `npm i -g opencode-ai` |
| `ollama` | yerel LLM (varsayılan `gemma3:4b`; `aya-expanse:8b` önerilir) | Ollama |
| `google` | Google Çeviri ücretsiz uç noktaları | – |
| `bing`, `yandex`, `modernmt` | `translators` paketi (GPL-3, isteğe bağlı) | `pip install translators` |
| `mymemory` | MyMemory API (anonim ~5 bin karakter/gün) | – |
| `lingva` | Lingva genel sunucuları (`LINGVA_URL`) | – |
| `libretranslate` | LibreTranslate sunucusu | kendi sunucunuz veya anahtar |
| `argos` | Argos Translate, tamamen çevrimdışı | `pip install argostranslate` |
| `openrouter`, `gemini`, `groq`, `mistral`, `openai` | OpenAI uyumlu API'ler (ücretsiz katmanlar) | ilgili API anahtarı |

## Kurulum

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[argos,extra]'
npm i -g opencode-ai
```

## Kullanım

```bash
# en iyi ücretsiz kalite: OpenCode LLM + redaksiyon, yedek olarak Google
epub-tr translate kitap.epub -o kitap.tr.epub --engine opencode --polish --fallback google

# yerel ve gizli
epub-tr translate kitap.epub --engine ollama -m aya-expanse:8b --chunk-chars 1500

# hızlı, iki dilli baskı
epub-tr translate kitap.epub --engine google --bilingual

# yalnızca 1-3. bölümler, ilk 50 paragraf, uzun çizgili diyalog, kendi sözlüğünüz
epub-tr translate kitap.epub --chapters 1-3 --limit 50 --dialogue dash --glossary adlar.tsv

epub-tr engines --check      # hangi motorlar kullanılabilir?
epub-tr inspect kitap.epub   # neler çevrilecek?
```

Not: OpenCode'un ücretsiz katmanı **IP başına** sınırlıdır. Kota dolduğunda (`FreeUsageLimitError`)
araç hızlıca diğer ücretsiz modelleri ve ardından `--fallback` motorlarını dener; daha sonra yeniden
çalıştırdığınızda önbellekteki parçalar tekrar çevrilmez.
