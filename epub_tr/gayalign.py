"""Aligned repair of "eşcinsel" in finished books (old-sense gay/queer mistranslated by free MT).
Each eşcinsel in the book is matched to its dump segment (source/translation pairs written by epub-tr) by the
words around it; only then is it changed:
  source has gay/gaily/gaiety (old sense)  -> neşeli / şen.. / şenlik.. / neşeyle (postfix.fix_gay_tr)
  source has queer (and no gay)            -> tuhaf.. (case suffix re-harmonised)
  anything else (no match, modern-sense vocabulary, surname Gay) -> unchanged
undo=True also repairs words an earlier book-level pass turned into neşeli/şen.. where the source said queer.
Modern sources (author born 1930+) are skipped by the caller (bookmeta.modern_source)."""
import json, re
from lxml import etree
from . import postfix as P

GAY_SRC = re.compile(r"\b(?:gay(?:er|est|ly|ety|eties|ness)?|gai(?:ly|ety|eties))\b|\bgay[a-z]+", re.I)
QUEER_SRC = re.compile(r"\bqueer\w*", re.I)
MODERN = re.compile(r"\b(?:homosexual\w*|lesbian\w*|sodom\w*|pederast\w*|uranian\w*|inverts?\b"
                    r"|gay (?:rights|bar|community|liberation))", re.I)
SURNAME = re.compile(r"\b(?:Mr|Mrs|Miss|Ms|Dr|Madame|John|the)\.?\s+Gays?\b")
ES = P._GAY_TR   # (eşcinsel)(lik)?(suffix)
DONE = re.compile(r"(?<![A-Za-zÇĞİÖŞÜçğıöşüâîû])(neşeli|Neşeli|NEŞELİ|neşeyle|Neşeyle|NEŞEYLE|şen[a-zçğıöşü]*|Şen[a-zçğıöşü]*"
                  r"|ŞEN[A-ZÇĞİÖŞÜ]*)(?![A-Za-zÇĞİÖŞÜçğıöşüâîû])")
WORD = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüâîû0-9]+")
TAG = re.compile(r"<[^>]+>")


def _w(s):
    return [P.lower_tr(x) for x in WORD.findall(s)]


def _keys(text, a, b, k=3):
    pre, post = _w(text[:a])[-k:], _w(text[b:])[:k]
    return (("p",) + tuple(pre)) if len(pre) == k else None, (("n",) + tuple(post)) if len(post) == k else None


def load(dump):
    """key -> set of (class, original eşcinsel word)"""
    M = {}
    try:
        f = open(dump, encoding="utf-8")
    except OSError:
        return M
    for line in f:
        try:
            r = json.loads(line)
        except Exception:
            continue
        t = TAG.sub("", r.get("translation") or "")
        if "şcinsel" not in t and "ŞCİNSEL" not in t:
            continue
        s = TAG.sub("", r.get("source") or "")
        if MODERN.search(s):
            cls = "keep"
        elif GAY_SRC.search(SURNAME.sub("", s)):   # Mr. Gay, the Gays: a surname
            cls = "gay"
        elif QUEER_SRC.search(s):
            cls = "queer"
        else:
            cls = "keep"
        for m in ES.finditer(t):
            for key in _keys(t, m.start(), m.end()):
                if key:
                    M.setdefault(key, set()).add((cls, m.group(0)))
    return M


def _case(src, out):
    if src.isupper() and len(src) > 1:
        return P.upper_tr(out)
    return out[0].upper() + out[1:] if src[0].isupper() else out


def tuhaf(orig):
    m = ES.fullmatch(orig)
    w, lik, suf = m.groups() if m else (orig, "", "")
    s = P.lower_tr(suf or "")
    if lik:
        out = "tuhaflık" + P.reharmonize("tuhaflık", s, "eşcinsellik")
    elif s in ("ce", "çe"):
        out = "tuhafça"
    else:
        out = "tuhaf" + P.reharmonize("tuhaf", s, "eşcinsel")
    return _case(orig, out)


def _decide(M, text, a, b):
    hits = set()
    for key in _keys(text, a, b):
        if key and key in M:
            hits |= M[key]
    if len({c for c, _ in hits}) != 1:
        return None, None
    c = next(iter(hits))[0]
    origs = {o for _, o in hits}
    return c, (next(iter(origs)) if len(origs) == 1 else None)


def fix_tree(t, M, undo=False):
    """returns {"gay": n, "queer": n, "undo": n, "left": n}"""
    st = {"gay": 0, "queer": 0, "undo": 0, "left": 0}
    body = next((e for e in t.iter() if P._local(e) == "body"), None)
    if body is None or not M:
        return st
    leaves = [e for e in body.iter() if P._local(e) in P._BLOCKS
              and not any(P._local(c) in P._BLOCKS for c in e.iter() if c is not e)]
    for e in leaves:
        pieces = []   # (node, attr, start offset)
        buf = []
        pos = 0
        for x in e.iter():
            if not isinstance(x.tag, str):
                continue
            for a in ("text", "tail") if x is not e else ("text",):
                v = getattr(x, a)
                if v:
                    pieces.append((x, a, pos, v)); buf.append(v); pos += len(v)
        text = "".join(buf)
        if not ("şcinsel" in text or "ŞCİNSEL" in text or (undo and DONE.search(text))):
            continue
        edits = []   # (start, end, new)
        for m in ES.finditer(text):
            c, orig = _decide(M, text, m.start(), m.end())
            if c == "gay":
                edits.append((m.start(), m.end(), P.fix_gay_tr(m.group(0))[0], "gay"))
            elif c == "queer":
                edits.append((m.start(), m.end(), tuhaf(m.group(0)), "queer"))
            else:
                st["left"] += 1
        if undo:
            for m in DONE.finditer(text):
                c, orig = _decide(M, text, m.start(), m.end())
                if c == "queer" and orig and P.lower_tr(P.fix_gay_tr(orig)[0]) == P.lower_tr(m.group(0)):
                    edits.append((m.start(), m.end(), _case(m.group(0), tuhaf(P.lower_tr(orig))), "undo"))
        for a, b, new, kind in sorted(edits, reverse=True):
            for x, attr, p0, v in pieces:
                if p0 <= a and b <= p0 + len(v):
                    cur = getattr(x, attr)
                    setattr(x, attr, cur[:a - p0] + new + cur[b - p0:])
                    st[kind] += 1
                    break
    return st


def fix_files(files, dump, undo=False, skip=("kunye.xhtml", "kaynak.xhtml")):
    """files: {zip path: bytes}; returns ({changed path: bytes}, stats)"""
    M = load(dump)
    out, tot = {}, {"gay": 0, "queer": 0, "undo": 0, "left": 0}
    if not M:
        return out, tot
    par = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    for n, b in files.items():
        if not n.endswith((".xhtml", ".html", ".htm")) or n.endswith(skip):
            continue
        s = b.decode("utf-8", "ignore")
        if "şcinsel" not in s and "ŞCİNSEL" not in s and not (undo and ("neşe" in s or "şen" in s or "Şen" in s)):
            continue
        t = etree.fromstring(b, par)
        st = fix_tree(t, M, undo)
        for k in tot:
            tot[k] += st[k]
        if st["gay"] or st["queer"] or st["undo"]:
            out[n] = etree.tostring(t, xml_declaration=True, encoding="utf-8")
    return out, tot


def fix_epub(src, dump, dst=None, undo=False):
    """apply fix_files to an EPUB (dst defaults to src). returns stats"""
    import os
    import zipfile
    dst = dst or src
    z = zipfile.ZipFile(src)
    files = {n: z.read(n) for n in z.namelist() if n.endswith((".xhtml", ".html", ".htm"))}
    out, st = fix_files(files, dump, undo=undo)
    if out:
        tmp = dst + ".ga.tmp"
        with zipfile.ZipFile(tmp, "w") as o:
            o.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            for n in z.namelist():
                if n != "mimetype":
                    o.writestr(z.getinfo(n), out.get(n) or z.read(n), compress_type=zipfile.ZIP_DEFLATED)
        z.close()
        os.replace(tmp, dst)
    return st


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="aligned eşcinsel -> neşeli/tuhaf repair of a translated EPUB "
                                             "(needs the --dump JSONL written by `epub-tr translate`)")
    ap.add_argument("epub")
    ap.add_argument("dump")
    ap.add_argument("-o", "--output")
    ap.add_argument("--undo", action="store_true", help="also repair neşeli/şen.. an earlier pass made from 'queer'")
    a = ap.parse_args()
    print(json.dumps(fix_epub(a.epub, a.dump, a.output, a.undo)))
