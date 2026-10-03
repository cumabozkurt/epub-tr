# epub-tr test report (2026-10-03, TRT)

**Test book:** O. Henry, *The Gift of the Magi*, Project Gutenberg #7256 (EPUB3, `samples/pg7256.epub`):
51 translatable segments, 11,237 chars (the story, title, TOC/NCX labels; the Gutenberg header/licence
is skipped on purpose). For a second structural check, *The Yellow Wallpaper* (#1952, 273 segments)
went through Google as well.
**Box:** 8 vCPU, 16 GB RAM, no GPU. Several engines ran **at the same time**, so CPU-bound timings
(Argos, Ollama) are pessimistic.

## Results per engine

| Engine | Status | Scope | Time | Notes |
|---|---|---|---|---|
| **opencode** (all 10 Zen free models) | ❌ **blocked by quota** | – | – | Every free model returns HTTP 429 `FreeUsageLimitError` for this box's IP (`retry-after` ≈ 4.7 h at 22:17, so it resets around 03:00 TRT on Oct 4). longcat-2.5-preview-free returns 403 when called outside the CLI. The integration itself is working: agent config, `--format json` parsing (checked against opencode's `run.ts`), and fast rate-limit detection with switching across all models (about 11 s per model). Fixed a real bug along the way: opencode takes its project dir from `$PWD`, so the engine now sets `PWD` and `--dir`. `scripts/opencode_when_available.sh` is running in the background and will translate the full book (draft, then polish, then bilingual) once the quota comes back. |
| google (free endpoint) | ✅ | full book | **1.7 s** | Placeholder tags kept. deep-translator's endpoint was captcha-blocked from this IP, so the `clients5` endpoint was used. |
| bing (`translators`) | ✅ | full book | 42.8 s | most fluent MT |
| yandex (`translators`) | ✅ | full book | 17.6 s | |
| modernmt (`translators`) | ✅ | full book | 16.0 s | puts stray spaces before punctuation (`sevgilim ,`) |
| argos (offline) | ✅ | full book | 820 s (CPU contention) | weakest quality; plain text only (inline tags dropped, single-element TOC links re-wrapped) |
| ollama gemma3:4b | ✅ | full book | 481 s | 2 TOC placeholders dropped, then repaired by re-wrap and TOC harmonisation |
| ollama gemma3:4b + `--polish` | ✅ | full book | 720 s | 50 segments polished |
| ollama aya-expanse:8b | ✅ | first 16 segments (221 s); a full-book run was started afterwards | 221 s / 16 seg | |
| lingva (public) | ❌ | – | 147 s | lingva.ml returns HTTP 500, or the source untranslated (upstream Google blocks it); other instances are 404/403 |
| mymemory | ❌ | – | – | the anonymous daily quota for this IP was already used up ("NEXT AVAILABLE IN 13 HOURS"); setting `MYMEMORY_EMAIL` would help |
| libretranslate | ⏭ | – | – | libretranslate.com now needs an API key and the public mirrors are dead; works with a self-hosted server (`LIBRETRANSLATE_URL`) |
| openrouter / gemini / groq / mistral / openai | ⏭ | – | – | no API key in the environment (documented only) |
| fallback chain `lingva → google` | ✅ | full book | 35 s | lingva failed and all 51 segments were done by google |
| resume / cache | ✅ | – | 0.7 s | rerunning bing took 51/51 segments from the cache |

## EPUB validation (EPUBCheck 5.4.0)

The **source** EPUB already has 1 error: Gutenberg's `<nav aria-label=…>` in `toc.xhtml` (RSC-005).
**Every output EPUB, monolingual and bilingual, has exactly that one inherited error and nothing new.**
That holds for google, bing, yandex, modernmt, argos, gemma3, gemma3-polish, aya, the fallback run,
bing-bilingual, and Yellow Wallpaper (the source has 1 error, the output has 1).
Bugs found and fixed during testing:
* Bilingual nav created duplicate IDs. Nav is now translated in place.
* Tag-less engines (Argos) and LLMs that drop placeholders left TOC `<a>` elements empty. Single-element segments are now re-wrapped, and TOC labels are harmonised with the translated chapter headings.
* OpenCode `$PWD` bug.
* Ollama output is now capped (`num_predict`) because gemma once looped for more than 8 minutes.
* SQLite lock when several runs start at once.

Every output passes `ebooklib` re-reading. `dc:language` is set to `tr`, the title is translated, and the ZIP entry list is identical to the source (unit test).

## Sample comparisons

#### Segment 2:0

**Original (EN):** One dollar and eighty-seven cents. That was all. And sixty cents of it was in pennies. Pennies saved one and two at a time by bulldozing the grocer and the vegetable man and the butcher until one’s cheeks burned with the silent imputation of parsimony that such close dealing implied. Three times Della counted it. One dollar and eighty-seven cents. And the next day would be Christmas.

- **argos**: Bir bir dolar ve sekizi yedi sent. Hepsi buydu. Ve 60 senti pennies'teydi. Pennies bir ve iki kez marketi ve sebze adamını kırarak kurtardı ve ancak biri yanakları, bu kadar yakın bir şekilde ifade eden parsimony'nin sessiz engeli ile yakıldı. Üç kez Della bunu saydı. Bir dolar ve sekiz yedi sent. Ve ertesi gün Noel olacaktı.
- **bing**: Bir dolar seksen yedi cent. Hepsi bu kadar. Ve bunun altmış centi bozuk paraydı. Bozuk paralar, marketçiyle, sebzeciyle ve kasapla pazarlık yaparken yanakları, böylesine sıkı hesap yapmanın ima ettiği sessiz tutumluluk suçlamasıyla yanana kadar birer birer ve ikişer ikişer biriktirilmişti. Della bunu üç kez saydı. Bir dolar seksen yedi cent. Ve ertesi gün Noel olacaktı.
- **google**: Bir dolar seksen yedi sent. Hepsi bu kadar. Ve bunun altmış senti peni cinsindendi. Pennies, bakkal, manav ve kasap gibi yakın ilişkilerin ima ettiği sessiz cimrilik suçlamasıyla yanakları yanana kadar buldozerlerle ezerek birer birer ve iki kişiyi kurtardı. Della bunu üç kez saydı. Bir dolar seksen yedi sent. Ve ertesi gün Noel olacaktı.
- **modernmt**: Bir dolar seksen yedi sent. Hepsi bu kadardı. Altmış senti de bozuk paraydı. Bozuk paralar, bu kadar yakın anlaşmanın ima ettiği sessiz cimrilik suçlamasıyla birinin yanakları yanana kadar bakkalı, sebze adamını ve kasabı buldozerle yıkayarak birer birer ve ikiyi kurtardı. Della üç kez saydı. Bir dolar seksen yedi sent. Ve ertesi gün Noel olacaktı.
- **ollama-aya**: Bir dolar ve otuz yedi sent. İşte hepsi bu. On altı senti de kuruşlarda. Kuruşlar, marketçiyi, sebze satıcısını ve kasapları ezerken bir kişinin yanakları parsimlilik suçlamasıyla yanarak bir zaman bir iki kuruş tasarruf etti. Della üç kez bunu saydı. Bir dolar ve otuz yedi sent. Ve ertesi gün Noel olacaktı.
- **ollama-gemma3-polish**: Bir dolar seksen yedi sentti. İşte bütün melekse o kadar. Ve bu melekse’nin elli altı santimi para baytasıydı. Baytaları, kasabayı, sebze adamını ve etçiyi ezerek, yüzlerimizden sessizce cimrilik ima eden yakın sözleşmelerin getirdiği gibi, birer birer birleştirilmişti. Della üç kez saydı. Bir dolar seksen yedi sentti. Ve ertesi gün Noel’i olacaktı.
- **ollama-gemma3**: Bir dolar seksen yedi kuruş. İşte o kadar. Ve on buçuk kuruşu da altındanlardı. Zincirleme bir şekilde, kasabeyi, sebze satıcısını ve etçiyi, yüzlerimizi paranın hiddetiyle yakarak, böyle yakın bir ticaretin ima ettiği cimrilik ile... Üç defa Della saydı. Bir dolar seksen yedi kuruş. Ve ertesi gün Noel’di.
- **yandex**: Bir dolar seksen yedi sent. Hepsi bu kadardı. Ve bunun altmış senti kuruştu. Pennies, bakkalı, sebzeciyi ve kasabı buldozerle bu kadar yakın anlaşmanın ima ettiği sessiz cimrilik iddiasıyla yanakları yanana kadar birer ikişer kurtardı. Della üç kez saydı. Bir dolar seksen yedi sent. Ve ertesi gün Noel olacaktı.

#### Segment 2:13

**Original (EN):** “I buy hair,” said Madame. “Take yer hat off and let’s have a sight at the looks of it.”

- **argos**: “ Saç satın alıyorum,” dedi Madam. “Köpekten çıkıp bir görüşe sahip olalım.”
- **bing**: “Saç alırım,” dedi Madame. “Şapkanı çıkar ve nasıl göründüğüne bir bakalım.”
- **google**: "Saç satın alıyorum" dedi Madam. "Şapkanı çıkar ve şuna bir bakalım."
- **modernmt**: “Saç satın alıyorum ,” dedi Madam. "Şapkanı çıkar ve görünüşüne bir bakalım ."
- **ollama-aya**: “Saç satın alırım,” dedi Bayan. “Şapkanı çıkar ve saçlarının halini görelim.”
- **ollama-gemma3-polish**: “Saç alırım,” dedi Madame. “Şapkanızı çıkarın ve bakalım nasıl bir duruşu var?”
- **ollama-gemma3**: “Saçı alırım,” dedi Madame. “Şaptonu çıkar ve halının görünüşüne bakalım.”
- **yandex**: ”Saç alıyorum," dedi Madam. "Şapkanı çıkar ve ona bir göz atalım.”

#### Segment 2:27

**Original (EN):** “Jim, darling,” she cried, “don’t look at me that way. I had my hair cut off and sold because I couldn’t have lived through Christmas without giving you a present. It’ll grow out again—you won’t mind, will you? I just had to do it. My hair grows awfully fast. Say ‘Merry Christmas!’ Jim, and let’s be happy. You don’t know what a nice—what a beautiful, nice gift I’ve got for you.”

- **argos**: “Jim, sevgilim,” diye bağırdı, “Bana bu şekilde bakmıyor. Saçımı kestim ve sattım çünkü size bir hediye vermeden Noel'de yaşayamadım. Tekrar büyüyecek - aklınızda olmayacak mısın? Sadece bunu yapmak zorunda kaldım. Saçlarım korkunç bir şekilde hızlı büyür. De ki: "Ey Noel! Jim, ve mutlu olalım. Ne güzel olduğunu bilmiyorsunuz – sizin için sahip olduğum güzel, güzel bir hediye.”
- **bing**: “Jim, tatlım,” diye ağladı, “bana öyle bakma. Saçımı kestirdim ve sattım çünkü sana bir hediye vermeden Noel’i geçiremezdim. Tekrar uzar—umursamazsın, değil mi? Bunu yapmak zorundaydım. Saçım inanılmaz hızlı uzar. ‘Mutlu Noeller!’ de Jim, ve mutlu olalım. Ne kadar hoş—ne kadar güzel, hoş bir hediyem olduğunu bilmiyorsun.”
- **google**: "Jim, tatlım," diye bağırdı, "bana öyle bakma. Saçımı kestim ve sattım çünkü sana bir hediye vermeden Noel'i atlatamazdım. Tekrar uzayacak, aldırmazsın, değil mi? Bunu yapmak zorundaydım. Saçlarım çok hızlı uzuyor. 'Mutlu Noeller!' de Jim ve hadi mutlu olalım. Sana ne kadar güzel, ne güzel, ne hoş bir hediye aldığımı bilemezsin."
- **modernmt**: "Jim, sevgilim ," diye bağırdı," bana öyle bakma. Saçımı kestirdim ve sattım çünkü sana bir hediye vermeden Noel'i atlatamazdım. Tekrar uzayacak - aldırmazsın, değil mi? Sadece bunu yapmak zorundaydım. Saçlarım çok hızlı uzuyor. ‘Mutlu Noeller !' de Jim, hadi mutlu olalım. Sana ne kadar güzel, ne kadar güzel bir hediyem olduğunu bilmiyorsun ."
- **ollama-gemma3-polish**: “Jim, canım,” diye bağırdı, “ona öyle bakma. Saçımı kestirdim ve sattım çünkü Noel’i hiç yaşayamazdım eğer sana bir hediye vermezsem. Yeniden uzar—sana biraz rahatsızlık olmaz mı? Sadece yapmam gerekiyordu. Saçım çok hızlı uzuyor. ‘Mutlu Noeller!’ Jim, ve mutlu olalım. Ne kadar güzel—ne kadar güzel bir hediye aldığımı bilmezsin,” dedi.
- **ollama-gemma3**: “Jim, canım,” diye bağırdı, “bana böyle bakma. Saçımı kestirdim ve sana Noel’i atlamamak için bir hediye vermeden yaşayamayacaktım diye sattım. Tekrar uzar—sıkılmaz mısın? Sadece yapmam gerekiyordu. Saçım çok hızlı büyüyor. ‘Mutlu Noeller!’ de, Jim, ve mutlu olalım. Seni ne kadar güzel—ne kadar güzel bir hediye aldığımı bilmezsin,”
- **yandex**: "Jim, sevgilim,” diye bağırdı, “bana öyle bakma. Sana bir hediye vermeden Noel'i yaşayamayacağım için saçımı kestirip sattırdım. Tekrar büyüyecek - sakıncası olmayacak, değil mi? Sadece yapmak zorundaydım. Saçlarım çok hızlı uzuyor. Mutlu Noeller de! Jim ve mutlu olalım. Senin için ne kadar güzel, ne kadar güzel bir hediyem olduğunu bilmiyorsun.”

#### Segment 2:44

**Original (EN):** The magi, as you know, were wise men—wonderfully wise men—who brought gifts to the Babe in the manger. They invented the art of giving Christmas presents. Being wise, their gifts were no doubt wise ones, possibly bearing the privilege of exchange in case of duplication. And here I have lamely related to you the uneventful chronicle of two foolish children in a flat who most unwisely sacrificed for each other the greatest treasures of their house. But in a last word to the wise of these days let it be said that of all who give gifts these two were the wisest. Of all who give and receive gifts, such as they are wisest. Everywhere they are wisest. They are the magi.

- **argos**: Bildiğiniz gibi magi, bilge erkeklerdi - inanılmaz derecede bilge erkekler - erkekte Babe'ye hediyeler getiren. Noel hediyelerini vermenin sanatını icat ettiler. Bilge olmak, hediyeleri şüphesiz bilge değildi, muhtemelen duplikasyon durumunda değişim ayrıcalıklarını taşıyan. Ve işte size, evin en büyük hazineleri için en doğru şekilde kurban edilen bir dairedeki iki aptal çocuğun eşitsiz kronikiyle ilgili oldum. Ancak bu günlerden bilgeye son bir kelimede, bu ikisine hediye veren herkesin bilge olduğu söylenmelidir. Kim verir ve hediyeler alırlar, onlar bilgedir. Her yerde bilgedirler. Onlar magi’dir.
- **bing**: Bildiğiniz gibi, büyücüler (Magi), bilge insanlardı—olağanüstü bilge insanlardı—ve beşiğin içindeki Bebek'e hediyeler getirdiler. Noel hediyesi verme sanatını icat ettiler. Bilge olduklarından, hediyeleri kuşkusuz bilge hediyelerdi, muhtemelen çoğaltıldığında değiştirme ayrıcalığını taşıyan. Ve işte burada size, birbirlerine evlerindeki en büyük hazineleri en akılsızca feda eden, iki aptal çocuğun olaysız kroniğini berbat bir şekilde aktardım. Ama bugünün bilge insanlarına son bir söz olarak şunu söyleyelim ki, hediye verenlerin hepsi arasında bu ikisi en bilgeliydi. Hediye veren ve alanların hepsi arasında, onlar en bilgeliydi. Heryerde en bilgeliydiler. Onlar büyücülerdi (Magi).
- **google**: Bildiğiniz gibi büyücüler, yemlikteki Bebek'e hediyeler getiren bilge adamlardı - olağanüstü bilge adamlardı. Noel hediyesi verme sanatını icat ettiler. Bilge olduklarına göre, onların armağanları şüphesiz akıllıcaydı ve muhtemelen kopyalanması durumunda takas ayrıcalığını taşıyordu. Ve burada size, bir apartman dairesinde evlerinin en büyük hazinelerini birbirleri için son derece akılsızca feda eden iki aptal çocuğun olaysız öyküsünü yetersiz bir şekilde anlattım. Ama günümüzün bilgelerine son söz olarak şunu söyleyelim ki, hediye verenler arasında en bilge olanlar bu ikisiydi. Hediye veren ve alan herkes arasında en bilge olanlar onlar gibi. Her yerde onlar en bilgedir. Onlar büyücüler.
- **modernmt**: Bildiğiniz gibi büyücüler, yemlikteki Babe'e hediyeler getiren bilge adamlardı - son derece bilge adamlardı. Noel hediyesi verme sanatını icat ettiler. Bilge oldukları için, hediyeleri şüphesiz bilge olanlardı, muhtemelen kopyalama durumunda değiş tokuş ayrıcalığını taşıyorlardı. Ve burada, evlerinin en büyük hazinelerini birbirleri için en akılsızca feda eden bir apartman dairesindeki iki aptal çocuğun olaysız tarihini size acınası bir şekilde anlattım. Ancak bu günlerin bilgesine son bir söz olarak, bu ikisinin hediye verenlerin en bilgesi olduğu söylenmelidir. En bilge oldukları gibi hediye veren ve alan herkes arasında. En bilge oldukları her yerde. Onlar büyücülerdir.
- **ollama-gemma3-polish**: Magi’yi, sizler de bildiğiniz gibi, doğuşun ilk anlarında ona hediyeler getirmiş olan bilge kişilerdi—inanılmaz derecede bilge kişiler—ve hediye vermenin sanatını icat ettiler. Bilgeleri olmaları sebebiyle, hedeflerinden şüphe yok ki de çok da akıllıydılar; belki de takas etme ayrıcalığına sahip olabilirler. Ve şimdi size, lam selamla anlatacağım evlerinin en değerli hazinelerini birbirlerine feda eden iki aptal çocuğun sıradan ve sıkıcı öyküsü bu. Fakat günümüzün bilge insanlarına son söz olarak belirtmek gerekirse, hediye verenlerden en bilgeli olan ikisi buydu. Hediye veren ve alanlardan, onlara benzer şekilde en bilgiliydiler. Her yerde onlar en bilgilidirler; onlar, magi’dir.
- **ollama-gemma3**: Mageus’un, yani sizler de bildiğiniz üzere, nasıl bilge adamlar olduğunu, Doğuşan Mesih’e mahzende hediyeler getiren o kadar da bilge adamlar olduklarını hatırlatmak isterim. Hediye vermenin sanatını onlar icat ettiler. Bilgeleri sayesinde hediye-leri elbette de bilgece olurdu, belki de taklit durumunda değişim keyfi taşırlardı. Ve şimdi size, iki aptal çocuğun düzgün bir evde, en ahmakça şekilde birbirlerine evlerinin en değerli hazinelerini feda ettikleri sıradan ve olaydan uzak tarihçesini zayıf bir dille anlattım. Fakat günümüzün bilge adamlarına son söz olarak şunu belirtmek gerek ki, hediye verenlerden en bilgeli olan ikisi budur. Hediye veren ve alanlardan, onlardan daha bilgiliydiler. Her yerde onlar daha bilgilidirler. Onlar, Mageus’lardır.
- **yandex**: Magi, bildiğiniz gibi, yemlikteki Bebeğe hediyeler getiren bilge adamlardı — harika bilge adamlardı —. Noel hediyeleri verme sanatını icat ettiler. Bilge oldukları için, hediyeleri şüphesiz bilge olanlardı, muhtemelen çoğaltma durumunda değiş tokuş ayrıcalığını taşıyorlardı. Ve burada size, evlerinin en büyük hazinelerini birbirleri için en akılsızca feda eden bir apartmandaki iki aptal çocuğun olaysız hikayesini anlattım. Ama bu günlerin bilgesine son bir sözle, hediye verenlerin hepsinin en bilge oldukları söylensin. Hediye veren ve alan herkesten, en bilge oldukları gibi. Her yerde en akıllılar. Onlar büyücülerdir.


## Honest quality judgement

Ranking for **literary Turkish** on this text (OpenCode could not be evaluated):

1. **Bing**: clearly the most natural and accurate. It gets the hard sentence right ("marketçiyle, sebzeciyle ve kasapla pazarlık yaparken… sessiz tutumluluk suçlaması"), renders "pennies" as "bozuk para", and keeps Turkish dialogue punctuation and em dashes. Weak points: it keeps "cent", renders "she cried" as "diye ağladı" (wrong here; she exclaimed, she did not weep), and has small slips ("Heryerde", "en bilgeliydi").
2. **Google**: fluent and very fast, but literal on the idioms ("buldozerlerle ezerek… iki kişiyi kurtardı", "Pennies" left untranslated) and it switches to straight quotes.
3. **Yandex ≈ ModernMT**: comparable to Google with more calques ("buldozerle", "Büyücünün Armağanı"). ModernMT adds spacing errors around punctuation.
4. **Ollama aya-expanse:8b**: idiomatic Turkish phrasing, but it hallucinates numbers ("otuz yedi sent", "On altı senti").
5. **Ollama gemma3:4b (with or without polish)**: some nice literary touches ("Jim, canım"), but too many invented words ("melekse", "para baytası", "Şaptonu", "Mageus"). The polish pass makes it smoother but does not fix factual errors. A 4B model is too small for this job.
6. **Argos**: literal and often ungrammatical ("Bir bir dolar ve sekizi yedi sent", "Köpekten çıkıp…").

**Best engine actually tested: Bing** (`--engine bing`), with Google as a fast fallback.
`--engine opencode --polish --fallback bing` is the intended top-quality setup: a large LLM with context, a glossary, and the literary prompt. It could not be measured today because of the per-IP free quota. Rerun after the reset, or let the background script do it; results will land in `out/magi.opencode*.epub` and `out/logs/opencode-comparison.md`.
Even the best machine output above still needs human editing to read as published literary Turkish.
