# Motorlar

English: [ENGINES.md](ENGINES.md) · [README](../README.tr.md)'ye dön

Tüm motorlar ücretsiz kullanılabilir. Bazıları ücretsiz bir kurulum ya da ücretsiz bir anahtar ister;
hiçbiri ücretli anahtar gerektirmez. Makinenizde hangilerinin çalıştığını `epub-tr engines --check` gösterir.

## Ölçülmüş sıralama (edebi Türkçe)

Test metni O. Henry'nin *The Gift of the Magi* öyküsü: 51 parça, 11.237 karakter. Tüm veriler
[TEST_REPORT.md](../TEST_REPORT.md) içinde, çıktılar [`out/`](../out) klasöründe.

| # | motor / ayar | kalite | süre (tüm öykü) | kapsam | notlar |
|---|---|---|---|---|---|
| 1 | **`opencode --polish`** (`opencode/space-bunny-free`) | en iyisi: deyimsel, edebi, doğru üslup | 6.932 sn | ilk çalıştırmada 43/51, bir kez devam ettirince 51/51 | ücretsiz katman çok yavaş; `--fallback` kullanın |
| 2 | `opencode` (yalnızca taslak, aynı model) | çok iyi ama yazım hataları var | 3.730 sn | 45/51 | "beni böyle **srma**", "**uyacak**" (*uzayacak* yerine), "Şapkanını" |
| 3 | `bing` | en doğal makine çevirisi | 42,8 sn | 51/51 | "cent" kalıyor; *she cried* için "diye ağladı" |
| 4 | `google` | akıcı, deyimlerde birebir | 1,7 sn | 51/51 | "buldozerlerle ezerek", düz tırnaklar |
| 5 | `yandex` ≈ `modernmt` | Google gibi, daha çok kalıp çeviri | 16–18 sn | 51/51 | ModernMT noktalamadan önce boşluk bırakıyor |
| 6 | `ollama` aya-expanse:8b | deyimsel ama sayıları değiştiriyor | 221 sn / 16 parça | kısmi | 87 sent yerine "otuz yedi sent" |
| 7 | `ollama` gemma3:4b (redaksiyonlu ya da değil) | sözcük uyduruyor | 481 sn / 720 sn | 51/51 | "melekse", "Şaptonu"; 4B bu iş için küçük |
| 8 | `argos` (çevrimdışı) | birebir, çoğu zaman dil bilgisi hatalı | 820 sn | 51/51 | yalnızca düz metin |

**Öneri**

- En yüksek kalite: `--engine opencode --polish --fallback bing` (ya da `--fallback google`). Boşlukları
  doldurmak için daha sonra yeniden çalıştırın: önbellekteki parçalar kullanılır, modele yalnızca
  eksikler gider.
- Hızlı ve iyi: `--engine bing` (`pip install translators` gerekir) ya da kurulumsuz `--engine google`.
- Gizli ya da çevrimdışı: `--engine ollama -m aya-expanse:8b` (RAM yetiyorsa daha büyük bir model) ya da `argos`.

En iyi çıktı bile yayımlanmadan önce insan redaksiyonundan geçmeli.

## OpenCode (ücretsiz Zen modelleri)

`opencode run`, özel bir ajan klasöründe çalışır. Oradaki `opencode.json`, araç kullanmayan bir `epubtr`
ajanı tanımlar; bu ajanın sistem istemi edebi çeviri istemidir. Ücretsiz modeller şu sırayla denenir:

`big-pickle`, `nemotron-3-ultra-free`, `longcat-2.5-preview-free`, `mimo-v2.6-flash-free`,
`muse-spark-1.3-contributor-free`, `space-bunny-free`, `ling-3.0-flash-fin-free`,
`nemotron-3.5-lightning-free`, `ling-3.1-flash-free`, `fledge-alpha-free`

Gerçek çalıştırmada gördüklerimiz (2026-10-05, 11:08–14:48 TRT):

- Ücretsiz katmanda **IP başına kota** var. İlk beş model her biri yaklaşık 2 saniyede
  `Rate limit exceeded` döndürdü, epub-tr de `opencode/space-bunny-free`'ye geçti. Çevrilen ya da
  redaksiyondan geçen **her** parça bu modelden geldi (OpenCode'un oturum veritabanında doğrulandı).
  Özetteki `engine_models` alanı artık bunu kaydediyor.
- `space-bunny-free` yavaş: çağrı başına ortalama yaklaşık 290 saniye. Bazı çağrılar 600 saniyelik
  zaman aşımına takıldı, bazıları boş çıktı döndürdü (çıkış kodu 0). epub-tr artık boş çıktıda da model değiştiriyor.
- Paralel çalışan iki OpenCode işçisi ara sıra OpenCode'un kendi SQLite veritabanında
  `database is locked` hatası aldı. Yeniden deneme bunu çözüyor; sık görürseniz `--workers 1` kullanın.
- Kotalar birkaç saatte sıfırlanıyor. `scripts/opencode_when_available.sh` çalışan bir model bulana dek
  bekler, sonra taslak, redaksiyon ve iki dilli geçişleri çalıştırır.

Seçenekler: `-m opencode/<model>` ya da `EPUB_TR_OPENCODE_MODEL` ilk denenecek modeli seçer;
`EPUB_TR_OPENCODE_TIMEOUT` çağrı başına süreyi saniye cinsinden belirler (varsayılan 600).

## Diğer motorlar

| motor | tür | gerekenler | notlar |
|---|---|---|---|
| `ollama` | yerel LLM | çalışan [Ollama](https://ollama.com) ve indirilmiş bir model | `EPUB_TR_OLLAMA_MODEL`, `OLLAMA_HOST`, `EPUB_TR_OLLAMA_CTX`, `EPUB_TR_OLLAMA_MAX_TOKENS` |
| `google` | ücretsiz web uç noktaları | – | istek başına 4.500 karakter, 4 işçi |
| `bing`, `yandex`, `modernmt` | ücretsiz web çevirmenleri | `pip install translators` (GPL-3, isteğe bağlı) | istek başına 1.000 karakter |
| `mymemory` | REST API | – | anonim kullanımda IP başına günde yaklaşık 5.000 karakter; `MYMEMORY_EMAIL` ile 50.000 |
| `lingva` | Google ön yüzü | çalışan bir sunucu (`LINGVA_URL`) | herkese açık sunucular sık sık çöküyor |
| `libretranslate` | REST API | kendi sunucunuz (`LIBRETRANSLATE_URL`) ya da bir anahtar | |
| `argos` | çevrimdışı makine çevirisi | `pip install argostranslate` | en→tr modeli ilk kullanımda iner |
| `openrouter`, `gemini`, `groq`, `mistral`, `openai` | OpenAI uyumlu API'ler | `*_API_KEY` içinde ücretsiz katman anahtarı | model ve adres `EPUB_TR_<PRESET>_MODEL` ve `_BASE_URL` ile değiştirilebilir |
| `echo` | işlem yapmaz | – | yapı testleri için |

LLM motorları (`opencode`, `ollama`, API hazır ayarları) tüm edebi hattı kullanır: bağlam, sözlük, adlar
ve redaksiyon. Makine çevirisi motorları yer tutuculu parça grupları alır.
