from epub_tr import postfix as P
from epub_tr.titles import tidy

XH = '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>pg_iSYMBOLIC</title></head><body>{}</body></html>'


def test_roman_numerals_restored():
    for bad, good in [("BEN. Philip'in Ölümü", "I. Philip'in Ölümü"), ("KİTAP İ.", "KİTAP I."), ("Kitap İİ", "Kitap II"),
                      ("Şek. BEN.", "Şek. I."), ("Bölüm Vİ", "Bölüm VI"), ("İİİ. Bir", "III. Bir")]:
        assert P.fix_roman(bad)[0] == good


def test_roman_leaves_turkish_words():
    for s in ["Ben. değil", "İstanbul. İ.", "BEN geldim", "Kitap İstanbul"]:
        assert P.fix_roman(s)[0] == s


def test_page_markers_removed():
    assert P.fix_pg("pg_xhangi yol")[0] == "hangi yol"
    assert P.fix_pg("pg_iSYMBOLIC")[0] == "SYMBOLIC"
    assert P.fix_pg("bkz. pg075 ve")[0].split() == ["bkz.", "ve"]
    b = XH.format('<p><a id="pg_i"><span class="marginal">pg_ii</span></a>Metin</p>').encode()
    out, st = P.process(b)
    assert b"pg_ii<" not in out and b"pg_iSYMBOLIC" not in out and b'id="pg_i"' in out


def test_inner_title_uses_verified_title():
    b = XH.format('<h1 id="pgepubid00000">MONTE KRISTO KONUSU</h1><h2>Yazan: Dumas</h2>').encode()
    out, st = P.process(b, title="Monte Kristo Kontu", first=True)
    assert "MONTE KRİSTO KONTU".encode() in out and st["title"] == 1
    out, st = P.process(b, title="Monte Kristo Kontu", first=False)
    assert st["title"] == 0


def test_front_english_detected():
    b = XH.format('<p>Butler &amp; Tanner,<br/> Selwood Printing Works,<br/> Frome ve Londra.</p><h2>ÖNSÖZ</h2>').encode()
    assert any("Printing Works" in h for h in P.front_english(b)[1])


def test_title_case():
    assert tidy("Güç istenci - Kitap 1") == "Güç İstenci - Kitap 1"
    assert tidy("Savaş ve barış") == "Savaş ve Barış"
    assert tidy("Le Morte d'Arthur") == "Le Morte d'Arthur"


def test_protect_names_restores_exonyms_with_suffix_harmony():
    assert P.protect_names("Öncü İbrahim'in ölümü.", {"Abraham"})[0] == "Öncü Abraham'ın ölümü."
    assert P.protect_names("İBRAHİM LINCOLN BÖLÜM I", {"Abraham", "Lincoln"})[0] == "ABRAHAM LINCOLN BÖLÜM I"
    assert P.protect_names("Musa'nın asası, Musa'ya", {"Moses"})[0] == "Moses'in asası, Moses'e"
    assert P.protect_names("Meryem'in", {"Mary"})[0] == "Mary'nin"
    # only names that come from the title/author are touched; longer words are left alone
    assert P.protect_names("Musa ve İbrahimoğlu", {"Abraham"})[0] == "Musa ve İbrahimoğlu"


def test_protect_names_word_forms_only_after_a_name():
    s, n = P.protect_names("Agnes Gri'nin annesi, gri gökyüzü. Bayan Gri geldi. Gri kedi.", {"Agnes"}, {"Gri": "Grey"})
    assert s == "Agnes Grey'in annesi, gri gökyüzü. Bayan Grey geldi. Gri kedi." and n == 2
    assert P.protect_names("RODNEY TAŞ'IN ANILARI", {"Rodney"}, {"Taş": "Stone"})[0] == "RODNEY STONE'UN ANILARI"


OPF = """<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/"
 version="3.0" xml:lang="en"><metadata><dc:title>Kitap</dc:title><dc:subject>Sisters -- Fiction</dc:subject>
<dc:rights>Public domain in the USA.</dc:rights></metadata><manifest>
<item id="nav" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
<item id="c0" href="c0.xhtml" media-type="application/xhtml+xml"/>
<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="c0"/><itemref idref="c1"/></spine></package>"""
NAV = """<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Abraham Lincoln: a History</title><meta name="dtb:generator" content="Ebookmaker by Project Gutenberg"/></head>
<body><nav epub:type="toc" aria-label="Table of Contents"><ol>
<li><a href="c0.xhtml#pgepubid00000">Old English Title</a></li><li><a href="c1.xhtml#ch1">Chapter One</a></li>
<li><a href="c1.xhtml#ch2">Bölüm 2</a></li></ol></nav></body></html>"""
NCX = """<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="en">
<head/><docTitle><text>Abraham Lincoln: a History</text></docTitle><navMap>
<navPoint id="n1"><navLabel><text>Chapter One</text></navLabel><content src="c1.xhtml#ch1"/></navPoint></navMap></ncx>"""
C0 = XH.replace("pg_iSYMBOLIC", "The Project Gutenberg eBook of Abraham Lincoln").format(
    '<h1 id="pgepubid00000">ESKİ BAŞLIK</h1>')
C1 = XH.replace("pg_iSYMBOLIC", "Chapter One").format(
    '<h2 id="ch1">BİRİNCİ BÖLÜM<br/>İbrahim\'in Çocukluğu</h2><p>Genç İbrahim okudu.</p><h2 id="ch2">Bölüm 2</h2>')


def test_meta_fix_turkish_titles_toc_and_names():
    files = {"content.opf": OPF.encode(), "toc.xhtml": NAV.encode(), "toc.ncx": NCX.encode(),
             "c0.xhtml": C0.encode(), "c1.xhtml": C1.encode()}
    out, st = P.meta_fix(files, "Abraham Lincoln - Cilt 1", {"Abraham", "Lincoln"}, None, "c0.xhtml")
    nav, ncx = out["toc.xhtml"].decode(), out["toc.ncx"].decode()
    c0, c1, opf = out["c0.xhtml"].decode(), out["c1.xhtml"].decode(), out["content.opf"].decode()
    assert "<title>Abraham Lincoln - Cilt 1</title>" in nav and "Gutenberg" not in nav
    assert 'aria-label="İçindekiler"' in nav
    assert "BİRİNCİ BÖLÜM Abraham'ın Çocukluğu" in nav and "Chapter One" not in nav
    assert "Bölüm 2" in nav and ">ABRAHAM LİNCOLN - CİLT 1<" in nav
    assert "<text>Abraham Lincoln - Cilt 1</text>" in ncx and 'xml:lang="tr"' in ncx
    assert "Chapter One" not in ncx
    assert "Gutenberg" not in c0 and "<title>Abraham Lincoln - Cilt 1</title>" in c1
    assert "Genç Abraham okudu" in c1 and st["names"] == 2 and st["inner"] == 1
    assert "Sisters" not in opf and "Kamu malı" in opf and 'xml:lang="tr"' in opf


def test_meta_fix_keeps_turkish_labels_and_colophon_titles():
    kunye = XH.replace("pg_iSYMBOLIC", "Künye").format("<h1>Kitap</h1>")
    nav = NAV.replace("Old English Title", "Önsöz").replace("Chapter One", "BİRİNCİ BÖLÜM İbrahim'in Çocukluğu")
    files = {"content.opf": OPF.encode(), "toc.xhtml": nav.encode(), "c0.xhtml": C0.encode(),
             "c1.xhtml": C1.encode(), "kunye.xhtml": kunye.encode()}
    out, st = P.meta_fix(files, "Kitap", None, None, None)
    assert "kunye.xhtml" not in out
    n = out["toc.xhtml"].decode()
    assert "BİRİNCİ BÖLÜM İbrahim'in Çocukluğu" in n and st["labels"] == 1   # only the stale "Önsöz" entry


def test_meta_fix_keeps_richer_stale_label():
    nav = NAV.replace("Chapter One", 'I. BÖLÜM "Her Yerde Kahramanlık Var"')
    files = {"content.opf": OPF.encode(), "toc.xhtml": nav.encode(), "c0.xhtml": C0.encode(),
             "c1.xhtml": C1.replace("BİRİNCİ BÖLÜM<br/>İbrahim'in Çocukluğu", "BÖLÜM I").encode()}
    out, st = P.meta_fix(files, "Kitap", None, None, None)
    assert 'I. BÖLÜM "Her Yerde Kahramanlık Var"' in out["toc.xhtml"].decode()


def test_fix_gay_tr_suffixes():
    from epub_tr.postfix import fix_gay_tr
    s, n = fix_gay_tr("Eşcinsel bir kış; eşcinselliği, eşcinseldi, eşcinselce güldü, EŞCİNSEL")
    assert s == "Neşeli bir kış; şenliği, şendi, neşeyle güldü, NEŞELİ" and n == 5


def test_old_sense_source_mapping():
    from epub_tr.textfix import old_sense
    assert old_sense("She was gay and gaily danced; the gaiety of John Gay.") == \
        "She was merry and merrily danced; the merriment of John Gay."
    assert old_sense("Gay was the night. Mr. Gay came.") == "Merry was the night. Mr. Gay came."


def test_strip_pg_keeps_printer_and_drops_license():
    from lxml import etree

    from epub_tr.postfix import strip_pg
    x = ('<html xmlns="http://www.w3.org/1999/xhtml"><head><meta name="DC.Publisher" content="Project Gutenberg"/>'
         '</head><body><p>Bu, Mainz\'da doğan John Gutenberg\'di.</p>'
         '<p>Bu e-kitap Gutenberg Projesi lisansı altında dağıtılır.</p><p>Bağış için www.example.org.</p>'
         '<p>Başka bir <a href="https://www.gutenberg.org/ebooks/1">cilt</a> var.</p>'
         '<h2>Tam Proje Gutenberg Lisansı</h2><p>Madde 1</p><p>Madde 2</p></body></html>')
    t = etree.fromstring(x.encode())
    strip_pg(t)
    txt = "".join(t.itertext())
    assert "John Gutenberg" in txt and "Madde" not in txt and "Bağış" not in txt and "lisansı" not in txt
    assert not t.xpath("//*[local-name()='meta']")


def test_strip_pg_keeps_blocks_that_only_link_to_gutenberg():
    from lxml import etree

    from epub_tr.postfix import strip_pg
    x = ('<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Dizin</p>'
         '<p>Abraham, <a href="https://www.gutenberg.org/files/1/1-h.htm#p12">12</a>, 40</p>'
         '<p>Agnes, 7</p></body></html>')
    t = etree.fromstring(x.encode())
    assert strip_pg(t) == 0
    assert "Abraham, 12, 40" in "".join(t.itertext()) and not t.xpath("//*[@href]")


def _body(x):
    from lxml import etree
    return etree.fromstring(('<html xmlns="http://www.w3.org/1999/xhtml"><body>' + x + '</body></html>').encode())


def test_strip_pg_cuts_only_the_pg_sentence_of_long_blocks():
    from epub_tr.postfix import strip_pg
    t = _body("<pre>" + "Uzun satır metni burada. " * 40 + "Projenin Sonu Gutenberg'in Krizi, Cilt 2, Winston Churchill\n</pre>"
              "<p>Kapı açıldı. Projenin Sonu Gutenberg'in Anne Adayı, J. M. Barrie</p>"
              "<p>Yaklaşık 1450'de Gutenberg'le başlayan baskı.</p>")
    assert strip_pg(t) == 2
    txt = "".join(t.itertext())
    assert txt.count("Uzun satır metni burada.") == 40 and "Kapı açıldı." in txt and "Barrie" not in txt
    assert "Krizi" not in txt and "1450'de Gutenberg'le" in txt


def test_strip_pg_mt_end_lines():
    from epub_tr.postfix import strip_pg
    t = _body("<p>Kitap bitti.</p><h5>SON</h5><p>Gutenberg'in Boy Çiftçiler adlı eserinin sonu, Will Adams</p>"
              "<p>Mark Twain'in Gutenberg Çalışmalarının Tamamı</p><p>[1] Bu Gutenberg e-Metnindeki bölüm eksik.</p>"
              "<p>Johann Wolfgang von Goethe'nin yazdığı Gutenberg Otobiyografisi Projesinin Sonu</p>"
              "<p>John Gutenberg matbaayı buldu.</p>")
    strip_pg(t)
    txt = "".join(t.itertext())
    assert "Kitap bitti." in txt and "John Gutenberg matbaayı buldu." in txt
    assert txt.count("Gutenberg") == 1


def test_meta_fix_drops_license_toc_entry_with_empty_sublist_and_titles_bare_the():
    nav = NAV.replace("Old English Title", "THE").replace(
        '<li><a href="c1.xhtml#ch2">Bölüm 2</a></li>',
        '<li><a href="c1.xhtml#ch2">Bölüm 2</a></li><li><a href="c1.xhtml#lic">Tam Proje Gutenberg Lisansı</a><ol></ol></li>')
    c0 = C0.replace("ESKİ BAŞLIK", "THE")
    files = {"content.opf": OPF.encode(), "toc.xhtml": nav.encode(), "c0.xhtml": c0.encode(), "c1.xhtml": C1.encode()}
    out, st = P.meta_fix(files, "Goethe'nin Otobiyografisi", None, None, None)
    n = out["toc.xhtml"].decode()
    assert "Lisans" not in n and st["toc_pg"] == 1
    assert ">Goethe'nin Otobiyografisi</a>" in n and ">THE<" not in n


def test_gayalign_uses_the_aligned_source(tmp_path):
    import json

    from epub_tr import gayalign as G
    dump = tmp_path / "d.jsonl"
    rows = [("They were gay and happy all the long day.", "Bütün gün boyunca eşcinsel ve mutluydular hep."),
            ("“Is this Mr. Bloomer queer also?” she asked him.", "“Bu Bay Bloomer da eşcinsel mi?” diye sordu ona."),
            ("He studied homosexual behaviour in old age.", "Yaşlılıkta eşcinsel davranışları inceledi uzun süre."),
            ("And she was queer, they all said to me.", "Ve o eşcinseldi, hepsi bana söyledi yine.")]
    dump.write_text("\n".join(json.dumps({"source": s, "translation": t}, ensure_ascii=False) for s, t in rows))
    x = ('<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Bütün gün boyunca eşcinsel ve mutluydular hep.</p>'
         '<p>“Bu Bay Bloomer da eşcinsel mi?” diye sordu ona.</p><p>Yaşlılıkta eşcinsel davranışları inceledi uzun süre.</p>'
         '<p>Ve o şendi, hepsi bana söyledi yine.</p></body></html>')
    out, st = G.fix_files({"c.xhtml": x.encode()}, str(dump), undo=True)
    s = out["c.xhtml"].decode()
    assert "boyunca neşeli ve" in s and "Bloomer da tuhaf mi" in s and "eşcinsel davranışları" in s
    assert "Ve o tuhaftı," in s and st == {"gay": 1, "queer": 1, "undo": 1, "left": 1}
