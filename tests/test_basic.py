import os
import subprocess
import sys

from lxml import etree

from epub_tr.blocks import TagMismatch, decode_into, encode, validate
from epub_tr.epub_io import Book
from epub_tr.pipeline import SEG_RE, detect_names

HERE = os.path.dirname(__file__)
SAMPLE = os.path.join(HERE, "..", "samples", "pg7256.epub")
NS = "http://www.w3.org/1999/xhtml"


def el(xml):
    return etree.fromstring(f'<p xmlns="{NS}" id="p1">{xml}</p>')


def test_roundtrip_inline_markup():
    e = el('He said <i class="x">no</i>, <a href="#n1" id="r1">really<sup>1</sup></a>.<br/>Then &amp; left.')
    enc = encode(e)
    assert enc.text == 'He said <g1>no</g1>, <g2>really<g3>1</g3></g2>.<x4/>Then &amp; left.'
    tr = 'Hayır <g1>dedi</g1>, <g2>gerçekten<g3>1</g3></g2>.<x4/>Sonra &amp; gitti.'
    assert decode_into(e, tr, enc)
    out = etree.tostring(e, encoding="unicode")
    assert '<i class="x">dedi</i>' in out and 'id="r1"' in out and "<br/>" in out and "&amp; gitti" in out
    assert e.get("id") == "p1"


def test_mismatch_lenient_keeps_anchors():
    e = el('<a id="ch1"/>Hello <b>world</b>')
    enc = encode(e)
    try:
        validate("Merhaba dünya", enc)
        assert False
    except TagMismatch:
        pass
    assert decode_into(e, "Merhaba <g9>dünya</g9>", enc, strict=False) is False
    out = etree.tostring(e, encoding="unicode")
    assert 'id="ch1"' in out and "Merhaba dünya" in out


def test_seg_regex():
    out = 'x <seg id="1">Bir</seg>\n<seg id = "2" >İki <g1>a</g1></seg>'
    assert SEG_RE.findall(out) == [("1", "Bir"), ("2", "İki <g1>a</g1>")]


def test_names():
    assert "Della" in detect_names(["Then Della cried. And Della laughed.", "So did Jim and then Jim smiled."])


def test_book_echo(tmp_path):
    out = tmp_path / "o.epub"
    r = subprocess.run([sys.executable, "-m", "epub_tr.cli", "translate", SAMPLE, "-e", "echo", "-o", str(out),
                        "--no-cache", "-q"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    a, b = Book(SAMPLE), Book(str(out))
    sa = [s.enc.plain() for s in a.all_segments()]
    sb = [s.enc.plain() for s in b.all_segments()]
    assert sa == sb and len(sa) > 40
    assert b.language == "tr"
    import zipfile
    assert zipfile.ZipFile(out).namelist() == zipfile.ZipFile(SAMPLE).namelist()
