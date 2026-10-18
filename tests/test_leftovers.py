from epub_tr.leftovers import english_hits, is_english_leftover, strip_gutenberg_leftovers

X = b'<html xmlns="http://www.w3.org/1999/xhtml"><body>%s</body></html>'


def test_half_translated_prose_is_caught():
    assert is_english_leftover("In cevap to a soru by Başkan, he devam etti")
    assert is_english_leftover("it was the best of times dedi")


def test_names_and_citations_pass():
    assert english_hits("Her davanın bir Joan of Arc'ı vardır") == []
    assert english_hits("Chronicles of Robert of Gloucester okudum") == []
    assert english_hits("A History of the War kitabında") == []


def test_turkish_homographs_and_laughter_pass():
    assert not is_english_leftover("Yazdığım not her gün masadaydı")
    assert english_hits('"He he he!" diye güldü') == []


def test_strip_short_producer_note():
    raw = X % b"<p>David Price tarafindan kopyalanmistir, e-posta ccx074@pglaf.org</p><h1>BASLIK</h1>"
    out, n = strip_gutenberg_leftovers(raw)
    assert n == 1 and b"pglaf" not in out and b"BASLIK" in out


def test_strip_sentence_in_long_paragraph_keeps_rest():
    long = "Uzun bir paragraf cümlesi burada duruyor. " * 12
    raw = X % ("<p>%s Bu Gutenberg metni ilk baskıya dayanır. Son cümle kalır.</p>" % long).encode()
    out, n = strip_gutenberg_leftovers(raw)
    s = out.decode()
    assert n == 1 and "Gutenberg" not in s and "Son cümle kalır." in s and "Uzun bir paragraf" in s


def test_inventor_gutenberg_untouched():
    raw = X % "<p>Gutenberg hareketli harfleri icat etti.</p>".encode()
    out, n = strip_gutenberg_leftovers(raw)
    assert n == 0 and out == raw
