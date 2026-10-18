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
