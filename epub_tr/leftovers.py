"""Leftover checks for finished Turkish EPUBs.

english_hits(text)   -> lowercase English function words that survived MT. Proper names and citation
                        titles (Title Case runs joined by function words: "Joan of Arc",
                        "A History of the War") and laughter ("he he he!") are ignored, so real
                        English prose is caught while names do not block a book.
is_english_leftover(text, min_hits=2) -> bool
strip_gutenberg_leftovers(xhtml_bytes) -> (bytes, removed): removes producer / transcriber notes
                        ("... e-posta ...@pglaf.org", "Gutenberg baskısında ...", "Project Gutenberg"
                        links). Short note blocks are dropped; in long paragraphs only the sentence.
"""
import re
from lxml import etree

EN_FUNCTION = frozenset(
    "the of and to with was were his from that which this would could should they them their there "
    "have has been will by he she it is are but what when who whom".split())
_CAP = r"[A-ZÇĞİÖŞÜ][\w'’\-]*"
_FW = r"(?:of|the|and|in|on|to|a|an|for|with|by|from|at|or|de|la|le|von|van|der)"
_NAMEOF = re.compile(rf"\b{_CAP}(?:\s+(?:{_FW}\s+)+{_CAP}|\s+{_CAP})*(?:\s+(?:{_FW}\s+)+{_CAP})")
_LAUGH = re.compile(r"\b(?:[Hh]e[\s!,.\-—]+){1,}[Hh]e\b|\b[Hh]e!")


def english_hits(text):
    s = _NAMEOF.sub(" ", _LAUGH.sub(" ", text or ""))
    return [w for w in re.findall(r"[^\W\d_]+", s) if w in EN_FUNCTION]


def is_english_leftover(text, min_hits=2):
    return len(english_hits(text)) >= min_hits


GUT_LEFTOVER = re.compile(
    r"project\s+gutenberg|gutenberg\.(?:org|net)|gutenberg\s*(?:e-?kitab\w*|e-?book\w*|lisans\w*|baskı\w*|"
    r"sürüm\w*|projesi\w*|arşiv\w*|metni\w*|license|edition|ebook|text)|\bpglaf\b", re.I)
_BLOCKS = {"p", "li", "td", "h1", "h2", "h3", "h4", "h5", "h6", "div", "blockquote", "dd", "dt", "th", "caption"}


def _local(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def _drop_sentences(s):
    return " ".join(x for x in re.split(r"(?<=[.!?])\s+", s) if not GUT_LEFTOVER.search(x))


def strip_gutenberg_leftovers(raw, max_note=400):
    t = etree.fromstring(raw, etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False))
    removed = 0
    for el in list(t.iter()):
        if _local(el.tag) not in _BLOCKS:
            continue
        if any(_local(d.tag) in _BLOCKS for d in el.iterdescendants()):
            continue
        txt = "".join(el.itertext())
        if not GUT_LEFTOVER.search(txt):
            continue
        if len(txt.strip()) <= max_note:
            parent = el.getparent()
            if parent is None:
                continue
            if el.tail and el.tail.strip():
                prev = el.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or "") + el.tail
                else:
                    parent.text = (parent.text or "") + el.tail
            parent.remove(el)
        else:
            for e in el.iter():
                for a in ("text", "tail"):
                    v = getattr(e, a)
                    if v and GUT_LEFTOVER.search(v) and (e is not el or a == "text"):
                        setattr(e, a, _drop_sentences(v))
        removed += 1
    if not removed:
        return raw, 0
    return etree.tostring(t, xml_declaration=True, encoding="utf-8"), removed
