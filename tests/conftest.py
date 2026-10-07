"""Shared fixtures: synthetic EPUBs built in memory and fake (offline) translation engines."""
from __future__ import annotations

import os
import zipfile

import pytest

from epub_tr.engines.base import Engine, EngineError, RateLimited

HERE = os.path.dirname(__file__)
SAMPLES = os.path.join(HERE, "..", "samples")
MAGI = os.path.join(SAMPLES, "pg7256.epub")
WALLPAPER = os.path.join(SAMPLES, "pg1952.epub")

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

OPF3 = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">urn:uuid:epub-tr-test</dc:identifier>
    <dc:title>The Clockmaker</dc:title>
    <dc:creator>Jane Doe</dc:creator>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
    <item id="img" href="pic.png" media-type="image/png"/>
    <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx"><itemref idref="c1"/><itemref idref="c2"/></spine>
</package>"""

NAV = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
<head><title>Contents</title></head>
<body><nav epub:type="toc" id="toc"><ol>
  <li><a href="ch1.xhtml#c1">Chapter One</a></li>
  <li><a href="ch2.xhtml">Chapter Two</a></li>
</ol></nav></body></html>"""

NCX = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:epub-tr-test"/></head>
  <docTitle><text>The Clockmaker</text></docTitle>
  <navMap>
    <navPoint id="n1" playOrder="1"><navLabel><text>Chapter One</text></navLabel><content src="ch1.xhtml#c1"/></navPoint>
    <navPoint id="n2" playOrder="2"><navLabel><text>Chapter Two</text></navLabel><content src="ch2.xhtml"/></navPoint>
  </navMap>
</ncx>"""

CH1 = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head><title>Chapter One</title><link rel="stylesheet" href="style.css"/></head>
<body>
  <section id="pg-header"><p>The Project Gutenberg eBook of something.</p></section>
  <h1 id="c1">Chapter One</h1>
  <p id="p1">Della counted the coins <i>three</i> times.<br/>It was all she had.</p>
  <p>Della looked at <a href="#fn1" id="r1">Jim<sup>1</sup></a> and smiled.</p>
  <div class="box"><p>Inside a div.</p><p>Second in div.</p></div>
  <p class="notranslate">Do not translate me.</p>
  <p translate="no">Nor me.</p>
  <pre>code block stays</pre>
  <p>12345</p>
  <img src="pic.png" alt="a picture"/>
  <ul><li>First item</li><li>Second <b>item</b></li></ul>
  <aside id="fn1"><p>A footnote by Jim.</p></aside>
</body></html>"""

CH2 = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head><title>Chapter Two</title></head>
<body><h2>Chapter Two</h2><p>The end came quietly.</p><script>var x = "not text";</script></body></html>"""

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def make_epub(path, ch1=CH1, ch2=CH2, opf=OPF3, nav=NAV, ncx=NCX, extra=None):
    """Write a small but complete EPUB 3 (nav + NCX) to ``path`` and return it."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", opf)
        if nav is not None:
            z.writestr("OEBPS/nav.xhtml", nav)
        if ncx is not None:
            z.writestr("OEBPS/toc.ncx", ncx)
        z.writestr("OEBPS/style.css", "p { text-indent: 1em; }")
        z.writestr("OEBPS/pic.png", PNG)
        z.writestr("OEBPS/ch1.xhtml", ch1)
        z.writestr("OEBPS/ch2.xhtml", ch2)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return str(path)


@pytest.fixture
def epub_path(tmp_path):
    return make_epub(tmp_path / "book.epub")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """No test may touch the user's cache or wait for real back-off sleeps."""
    monkeypatch.setenv("EPUB_TR_CACHE", str(tmp_path / "cache" / "cache.sqlite3"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("epub_tr.pipeline.time.sleep", lambda s: None)


# ---------------------------------------------------------------- fake engines
class UpperMT(Engine):
    """Deterministic MT: upper-cases text outside placeholders; records every batch."""
    name = "upper"
    max_chars = 200

    def __init__(self, **kw):
        super().__init__(**kw)
        self.batches = []

    def translate_batch(self, texts):
        self.batches.append(list(texts))
        import re
        return [re.sub(r"(<[^>]+>)|([^<]+)", lambda m: m.group(1) or m.group(2).upper(), t) for t in texts]


class FailingEngine(Engine):
    name = "broken"

    def __init__(self, exc=EngineError, **kw):
        super().__init__(**kw)
        self.exc = exc
        self.calls = 0

    def translate_batch(self, texts):
        self.calls += 1
        raise self.exc("boom")


class FakeLLM(Engine):
    """LLM that answers every <seg> with '[tr] ...' and reports a glossary entry."""
    name = "fakellm"
    is_llm = True
    default_workers = 1

    def __init__(self, drop=(), glossary="Della => Della", prefix="[tr] ", **kw):
        super().__init__(**kw)
        self.drop = set(drop)       # seg ids omitted in the first answer
        self.glossary = glossary
        self.prefix = prefix
        self.prompts = []

    def complete(self, system, user):
        import re
        self.prompts.append((system, user))
        segs = re.findall(r'<seg id="(\d+)">(.*?)</seg>', user, re.S)
        if "DRAFT (" in user:  # polish request: only answer the draft part
            draft = user.split("DRAFT (", 1)[1]
            segs = re.findall(r'<seg id="(\d+)">(.*?)</seg>', draft, re.S)
            return "\n".join(f'<seg id="{i}">{t} (polished)</seg>' for i, t in segs)
        first = len(self.prompts) == 1
        out = [f'<seg id="{i}">{self.prefix}{t}</seg>' for i, t in segs if not (first and int(i) in self.drop)]
        if self.glossary:
            out.append(f"<glossary>\n{self.glossary}\n</glossary>")
        return "\n".join(out)


@pytest.fixture
def upper():
    return UpperMT()


__all__ = ["make_epub", "UpperMT", "FailingEngine", "FakeLLM", "RateLimited", "MAGI", "WALLPAPER"]
