# Mimari

English: [ARCHITECTURE.md](ARCHITECTURE.md) · [README](../README.tr.md)'ye dön

`epub-tr` sırayla üç iş yapar. Kitabı parçalara ayırarak **okur**, parçaları bir ya da birkaç motordan
geçirerek **çevirir**, ve yalnızca çevrilen kısımları özgün kitaptan farklı olan yeni bir EPUB **yazar**.

```text
kitap.epub
  │
  ├─ epub_io.Book ─ ebooklib (üst veri, manifest, spine) + lxml (XHTML, OPF, nav, NCX)
  │     └─ blocks.encode(): blok öğe → Segment(enc="Della <g1>counted</g1> it.<x2/>")
  │
  ├─ pipeline.Translator
  │     ├─ MT motorları  → parça grupları (engine.max_chars), iş parçacığı havuzu
  │     ├─ LLM motorları → belge başına <seg id=N>…</seg> öbekleri (--chunk-chars), belgeler paralel
  │     │                  + bağlam (önceki paragraflar ve çevirileri)
  │     │                  + yürüyen sözlük + tespit edilen özel adlar + edebi istem (prompts.py)
  │     │                  → isteğe bağlı --polish geçişi (aynı ya da başka LLM)
  │     ├─ cache.Cache   → SQLite, anahtar = motor + model + aşama + diller + kaynak metin; sözlük kitap başına
  │     └─ öbek başına yedek motor zinciri, artan beklemeli yeniden deneme, hızlı kota sınırı tespiti
  │
  ├─ pipeline.harmonize_toc(): içindekiler etiketleri çevrilen bölüm başlıklarını izler
  │
  └─ Book.apply() + Book.write()
        ├─ blocks.decode_into(): yer tutucular → tüm öznitelikleriyle özgün öğeler
        │     (motor etiketleri bozduysa esnek yol metni, çapaları ve bağlantı hedeflerini korur)
        └─ ZIP yeniden yazımı: her girdi aynı sırayla bayt bayt kopyalanır (mimetype ilk ve sıkıştırmasız);
           yalnızca çevrilen XHTML, OPF (dc:language, başlık), nav ve NCX değişir
```

## Parçalar ve yer tutucular

**Parça** (segment), metin içeren tek bir blok öğedir: `p`, `h1`–`h6`, `li`, `td`, `blockquote`, `dd`
vb. ve içindekiler etiketleri. Satır içi içerik, motor gerçek etiket görmesin diye kodlanır:

| kaynak | motora giden |
|---|---|
| `<i>`, `<em>`, `<span class=…>`, `<a href=…>` | `<g1>…</g1>` (çift, numaralı) |
| `<br/>`, `<img/>`, boş `<a id=…/>` | `<x2/>` (tek etiket) |

Çeviriden sonra `decode_into()` öğeyi yeniden kurar. Özgün özniteliklerin hepsi geri gelir; hedef dil
gerektiriyorsa etiketlerin sırası değişebilir. Motor bir etiketi düşürdüyse ya da uydurduysa **esnek**
yol çevrilen metni korur ve çapalarla bağlantıları yeniden ekler; iç bağlantılar ve dipnotlar bozulmaz.
Çalışma özetinde bu `markup_fallbacks` olarak sayılır.

Hiç çevrilmeyenler: `script`, `style`, `pre`, `code`, `math`, `svg`, `translate="no"` ya da `notranslate`
sınıflı öğeler, harf içermeyen paragraflar (yalnızca rakam, süs) ve (varsayılan olarak) Project Gutenberg başlık ve
lisans metni.

## LLM yolu

1. **Öbekleme.** Bir belgenin parçaları yaklaşık `--chunk-chars` karakterlik öbeklere toplanır. Her parça
   `<seg id="N">…</seg>` olarak gider, yanıt kimlikle eşleştirilir. Yanıtta eksik kalan
   parçalar en çok iki tur yeniden istenir, sonra yedek motora geçer.
2. **Bağlam.** Son `--context` kaynak paragraf ve çevirileri her öbekle gönderilir; böylece ton, sen/siz
   ve adlar öbek sınırlarında da tutarlı kalır.
3. **Sözlük.** Model yanıtın sonuna `<glossary>kaynak => hedef</glossary>` ekleyebilir. Bir girdi
   yalnızca kaynak terim o öbekte geçiyorsa öğrenilir; bu, ters ya da uydurma çiftleri engeller. Girdiler
   önbellekte kitap başına saklanır; yüklenirken yalnızca o anki metinde geçenler kullanılır.
   `--glossary` girdileri her zaman önceliklidir.
4. **Adlar.** Cümle ortasında tekrar eden büyük harfli sözcükler tespit edilir ve "bu adları koru"
   diye iletilir. Türkçe ekler kesme işaretiyle eklenir (*Della'nın*).
5. **Redaksiyon** (`--polish`). İkinci geçiş kaynağı ve taslağı alır, düzeltilmiş bir sürüm döndürür.
   Redaksiyon başarısız olursa taslak korunur.

## Yazma

`Book.write()`, değiştirmediği dosyaları asla yeniden üretmez. Yazı tipleri, görseller, CSS, şifreleme
bilgisi ve bilinmeyen dosyalar özgün baytlarını korur. OPF'de `dc:language` hedef dile ayarlanır ve
başlık çevrilir. **İki dilli** modda çevrilen kopya her kaynak bloğun ardına eklenir; belge geçerli
kalsın diye kopyadaki kimlikler (`id`) silinir.

## Modüller

| modül | görev |
|---|---|
| `epub_tr/cli.py` | argüman ayrıştırma, motor ve yedek kurulumu, özet, istatistik ve döküm; güvenli konsol kodlaması |
| `epub_tr/epub_io.py` | EPUB okuma (parçalar, içindekiler etiketleri, Gutenberg metni tespiti), çevirileri uygulama, ZIP yazma |
| `epub_tr/blocks.py` | blok öğe ⇄ yer tutuculu metin kodlaması, esnek geri kurma |
| `epub_tr/pipeline.py` | öbekleme, bağlam, sözlük, adlar, redaksiyon, eşzamanlılık, yeniden deneme, yedek motor, içindekiler uyumu |
| `epub_tr/prompts.py` | sistem, kullanıcı ve redaksiyon istemleri; Türkçe edebi kurallar; diyalog biçimi |
| `epub_tr/cache.py` | SQLite önbellek (WAL, kilitte yeniden deneme), kitap başına sözlük |
| `epub_tr/engines/` | `base.py` arayüzü, `llm.py` (OpenCode, Ollama, OpenAI uyumlu), `mt.py` (Google, translators, MyMemory, Lingva, LibreTranslate, Argos) |

Motor ayrıntıları için [ENGINES.tr.md](ENGINES.tr.md), CI ve sürümler için [AUTOMATION.tr.md](AUTOMATION.tr.md).
