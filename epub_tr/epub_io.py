"""EPUB reading / writing.

Reading uses *ebooklib* (metadata, manifest, spine order) and *lxml* for the
XHTML documents.  Writing is done at the ZIP level: every entry of the source
EPUB is copied byte-for-byte (images, CSS, fonts, cover, ...) and only the
translated XHTML documents, the OPF (language/title) and the NCX/nav labels are
replaced.  This keeps the original structure intact far better than
re-generating the book with ``ebooklib.epub.write_epub``.
"""
from __future__ import annotations

import copy
import posixpath
import warnings
import zipfile
from dataclasses import dataclass, field

import ebooklib
from ebooklib import epub
from lxml import etree

from .blocks import Encoded, decode_into, encode, localname

warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

XHTML_NS = "http://www.w3.org/1999/xhtml"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
DC_NS = "http://purl.org/dc/elements/1.1/"
NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"

# Elements that are translated as one unit when they do not contain other blocks.
BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd", "td", "th",
    "caption", "figcaption", "blockquote", "div", "section", "article", "aside",
    "header", "footer", "summary", "label", "legend", "title",
}
CONTAINER_TAGS = BLOCK_TAGS | {"ul", "ol", "dl", "table", "tr", "tbody", "thead", "figure", "nav", "body", "hr", "pre"}
SKIP_TAGS = {"script", "style", "pre", "code", "svg", "math", "head"}
GUTENBERG_IDS = {"pg-header", "pg-footer", "pg-machine-header", "pg-start-separator", "pg-end-separator"}


@dataclass
class Segment:
    uid: str                 # stable id: "<doc-index>:<n>"
    doc: Document
    element: object          # lxml element
    enc: Encoded
    kind: str = "text"       # text | heading | toc
    translation: str | None = None
    engine: str | None = None

    @property
    def source(self) -> str:
        return self.enc.text


@dataclass
class Document:
    index: int
    zip_path: str
    href: str
    tree: object
    is_nav: bool = False
    segments: list = field(default_factory=list)
    modified: bool = False


class Book:
    def __init__(self, path: str, skip_gutenberg: bool = True, translate_toc: bool = True):
        self.path = path
        self.skip_gutenberg = skip_gutenberg
        self.translate_toc = translate_toc
        self.zip = zipfile.ZipFile(path)
        self.ebook = epub.read_epub(path, options={"ignore_ncx": False})
        self.opf_path = self._find_opf()
        self.opf_dir = posixpath.dirname(self.opf_path)
        self.title = self._first_meta("title")
        self.language = self._first_meta("language")
        self.creator = self._first_meta("creator")
        self.documents: list[Document] = []
        self.ncx_path: str | None = None
        self.ncx_tree = None
        self.ncx_segments: list[Segment] = []
        self._load_documents()

    def close(self):
        self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------ load
    def _first_meta(self, name):
        vals = self.ebook.get_metadata("DC", name)
        return vals[0][0] if vals else None

    def _find_opf(self) -> str:
        container = etree.fromstring(self.zip.read("META-INF/container.xml"))
        rootfile = container.find(".//{*}rootfile")
        return rootfile.get("full-path")

    def _zip_name(self, href: str) -> str:
        return posixpath.normpath(posixpath.join(self.opf_dir, href)) if self.opf_dir else href

    def _load_documents(self):
        spine_ids = [s[0] for s in self.ebook.spine]
        items = []
        for idref in spine_ids:
            it = self.ebook.get_item_with_id(idref)
            if it is not None and it.get_type() in (ebooklib.ITEM_DOCUMENT, ebooklib.ITEM_NAVIGATION):
                items.append(it)
        # nav document(s) not in spine
        for it in self.ebook.get_items():
            if it in items:
                continue
            props = getattr(it, "properties", []) or []
            if isinstance(it, epub.EpubNav) or "nav" in props:
                items.append(it)
            elif it.get_type() == ebooklib.ITEM_NAVIGATION and it.get_name().endswith(".ncx"):
                self.ncx_path = self._zip_name(it.get_name())
        for it in self.ebook.get_items():
            if it.get_name().endswith(".ncx"):
                self.ncx_path = self._zip_name(it.get_name())

        for idx, it in enumerate(items):
            zp = self._zip_name(it.get_name())
            if zp not in self.zip.namelist() or zp.endswith(".ncx"):
                continue
            raw = self.zip.read(zp)
            tree = _parse_xhtml(raw)
            if tree is None:
                continue
            props = getattr(it, "properties", []) or []
            is_nav = isinstance(it, epub.EpubNav) or "nav" in props
            doc = Document(index=idx, zip_path=zp, href=it.get_name(), tree=tree, is_nav=is_nav)
            if is_nav and not self.translate_toc:
                pass
            else:
                self._collect(doc)
            self.documents.append(doc)

        if self.translate_toc and self.ncx_path and self.ncx_path in self.zip.namelist():
            self.ncx_tree = etree.fromstring(self.zip.read(self.ncx_path), etree.XMLParser(recover=True))
            for n, t in enumerate(self.ncx_tree.iter("{%s}text" % NCX_NS, "text")):
                if (t.text or "").strip() and _parent_local(t) == "navlabel":
                    self.ncx_segments.append(Segment(uid=f"ncx:{n}", doc=None, element=t, enc=encode(t), kind="toc"))

    def _collect(self, doc: Document):
        root = doc.tree.getroot()
        body = root.find("{%s}body" % XHTML_NS)
        if body is None:
            body = root.find("body")
        if body is None:
            return
        n = 0

        def skip(el) -> bool:
            name = localname(el.tag)
            if name in SKIP_TAGS:
                return True
            if el.get("translate") == "no" or "notranslate" in (el.get("class") or "").split():
                return True
            if self.skip_gutenberg and (el.get("id") in GUTENBERG_IDS or "pg-boilerplate" in (el.get("class") or "")):
                return True
            return False

        def has_block_child(el) -> bool:
            for d in el.iterdescendants():
                if localname(d.tag) in CONTAINER_TAGS:
                    return True
            return False

        def visit(el):
            nonlocal n
            for ch in el:
                if not isinstance(ch.tag, str) or skip(ch):
                    continue
                name = localname(ch.tag)
                if doc.is_nav and name in ("a", "span") :
                    self._add(doc, ch, n, "toc")
                    n += 1
                    continue
                if name in BLOCK_TAGS and not has_block_child(ch):
                    self._add(doc, ch, n, "heading" if name.startswith("h") and len(name) == 2 else "text")
                    n += 1
                elif name in CONTAINER_TAGS or name in BLOCK_TAGS:
                    visit(ch)
                else:
                    # inline element directly in a container (rare): translate as block
                    if (ch.text or "").strip() or len(ch):
                        if not has_block_child(ch):
                            self._add(doc, ch, n, "text")
                            n += 1
                        else:
                            visit(ch)
        visit(body)

    def _add(self, doc, el, n, kind):
        enc = encode(el)
        if not _is_translatable(enc.plain()):
            return
        doc.segments.append(Segment(uid=f"{doc.index}:{n}", doc=doc, element=el, enc=enc, kind=kind))

    # --------------------------------------------------------------- access
    def all_segments(self, include_toc=True):
        out = []
        for d in self.documents:
            out.extend(d.segments)
        if include_toc:
            out.extend(self.ncx_segments)
        return out

    # ---------------------------------------------------------------- write
    def apply(self, bilingual: bool = False, target_lang: str = "tr") -> dict:
        stats = {"applied": 0, "lenient": 0, "untranslated": 0}
        for seg in self.all_segments():
            if not seg.translation:
                stats["untranslated"] += 1
                continue
            el = seg.element
            if bilingual and seg.kind != "toc" and not (seg.doc is not None and seg.doc.is_nav):
                new = copy.deepcopy(el)
                for d in new.iter():
                    if isinstance(d.tag, str) and d.get("id"):
                        del d.attrib["id"]
                new.tail = el.tail
                el.tail = None
                cls = (new.get("class") or "").split()
                new.set("class", " ".join(cls + ["epub-tr-translation"]))
                new.set("lang", target_lang)
                new.set(XML_LANG, target_lang)
                el.addnext(new)
                target = new
            else:
                target = el
            full = decode_into(target, seg.translation, seg.enc, strict=False)
            if target is not el:
                # rebuilt inline children (anchors, note refs) must not duplicate the original ids
                for d in target.iter():
                    if isinstance(d.tag, str) and d.get("id"):
                        del d.attrib["id"]
            stats["applied"] += 1
            if not full:
                stats["lenient"] += 1
            if seg.doc is not None:
                seg.doc.modified = True
        if not bilingual:
            for d in self.documents:
                if d.modified:
                    root = d.tree.getroot()
                    root.set("lang", target_lang)
                    root.set(XML_LANG, target_lang)
        return stats

    def write(self, out_path: str, target_lang: str = "tr", title: str | None = None, bilingual: bool = False):
        replacements: dict[str, bytes] = {}
        for d in self.documents:
            if d.modified:
                if bilingual:
                    _inject_bilingual_css(d.tree)
                replacements[d.zip_path] = etree.tostring(d.tree, xml_declaration=True, encoding="utf-8")
        if self.ncx_tree is not None and any(s.translation for s in self.ncx_segments):
            replacements[self.ncx_path] = etree.tostring(self.ncx_tree, xml_declaration=True, encoding="utf-8")
        replacements[self.opf_path] = self._patched_opf(target_lang, title, bilingual)

        with zipfile.ZipFile(out_path, "w") as out:
            names = self.zip.namelist()
            if "mimetype" in names:
                out.writestr(zipfile.ZipInfo("mimetype"), self.zip.read("mimetype"), compress_type=zipfile.ZIP_STORED)
            for name in names:
                if name == "mimetype":
                    continue
                data = replacements.get(name)
                if data is None:
                    data = self.zip.read(name)
                out.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)

    def _patched_opf(self, target_lang, title, bilingual) -> bytes:
        tree = etree.fromstring(self.zip.read(self.opf_path))
        meta = tree.find("{*}metadata")
        langs = meta.findall("{%s}language" % DC_NS)
        if langs:
            if bilingual:
                new = copy.deepcopy(langs[0])
                new.text = target_lang
                langs[0].addprevious(new)
            else:
                langs[0].text = target_lang
        else:
            el = etree.SubElement(meta, "{%s}language" % DC_NS)
            el.text = target_lang
        if title:
            t = meta.find("{%s}title" % DC_NS)
            if t is not None:
                t.text = title
        # mark as translated
        contrib = etree.SubElement(meta, "{%s}contributor" % DC_NS)
        contrib.text = "epub-tr (machine translation)"
        return etree.tostring(tree, xml_declaration=True, encoding="utf-8")


def _parent_local(el):
    p = el.getparent()
    return localname(p.tag) if p is not None else ""


def _is_translatable(text: str) -> bool:
    return any(c.isalpha() for c in text)


def _parse_xhtml(raw: bytes):
    try:
        parser = etree.XMLParser(resolve_entities=False, strip_cdata=False, recover=False, huge_tree=True)
        return etree.parse(_bio(raw), parser)
    except etree.XMLSyntaxError:
        try:
            parser = etree.XMLParser(recover=True, huge_tree=True)
            return etree.parse(_bio(raw), parser)
        except Exception:
            return None


def _bio(raw):
    import io
    return io.BytesIO(raw)


BILINGUAL_CSS = ".epub-tr-translation{color:#444;font-style:normal;margin-top:0.2em;margin-bottom:0.9em;}"


def _inject_bilingual_css(tree):
    root = tree.getroot()
    head = root.find("{%s}head" % XHTML_NS)
    if head is None:
        return
    style = etree.SubElement(head, "{%s}style" % XHTML_NS)
    style.set("type", "text/css")
    style.text = BILINGUAL_CSS
