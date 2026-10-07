# epub-tr test raporu: Türkçe özet

Ayrıntılı rapor (tüm örnekler ve günlükler): [TEST_REPORT.md](TEST_REPORT.md)

**Test kitabı:** O. Henry, *The Gift of the Magi* (Project Gutenberg #7256): 51 parça, 11.237 karakter.
Yapı denetimi için *The Yellow Wallpaper* (#1952, 273 parça) da Google ile çevrildi.
**Makine:** 8 vCPU, 16 GB RAM, GPU yok. Motorlar kısmen aynı anda çalıştı.

## Sonuçlar

| motor | sonuç | süre | not |
|---|---|---|---|
| **opencode `--polish`** (`opencode/space-bunny-free`) | 43/51 parça, 31'i redaksiyonlu; devam ettirmede 51/51 | 6.932 sn | **en iyi edebi Türkçe** |
| opencode (yalnızca taslak, aynı model) | 45/51 parça | 3.730 sn | çok iyi ama yazım hataları var: "srma", "uyacak", "Şapkanını" |
| bing | 51/51 | 42,8 sn | en doğal makine çevirisi |
| google | 51/51 | 1,7 sn | akıcı, deyimlerde birebir |
| yandex / modernmt | 51/51 | 17,6 / 16,0 sn | Google düzeyinde, daha çok kalıp çeviri |
| ollama aya-expanse:8b | ilk 16 parça | 221 sn | sayıları uyduruyor |
| ollama gemma3:4b (± redaksiyon) | 51/51 | 481 / 720 sn | sözcük uyduruyor |
| argos (çevrimdışı) | 51/51 | 820 sn | en zayıf |
| lingva, mymemory | ❌ | – | herkese açık sunucu hatası / günlük kota dolu |
| libretranslate, API hazır ayarları | ⏭ | – | anahtar ya da kendi sunucu gerekiyor |

**EPUBCheck 5.4.0:** Kaynak EPUB'da zaten 1 hata var (Gutenberg'in `toc.xhtml` içindeki `aria-label`'ı,
RSC-005). Üç OpenCode çıktısı dahil **tüm çıktılarda yalnızca bu devralınan hata var, yeni hata yok.**

## OpenCode çalıştırması (2026-10-05, 11:08–14:48 TRT)

- İstenen model `opencode/big-pickle` idi. İlk beş ücretsiz model IP kotasına takıldı (her biri yaklaşık
  2 sn), motor `opencode/space-bunny-free`'ye geçti. OpenCode oturum veritabanına göre tamamlanan **tüm**
  yanıtlar bu modelden geldi. v1.1.0'dan itibaren özetteki `engine_models` alanı gerçekten kullanılan modeli gösteriyor.
- Çağrı başına ortalama yaklaşık 290 sn sürdü; bazı çağrılar 600 sn zaman aşımına uğradı, bazıları boş
  döndü. v1.1.0'da boş yanıt veren modelden bir sonrakine geçiliyor.
- Model sözlüğe ters girdiler bildirdi (`Hediyenin Getirdiği Mutluluk => The Gift of the Magi`).
  v1.1.0'da yalnızca kaynak terimi metinde geçen girdiler kabul ediliyor.

## Kalite değerlendirmesi

1. **OpenCode + `--polish`**: çeviri gibi değil, düzeltilmiş Türkçe düzyazı gibi okunuyor ("Birer ikişer
   kuruş biriktirmek için bakkala, manava ve kasaba gözünü karartıyordu…"). Kusursuz değil: "yulakta",
   "bural bural" gibi hatalar var. Ücretsiz katmanda çok yavaş.
2. **OpenCode taslak**: aynı ölçüde deyimsel, ama redaksiyonun düzelttiği yazım hataları var.
3. **Bing**, 4. **Google**, 5. **Yandex ≈ ModernMT**, 6. **aya-expanse:8b**, 7. **gemma3:4b**, 8. **Argos**.

**Önerilen ayar:** `epub-tr translate kitap.epub --engine opencode --polish --fallback bing`. Ücretsiz
katmanda başarısız olan parçaları doldurmak için aynı komutu sonra yeniden çalıştırın; tamamlanmış her şey
önbellekten gelir. Hız için `--engine bing` ya da kurulumsuz `--engine google`. En iyi çıktı bile
yayımlanmadan önce insan redaksiyonu ister.
