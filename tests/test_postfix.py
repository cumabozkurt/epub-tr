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
