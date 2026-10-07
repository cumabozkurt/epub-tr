"""EPUB reading (segment collection) and ZIP-level writing (epub_tr.epub_io)."""
import zipfile

from conftest import CH1, MAGI, NCX, OPF3, make_epub
from lxml import etree

from epub_tr.epub_io import Book

DC = "{http://purl.org/dc/elements/1.1/}"


def segs_by_doc(book):
    return {d.zip_path: [s.enc.plain() for s in d.segments] for d in book.documents}


def test_metadata_and_documents(epub_path):
    with Book(epub_path) as b:
        assert (b.title, b.creator, b.language) == ("The Clockmaker", "Jane Doe", "en")
        assert b.opf_path == "OEBPS/content.opf" and b.ncx_path == "OEBPS/toc.ncx"
        paths = [d.zip_path for d in b.documents]
        assert paths[:2] == ["OEBPS/ch1.xhtml", "OEBPS/ch2.xhtml"]  # spine order first
        assert "OEBPS/nav.xhtml" in paths and next(d for d in b.documents if d.zip_path.endswith("nav.xhtml")).is_nav


def test_segment_collection_rules(epub_path):
    with Book(epub_path) as b:
        ch1 = segs_by_doc(b)["OEBPS/ch1.xhtml"]
    assert ch1 == [
        "Chapter One",
        "Della counted the coins three times. It was all she had.",
        "Della looked at Jim1 and smiled.",
        "Inside a div.", "Second in div.",
        "First item", "Second item",
        "A footnote by Jim.",
    ]
    # skipped: Gutenberg header, .notranslate, translate="no", <pre>, digits-only, <script>


def test_segment_kinds_and_uids(epub_path):
    with Book(epub_path) as b:
        ch1 = b.documents[0].segments
        assert ch1[0].kind == "heading" and ch1[1].kind == "text"
        assert len({s.uid for s in b.all_segments()}) == len(b.all_segments())
        nav = next(d for d in b.documents if d.is_nav)
        assert [s.enc.text for s in nav.segments] == ["<g1>Chapter One</g1>", "<g1>Chapter Two</g1>"]
        assert [s.enc.plain() for s in b.ncx_segments] == ["Chapter One", "Chapter Two"]  # docTitle excluded


def test_keep_boilerplate_and_no_toc(epub_path):
    with Book(epub_path, skip_gutenberg=False, translate_toc=False) as b:
        assert "The Project Gutenberg eBook of something." in segs_by_doc(b)["OEBPS/ch1.xhtml"]
        assert b.ncx_segments == [] and all(not d.segments for d in b.documents if d.is_nav)


def translate_all(book, fn=lambda s: s.source.upper()):
    for s in book.all_segments():
        s.translation = fn(s)


def test_write_monolingual(tmp_path, epub_path):
    out = tmp_path / "out.epub"
    with Book(epub_path) as b:
        translate_all(b)
        stats = b.apply(target_lang="tr")
        b.write(str(out), target_lang="tr", title="Saatçi")
    with Book(epub_path) as fresh:
        n = len(fresh.all_segments())
    assert stats["applied"] == n and stats["lenient"] == 0
    zin, zout = zipfile.ZipFile(epub_path), zipfile.ZipFile(out)
    assert zout.namelist() == zin.namelist()
    first = zout.infolist()[0]
    assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
    for untouched in ("OEBPS/style.css", "OEBPS/pic.png", "META-INF/container.xml"):
        assert zout.read(untouched) == zin.read(untouched)
    opf = etree.fromstring(zout.read("OEBPS/content.opf"))
    assert opf.find(f".//{DC}language").text == "tr"
    assert opf.find(f".//{DC}title").text == "Saatçi"
    assert any("epub-tr" in (c.text or "") for c in opf.iter(f"{DC}contributor"))
    ch1 = zout.read("OEBPS/ch1.xhtml").decode()
    assert "DELLA COUNTED THE COINS <i>THREE</i> TIMES.<br/>IT WAS ALL SHE HAD." in ch1
    assert 'id="r1"' in ch1 and 'href="#fn1"' in ch1 and 'lang="tr"' in ch1
    assert "Do not translate me." in ch1 and "code block stays" in ch1 and "The Project Gutenberg" in ch1
    assert "CHAPTER ONE" in zout.read("OEBPS/toc.ncx").decode()
    assert "CHAPTER TWO" in zout.read("OEBPS/nav.xhtml").decode()
    with Book(str(out)) as b2:  # the output is a readable EPUB again
        assert b2.language == "tr" and b2.title == "Saatçi"


def test_write_bilingual(tmp_path, epub_path):
    out = tmp_path / "bi.epub"
    with Book(epub_path) as b:
        translate_all(b, lambda s: "TR " + s.source)
        b.apply(bilingual=True, target_lang="tr")
        b.write(str(out), target_lang="tr", bilingual=True)
    z = zipfile.ZipFile(out)
    ch1 = z.read("OEBPS/ch1.xhtml").decode()
    assert ch1.count("Della counted the coins") == 2 and ch1.count('id="r1"') == 1  # ids not duplicated
    assert "epub-tr-translation" in ch1 and "<style" in ch1
    nav = z.read("OEBPS/nav.xhtml").decode()
    assert nav.count("Chapter Two") == 1  # nav translated in place, never duplicated
    langs = [e.text for e in etree.fromstring(z.read("OEBPS/content.opf")).iter(f"{DC}language")]
    assert langs == ["tr", "en"]


def test_untranslated_segments_are_kept(tmp_path, epub_path):
    out = tmp_path / "partial.epub"
    with Book(epub_path) as b:
        b.documents[0].segments[1].translation = "Della paraları üç kez saydı."
        stats = b.apply()
        b.write(str(out))
    with Book(epub_path) as fresh:
        n = len(fresh.all_segments())
    assert stats["applied"] == 1 and stats["untranslated"] == n - 1
    z = zipfile.ZipFile(out)
    assert "OEBPS/ch2.xhtml" in z.namelist() and z.read("OEBPS/ch2.xhtml") == zipfile.ZipFile(epub_path).read("OEBPS/ch2.xhtml")
    assert z.read("OEBPS/toc.ncx") == zipfile.ZipFile(epub_path).read("OEBPS/toc.ncx")  # NCX untouched


def test_lenient_count_when_markup_broken(tmp_path, epub_path):
    with Book(epub_path) as b:
        seg = b.documents[0].segments[1]
        seg.translation = "Della paraları üç kez saydı."  # placeholders dropped
        stats = b.apply()
    assert stats["lenient"] == 1


def test_epub2_without_nav_and_missing_language(tmp_path):
    opf = OPF3.replace('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>', "")
    opf = opf.replace("<dc:language>en</dc:language>", "").replace('version="3.0"', 'version="2.0"')
    p = make_epub(tmp_path / "e2.epub", opf=opf, nav=None)
    out = tmp_path / "e2.tr.epub"
    with Book(p) as b:
        assert b.language is None and not any(d.is_nav for d in b.documents)
        translate_all(b)
        b.apply()
        b.write(str(out))
    opf_out = etree.fromstring(zipfile.ZipFile(out).read("OEBPS/content.opf"))
    assert [e.text for e in opf_out.iter(f"{DC}language")] == ["tr"]


def test_malformed_xhtml_is_recovered(tmp_path):
    broken = CH1.replace("<p>Inside a div.</p>", "<p>Inside a div.<p>").replace("&", "&amp;")
    broken = broken.replace("It was all she had.", "It was all she had &nbsp;")  # undefined entity
    p = make_epub(tmp_path / "bad.epub", ch1=broken)
    with Book(p) as b:
        assert any("Della counted" in s.enc.plain() for s in b.documents[0].segments)


def test_ncx_with_nested_navpoints(tmp_path):
    ncx = NCX.replace('<content src="ch2.xhtml"/></navPoint>',
                      '<content src="ch2.xhtml"/><navPoint id="n3" playOrder="3"><navLabel><text>Part A</text>'
                      '</navLabel><content src="ch2.xhtml#a"/></navPoint></navPoint>')
    with Book(make_epub(tmp_path / "n.epub", ncx=ncx)) as b:
        assert [s.enc.plain() for s in b.ncx_segments] == ["Chapter One", "Chapter Two", "Part A"]


def test_real_gutenberg_sample_structure():
    with Book(MAGI) as b:
        assert b.title == "The Gift of the Magi" and b.language == "en"
        texts = [s.enc.plain() for s in b.all_segments()]
        assert len(texts) == 51 and texts[0] == "The Gift of the Magi"
        assert not any("Project Gutenberg" in t for t in texts)
    with Book(MAGI, skip_gutenberg=False) as b:
        assert any("Project Gutenberg" in s.enc.plain() for s in b.all_segments())
