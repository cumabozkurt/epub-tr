"""Source clean-ups before translation and a leftover-language QA pass after it.

* ``<pre>`` poetry/prose blocks become translatable paragraphs (line layout kept with
  ``<br/>``); blocks that look like program code are left alone.
* stretched / stammered words are normalised (``Beau—ootiful Soo—oop`` -> ``Beautiful Soup``,
  ``e—e—evening`` -> ``evening``) so engines can translate them.
* words broken across a ``<br/>`` are re-joined (``two p<br/>ennyworth`` -> ``two pennyworth``).
* optional removal of Project Gutenberg header/footer/license boilerplate.
* ``qa_epub``: finds text nodes that still contain source-language words and retranslates them.

Word-level heuristics need the optional ``wordfreq`` package (``pip install epub-tr[qa]``);
without it only the structural fixes (``<pre>``, boilerplate) are applied.
"""
from __future__ import annotations

import difflib
import re
import zipfile
from functools import lru_cache

from lxml import etree

XH = "http://www.w3.org/1999/xhtml"
WORD_FIX_LANGS = {"en"}   # stretched-word / broken-word heuristics are tuned for English sources
GUTENBERG_IDS = {"pg-header", "pg-footer", "pg-machine-header", "pg-start-separator", "pg-end-separator"}
PG_MARKER = re.compile(r"\*\*\*\s*(START|END) OF (THE|THIS) PROJECT GUTENBERG", re.I)
CODE_LIKE = re.compile(r"[{};]\s*$|^\s*(def|class|import|return|for|while|if)\b.*[:({]|[=<>]{2}|->|::", re.M)

try:  # optional
    from wordfreq import top_n_list, zipf_frequency
except Exception:  # pragma: no cover - exercised only without wordfreq
    zipf_frequency = None
    top_n_list = None


def have_wordfreq() -> bool:
    return zipf_frequency is not None


def _q(tag):
    return f"{{{XH}}}{tag}"


def _local(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


# ------------------------------------------------------------------ <pre> blocks
def looks_like_code(el) -> bool:
    if el.find(".//" + _q("code")) is not None or _local(el.tag) == "code":
        return True
    text = "".join(el.itertext())
    return len(CODE_LIKE.findall(text)) >= 2


def convert_pre(body) -> int:
    """Turn prose/poetry ``<pre>`` blocks into ``<p class="pre-poem">`` with ``<br/>`` line breaks."""
    n = 0
    for pre in list(body.iter(_q("pre"))):
        if looks_like_code(pre):
            continue
        pre.tag = _q("p")
        pre.set("class", ((pre.get("class") or "") + " pre-poem").strip())
        if not pre.get("style"):
            pre.set("style", "text-align:left;margin-left:2em")
        for el, attr in [(pre, "text")] + [x for c in list(pre.iter()) if c is not pre for x in ((c, "text"), (c, "tail"))]:
            s = getattr(el, attr)
            if not s or "\n" not in s:
                continue
            lines = s.split("\n")
            setattr(el, attr, lines[0].strip() if el is pre and attr == "text" else lines[0])
            parent = el if attr == "text" else el.getparent()
            idx = 0 if attr == "text" else list(parent).index(el) + 1
            for ln in lines[1:]:
                br = etree.Element(_q("br"))
                br.tail = (" " + ln.strip()) if ln.strip() else ""
                parent.insert(idx, br)
                idx += 1
        while len(pre) and _local(pre[0].tag) == "br" and not (pre.text or "").strip():
            pre.text = (pre[0].tail or "").strip()
            pre.remove(pre[0])
        while len(pre) and _local(pre[-1].tag) == "br" and not (pre[-1].tail or "").strip():
            pre.remove(pre[-1])
        n += 1
    return n


# ------------------------------------------------------------------ word fixes
_SKIDX = None


def _skel(w):
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy]", "", w.lower()))


def _skeleton_index(lang):
    global _SKIDX
    if _SKIDX is None:
        _SKIDX = {}
        for w in top_n_list(lang, 40000):
            if w.isalpha():
                _SKIDX.setdefault(_skel(w), []).append(w)
    return _SKIDX


def fix_stretched(tok: str, lang: str = "en", vocab: set | None = None) -> str:
    """Normalise one dash-joined token; returns it unchanged when it is a real compound."""
    if zipf_frequency is None:
        return tok
    Z = zipf_frequency
    parts = [p for p in re.split(r"[—–-]+", tok) if p]
    if len(parts) < 2 or len({p.lower() for p in parts}) == 1:   # stammer: I—I, gone—gone
        return tok
    stretched = (any(parts[i][-1].lower() == parts[i + 1][0].lower() for i in range(len(parts) - 1))
                 or any(Z(p.lower(), lang) < 2.0 for p in parts))
    if not stretched and all(Z(p.lower(), lang) >= 3.0 for p in parts):
        return tok                                                # said—and, blue—grey
    base = re.sub(r"[—–-]+", "", tok)
    cands = [base, re.sub(r"(.)\1{2,}", r"\1\1", base), re.sub(r"(.)\1+", r"\1", base)]
    best = next((c.lower() for c in cands if Z(c.lower(), lang) >= 3.0), None)
    if best is None and stretched:
        pool = [w for w in _skeleton_index(lang).get(_skel(base), []) if w[0] == base[0].lower()]
        if pool:
            def score(w):
                r = max(difflib.SequenceMatcher(None, c.lower(), w).ratio() for c in cands)
                return r + 0.15 * Z(w, lang) + (1.0 if vocab and w in vocab else 0.0)
            w = max(pool, key=score)
            if max(difflib.SequenceMatcher(None, c.lower(), w).ratio() for c in cands) >= 0.6:
                best = w
    if not best:
        return tok
    if tok.isupper():
        return best.upper()
    return best[0].upper() + best[1:] if tok[0].isupper() else best


STRETCH = re.compile(r"(?<![\w—])[A-Za-z]+(?:[—–][A-Za-z]+)+(?![\w—])")


def fix_text(s: str | None, lang="en", vocab=None):
    if not s or ("—" not in s and "–" not in s):
        return s
    return STRETCH.sub(lambda m: fix_stretched(m.group(0), lang, vocab), s)


def join_broken_words(body, lang="en") -> int:
    """``two p<br/>ennyworth`` -> ``two pennyworth`` (only when the joined form is a known word)."""
    if zipf_frequency is None:
        return 0
    Z, n = zipf_frequency, 0
    for br in list(body.iter(_q("br"))):
        prev, par = br.getprevious(), br.getparent()
        before = (prev.tail if prev is not None else par.text) or ""
        after = br.tail or ""
        m1, m2 = re.search(r"([A-Za-z]+)\s*$", before), re.match(r"\s*([a-z]+)", after)
        if not (m1 and m2):
            continue
        a, b = m1.group(1), m2.group(1)
        if Z((a + b).lower(), lang) >= 1.5 and Z(b, lang) < 1.5 and (len(a) <= 2 or Z(a.lower(), lang) < 4.5):
            joined = before[:m1.start(1)] + a + b + after[m2.end(1):]
            par.remove(br)
            if prev is not None:
                prev.tail = joined
            else:
                par.text = joined
            n += 1
    return n


def strip_boilerplate(body) -> int:
    n = 0
    for el in list(body.iter()):
        if not isinstance(el.tag, str):
            continue
        if el.get("id") in GUTENBERG_IDS or "pg-boilerplate" in (el.get("class") or ""):
            p = el.getparent()
            if p is None:
                continue
            if el.tail:
                prev = el.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or "") + el.tail
                else:
                    p.text = (p.text or "") + el.tail
            p.remove(el)
            n += 1
    for el in list(body.iter()):
        if isinstance(el.tag, str) and el.text and PG_MARKER.search(el.text) and el.getparent() is not None:
            el.getparent().remove(el)
            n += 1
    return n


def _is_small_caps(el) -> bool:
    if not isinstance(el.tag, str):
        return False
    tag, cls, sty = _local(el.tag), (el.get("class") or "").lower(), (el.get("style") or "").lower()
    return tag == "small" or (tag == "span" and ("smcap" in cls or "small-cap" in cls or "smallcap" in cls
                                                   or cls.split() == ["sc"] or "small-caps" in sty))


def merge_small_caps(body) -> int:
    """``M<small>RS</small>`` / ``Q<span class="smcap">UIRKE</span>`` -> ``Mrs`` / ``Quirke`` as one plain word.

    Engines otherwise translate the two halves separately and break names (``S<small>UIRKE</small>``).
    Whole small-caps words without a leading capital outside the tag keep their markup."""
    n = 0
    for el in list(body.iter()):
        if not _is_small_caps(el) or len(el) or not el.text:
            continue
        if not re.fullmatch(r"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ’'.]*", el.text):
            continue
        prev, par = el.getprevious(), el.getparent()
        if par is None:
            continue
        before = (prev.tail if prev is not None else par.text) or ""
        m = re.search(r"(?:^|(?<=[\s(\[\"“‘'—–-]))([A-ZÀ-ÖØ-Þ])$", before)
        if not m:
            continue
        merged = before[:m.start(1)] + m.group(1) + el.text.lower() + (el.tail or "")
        if prev is not None:
            prev.tail = merged
        else:
            par.text = merged
        par.remove(el)
        n += 1
    return n


_FFFD_CANDIDATES = "àâäéèêëîïôöùûüçñáíóúßæœ"


def fix_replacement_chars(s: str | None) -> str | None:
    """Repair U+FFFD left in the source (``for\ufffdt`` -> ``forêt``, ``\ufffd la`` -> ``à la``) from word
    frequencies; anything that cannot be repaired is dropped so no U+FFFD reaches the output."""
    if not s or "\ufffd" not in s:
        return s

    def best(m):
        w = m.group(0)
        if zipf_frequency is None:
            return w.replace("\ufffd", "")
        score, cand = max((max(zipf_frequency(w.replace("\ufffd", c, 1).lower(), lang)
                               for lang in ("fr", "en", "de", "es", "it", "pt")), w.replace("\ufffd", c, 1))
                          for c in _FFFD_CANDIDATES)
        return fix_replacement_chars(cand) if score >= 1.0 else w.replace("\ufffd", "", 1)

    return re.sub(r"[^\W\d_]*\ufffd[\ufffd\w]*", best, s).replace("\ufffd", "")


# ---------------------------------------------------------------- old-sense "gay" (cheerful) before MT
# Pre-1950 English: gay/gaily/gaiety mean cheerful; MT renders them as "eşcinsel". Map them to merry/... first.
_OLD_GAY = {"gay": "merry", "gayer": "merrier", "gayest": "merriest", "gaily": "merrily", "gayly": "merrily",
            "gaiety": "merriment", "gayety": "merriment", "gaieties": "merriments", "gayeties": "merriments",
            "gayness": "merriness",
            # old-sense queer (odd, strange): MT says "eşcinsel" too
            "queer": "strange", "queerer": "stranger", "queerest": "strangest", "queerly": "strangely",
            "queerness": "strangeness"}
_OLD_GAY_RE = re.compile(r"(?<![\w'’-])(" + "|".join(sorted(_OLD_GAY, key=len, reverse=True)) + r")(?!\w)", re.I)
_SENT_START = re.compile(r"(?:^|[.!?:;]\s*[\"“‘'(\[—-]*\s*|^[\"“‘'(\[—-]+\s*)$")
_ABBR = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|St|Rev|Capt|Col|Gen|Sir|Lady|Lord|Miss|Madame|Mme|John|Delphine)\.?\s*$")


def old_sense(s: str | None, at_start: bool = True) -> str | None:
    """gay -> merry etc. (case kept). A capitalised Gay mid-sentence is a surname (John Gay) and is kept;
    at a sentence start it is mapped. at_start: the string begins a block (text start = sentence start)."""
    if not s or ("ga" not in s.lower() and "queer" not in s.lower()):
        return s

    def f(m):
        w = m.group(1)
        new = _OLD_GAY[w.lower()]
        if w.isupper() and len(w) > 1:
            return new.upper()
        if w[0].isupper():
            before = s[:m.start()]
            if _ABBR.search(before) or not (_SENT_START.search(before) if before.strip() else at_start):
                return w
            return new[0].upper() + new[1:]
        return new
    return _OLD_GAY_RE.sub(f, s)


def old_sense_tree(body) -> int:
    n = 0
    for el in body.iter():
        if not isinstance(el.tag, str) or el.tag.split("}")[-1] in ("script", "style"):
            continue
        for a in ("text", "tail"):
            v = getattr(el, a)
            if v:
                v2 = old_sense(v, at_start=(a == "text"))
                if v2 != v:
                    setattr(el, a, v2)
                    n += 1
    return n


def preprocess_tree(tree, lang="en", pre=True, words=True, boilerplate=False, old_gay=True) -> bool:
    """old_gay: map old-sense gay/gaily/gaiety to merry/... (English sources written before ~1950)."""
    # Apply the fixes in place. Returns True when the document changed.
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    body = root.find(_q("body"))
    if body is None:
        return False
    before = etree.tostring(body)
    if boilerplate:
        strip_boilerplate(body)
    merge_small_caps(body)
    for el in body.iter():
        if isinstance(el.tag, str):
            el.text = fix_replacement_chars(el.text)
            el.tail = fix_replacement_chars(el.tail)
    if old_gay and lang == "en":
        old_sense_tree(body)
    if pre:
        convert_pre(body)
    if words and zipf_frequency is not None and lang in WORD_FIX_LANGS:
        vocab = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", "".join(body.itertext()))}
        for el in body.iter():
            if isinstance(el.tag, str) and _local(el.tag) not in ("pre", "code", "script", "style"):
                el.text = fix_text(el.text, lang, vocab)
                el.tail = fix_text(el.tail, lang, vocab)
        join_broken_words(body, lang)
    return etree.tostring(body) != before


# ------------------------------------------------------------------ leftover QA
TARGET_CHARS = {"tr": set("çğıöşüÇĞİÖŞÜ")}
# common words that are also valid in the target language
TARGET_OK = {"tr": {"not", "on", "son", "her", "ben", "bin", "kim", "sen", "ne", "de", "da", "an", "at", "ama", "bas", "hem",
                    "pas", "sat", "bar", "fon", "ek", "in", "kat", "mart", "pek", "tam", "top", "var", "yol", "ad", "alt", "ara",
                    "ay", "el", "et", "ev", "bay", "bey", "bak", "bu", "oda", "tek", "model", "film", "golf", "jet", "stop", "ok",
                    "bal", "dam", "dans", "dil", "fit", "gol", "hat", "kart", "kral", "mal", "set", "ton", "tren"}}
EN_FUNCTION = {"the", "and", "of", "with", "that", "which", "what", "this", "these", "those", "you", "your", "was", "were",
               "have", "has", "had", "would", "could", "should", "they", "their", "there", "from", "into", "very", "said",
               "but", "been", "will", "shall", "when", "where", "who", "whom", "whose", "why", "how", "about", "after",
               "before", "upon", "only", "than", "then", "them", "him", "his", "she", "its", "our", "out", "all"}


@lru_cache(maxsize=200_000)
def is_source_word(tok: str, source="en", target="tr") -> bool:
    """Heuristic: lower-case token that is frequent in ``source`` and not in ``target``."""
    if zipf_frequency is None:
        return False
    w = tok.lower().strip("'’")
    if len(w) < 2 or not w.isalpha() or not w.isascii() or any(c in TARGET_CHARS.get(target, ()) for c in tok):
        return False
    if re.fullmatch(r"[ivxlcdm]+", w) or w in TARGET_OK.get(target, ()):
        return False
    if source == "en" and w in EN_FUNCTION:
        return True
    if tok.isupper() and len(tok) >= 3:        # ALL-CAPS headings: only clearly common source words (not names)
        s, t = zipf_frequency(w, source), zipf_frequency(w, target)
        return s >= 4.0 and s - t >= 1.5
    if tok[0].isupper():                       # names, places
        return False
    s, t = zipf_frequency(w, source), zipf_frequency(w, target)
    if s < 3.2 or (t >= 3.8 and s - t < 1.5):
        return False
    return s - t >= 0.8


def _compound(w, lang="en"):
    """hearthrug -> hearth + rug: both parts ordinary words."""
    return any(zipf_frequency(w[:i], lang) >= 3.0 and zipf_frequency(w[i:], lang) >= 3.0 and w[i:] not in NAME_ENDINGS
               for i in range(5, len(w) - 2))


NAME_ENDINGS = {"and", "ish", "ing", "ton", "son", "ley", "ford", "land", "ville", "wood", "field", "man", "ham", "well",
                "worth", "by", "dale", "more", "stone", "bury", "wick", "ell", "er", "ers", "ett", "ard", "ie", "ey"}


class SourceInfo:
    """Facts about the source text used to tell names (Alice, Bill) from capitalised common nouns (Hearthrug)."""

    def __init__(self, text: str = ""):
        import collections
        self.all = set(re.findall(r"[A-Za-z]+", text))
        self.lower = {w for w in self.all if w.islower()}
        self.caps = collections.Counter(m.group(1) for m in re.finditer(r"(?<=[a-z,;] )([A-Z][a-z]{2,})\b", text))

    def maybe_common_noun(self, tok: str, source="en", target="tr") -> bool:
        if zipf_frequency is None or tok not in self.all or len(tok) < 4 or tok.isupper():
            return False
        lw = tok.lower()
        if zipf_frequency(lw, target) >= 2.5:
            return False
        if lw in self.lower:
            return True
        return self.caps.get(tok, 0) <= 1 and _compound(lw, source)


TOKEN = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")


# Half-translated paragraphs ("O my eş is a iyice domesticated kadın"): short function words are skipped
# word by word (too short / target-language homographs: is, not, it), so the paragraph is judged as a whole.
MIX_STRONG = {"en": {"my", "am", "are", "the", "of", "and", "to", "if", "we", "was", "were", "you", "his", "with", "that",
                     "this", "for", "have", "has", "would", "should", "could", "they", "their", "which", "what", "when",
                     "been", "will", "from", "our", "your", "but", "or", "by", "me", "him", "she", "per"}}
MIX_WEAK = {"en": {"is", "not", "it", "an", "at"}}


def mixed_words(text: str, source="en", target="tr") -> list[str]:
    """Source function words of a paragraph that is still partly in the source language (else [])."""
    strong, weak = MIX_STRONG.get(source), MIX_WEAK.get(source, set())
    if not strong or source == target:
        return []
    w = re.findall(r"[^\W\d_]+", text or "")
    if len(w) < 6:
        return []
    st = [x for x in w if x.lower() in strong and not (x.isupper() and len(x) > 1)]
    if source == "en":
        st += [m.group(0) for m in re.finditer(r"(?<![\w\"'‘“\-—])I(?=\s+[a-z])", text)]
    wk = [x for x in w if x.lower() in weak and not x.isupper()]
    n = len(st) + 0.5 * len(wk)
    return st + wk if n >= 3 and n / len(w) >= 0.06 else []


def leftover_words(text: str, source="en", target="tr", src_info: SourceInfo | None = None) -> list[str]:
    mixed = mixed_words(text, source, target)
    return mixed + _leftover_words(text, source, target, src_info) if mixed else _leftover_words(text, source, target, src_info)


def _leftover_words(text: str, source="en", target="tr", src_info: SourceInfo | None = None) -> list[str]:
    text = re.sub(r"https?://\S+|www\.\S+|\S+@\S+|\b[\w-]+(?:\.[\w-]+)+\.[a-z]{2,}\b", "", text or "")
    out = []
    for t in TOKEN.findall(text):
        w = re.split(r"['’]", t.strip("'’"))[0]       # LANDING'i -> LANDING, 'fiddle -> fiddle
        noun = bool(src_info and w[:1].isupper() and src_info.maybe_common_noun(w, source, target)) if w else False
        if w and (is_source_word(w, source, target) or noun):
            out.append(w)
    return out


def source_runs(text, source="en", target="tr", src_info: SourceInfo | None = None):
    """Spans of adjacent words that are source-language (or ALL-CAPS next to one): ``THE LANDING``."""
    runs, cur = [], []

    def good(m):
        w = m.group(0)
        return src_word(w) or (w.isupper() and len(w) >= 2)

    def src_word(w):
        noun = bool(src_info and w[:1].isupper() and src_info.maybe_common_noun(w, source, target))
        return is_source_word(w, source, target) or noun

    def close():
        if cur and any(src_word(x.group(0)) for x in cur):
            runs.append((cur[0].start(), cur[-1].end()))

    for m in re.finditer(r"[A-Za-z]+", text):
        if good(m) and (not cur or not text[cur[-1].end():m.start()].strip()):
            cur.append(m)
        else:
            close()
            cur = [m] if good(m) else []
    close()
    return runs


def _retranslate(text, engines):
    for e in engines:
        try:
            r = e.translate_batch([text])[0]
        except Exception:
            continue
        if r and r.strip():
            yield r.strip()


def qa_tree(tree, engines, source="en", target="tr", log=None, src_info: SourceInfo | None = None) -> dict:
    """Retranslate text nodes that still contain source-language words; word-level as last resort."""
    stats = {"nodes_checked": 0, "nodes_fixed": 0, "nodes_left": 0, "words_left": 0}
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    body = root.find(_q("body"))
    if body is None or zipf_frequency is None:
        return stats
    for el in body.iter():
        if not isinstance(el.tag, str) or _local(el.tag) in ("script", "style", "pre", "code"):
            continue
        for attr in ("text", "tail"):
            s = getattr(el, attr)
            if not s or not s.strip():
                continue
            stats["nodes_checked"] += 1
            bad = leftover_words(s, source, target, src_info)
            if not bad:
                continue
            lead, trail = s[: len(s) - len(s.lstrip())], s[len(s.rstrip()):]
            cur = s
            for r in _retranslate(s.strip(), engines):
                if len(leftover_words(r, source, target, src_info)) < len(leftover_words(cur, source, target, src_info)):
                    cur = lead + r + trail
                if not leftover_words(cur, source, target, src_info):
                    break
            for a, b in reversed(source_runs(cur, source, target, src_info)):
                phrase = cur[a:b]
                caps = phrase.isupper()
                lower_first = caps or phrase[:1].isupper()      # MT keeps capitalised words as names
                for r in _retranslate(phrase.lower() if lower_first else phrase, engines):
                    if caps:
                        r = r.replace("i", "İ").upper() if target == "tr" else r.upper()
                    elif phrase[:1].isupper() and r:
                        r = ("İ" if target == "tr" and r[0] == "i" else r[0].upper()) + r[1:]
                    lw = leftover_words
                    fewer = len(lw(r, source, target, src_info)) < len(lw(phrase, source, target, src_info))
                    if r.lower() != phrase.lower() and fewer:
                        cur = cur[:a] + r.rstrip(".") + cur[b:]
                        break
            setattr(el, attr, cur)
            left = leftover_words(cur, source, target, src_info)
            if left:
                stats["nodes_left"] += 1
                stats["words_left"] += len(left)
                if log is not None:
                    log.append({"text": cur.strip()[:200], "words": left[:10]})
            else:
                stats["nodes_fixed"] += 1
    return stats


def qa_epub(path, engines, source="en", target="tr", skip=lambda name, raw: False, src_info: SourceInfo | None = None) -> dict:
    """Run :func:`qa_tree` on every XHTML document of ``path`` (rewritten in place)."""
    total = {"nodes_checked": 0, "nodes_fixed": 0, "nodes_left": 0, "words_left": 0, "left": []}
    with zipfile.ZipFile(path) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    out = []
    for info, raw in entries:
        if info.filename.endswith((".xhtml", ".html", ".htm")) and b"<nav" not in raw and not skip(info.filename, raw):
            tree = etree.fromstring(raw, etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False))
            log = []
            st = qa_tree(tree, engines, source, target, log, src_info)
            for k in ("nodes_checked", "nodes_fixed", "nodes_left", "words_left"):
                total[k] += st[k]
            total["left"] += [{"doc": info.filename, **x} for x in log]
            if st["nodes_fixed"] or st["nodes_left"]:
                raw = etree.tostring(tree, xml_declaration=True, encoding="utf-8")
        out.append((info, raw))
    with zipfile.ZipFile(path, "w") as z:
        for info, raw in out:
            ctype = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            z.writestr(zipfile.ZipInfo(info.filename, info.date_time), raw, compress_type=ctype)
    return total
