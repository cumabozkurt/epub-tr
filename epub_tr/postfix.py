from __future__ import annotations

"""Post-translation repairs on content xhtml (bytes->bytes):
 1 Roman numerals mangled by MT (I.->BEN., Kitap I->KİTAP İ)
 2 inner title page h1 -> verified Turkish title
 3 leaked page-anchor markers (pg_i, pg104, pg_xhangi)
 4 English lines on source title page (detection; caller retranslates)"""
import re

ROM=r"[IVXLCDM]+"
LBL=r"(?:K[İI]TAP|Kitap|kitap|B[ÖO]L[ÜU]M|Bölüm|bölüm|C[İI]LT|Cilt|cilt|KISIM|Kısım|kısım|PERDE|Perde|perde|SAHNE|Sahne|sahne|KANTO|Kanto|ŞARKI|Şarkı|MEKTUP|Mektup|SEFER|Sefer|FASIL|Fasıl|EK|Ek|Şek\.|Şekil|ŞEKİL|Fig\.|Levha|LEVHA|No\.)"
_ROMI=re.compile(r"^(?=[IVXLCDMİ]+$)(?=.*İ)[IVXLCDMİ]+$")
def _rom_tok(t):
    u=t.replace("İ","I")
    return u if re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})",u) and u else None
def fix_roman(s):
    n=0
    def lab(m):
        nonlocal n
        r=_rom_tok(m.group(2))
        if r is None:
            if m.group(2) in ("BEN","Ben","ben"): r="I"
            else: return m.group(0)
        if r!=m.group(2): n+=1
        return m.group(1)+r+m.group(3)
    s=re.sub(rf"(\b{LBL}\s+)([IVXLCDMİ]+|BEN|Ben)(\b)",lab,s)
    # line/cell-initial "BEN." / "İİ." used as enumerators
    def ini(m):
        nonlocal n
        t=m.group(2); r="I" if t=="BEN" else _rom_tok(t)
        if r is None or r==t: return m.group(0)
        n+=1; return m.group(1)+r+m.group(3)
    s=re.sub(r"(^\s*)(BEN|[IVXLCDMİ]*İ[IVXLCDMİ]*)(\.\s)",ini,s)
    # standalone roman tokens containing dotted İ followed by "." (e.g. "İİ.", "Vİ.")
    def alone(m):
        nonlocal n
        r=_rom_tok(m.group(1))
        if r is None or len(m.group(1))<2: return m.group(0)
        n+=1; return r+m.group(2)
    s=re.sub(r"(?<![\wÇĞİÖŞÜçğıöşü])([IVXLCDMİ]*İ[IVXLCDMİ]*)(\.)",alone,s)
    return s,n
PG=re.compile(r"^\s*\[?\s*(?:pg|Pg|PG)_?(?:[ivxlcdm]+|\d+)\s*\]?\s*$")
PGGLUE=re.compile(r"\bpg_(?:[ivxlcdm]+|\d+)(?=[A-Za-zÇĞİÖŞÜçğıöşü])|\bpg_?(?:[ivxlcdm]+|\d+)\b|\bpg_(?=[A-Za-zÇĞİÖŞÜçğıöşü])")
def fix_pg(s):
    s2=PGGLUE.sub("",s); return s2,(s2!=s)
def upper_tr(s): return s.replace("i","İ").replace("ı","I").upper()
def process(raw,title=None,first=False):
    """returns (bytes, stats dict)"""
    from lxml import etree
    XH="http://www.w3.org/1999/xhtml"
    t=etree.fromstring(raw,etree.XMLParser(recover=True,huge_tree=True,resolve_entities=False))
    st={"roman":0,"pg":0,"title":0}
    body=t.find(f"{{{XH}}}body")
    if body is None: return raw,st
    for ht in t.iter(f"{{{XH}}}title"):
        if ht.text:
            v,c=fix_pg(ht.text); ht.text=v.strip(); st["pg"]+=c
    for el in list(body.iter()):
        if not isinstance(el.tag,str): continue
        tag=el.tag.split("}")[-1]
        if tag in ("script","style"): continue
        # page-number marker elements
        cls=(el.get("class") or "")
        if el.text and PG.match(el.text) and (re.search(r"marginal|pagenum|page|pgnum",cls) or len(el)==0 and tag in("span","a")):
            el.text=None; st["pg"]+=1
        for a in ("text","tail"):
            v=getattr(el,a)
            if not v: continue
            v2,c=fix_pg(v); st["pg"]+=c
            v3,r=fix_roman(v2); st["roman"]+=r
            if v3!=v: setattr(el,a,v3)
    if first and title:
        h=None
        for e in body.iter(f"{{{XH}}}h1"):
            if e.get("id")=="pgepubid00000": h=e;break
        if h is None: h=next(body.iter(f"{{{XH}}}h1"),None)
        if h is not None:
            old="".join(h.itertext()).strip()
            letters=[c for c in old if c.isalpha()]
            caps=letters and sum(c.isupper() for c in letters)>0.7*len(letters)
            new=upper_tr(title) if caps else title
            if re.sub(r"\W","",old.lower())!=re.sub(r"\W","",new.lower()):
                tail=h.tail
                for c in list(h): h.remove(c)
                h.text=new; h.tail=tail; st["title"]=1
    return etree.tostring(t,xml_declaration=True,encoding="utf-8"),st
def scan(raw):
    """count issues without modifying"""
    s=re.sub(r"<(?!/?(?:p|td|li|h\d|div|br)\b)[^>]*>","",raw.decode("utf-8","replace"))
    s=re.sub(r"<[^>]*>",">",s)
    return {"roman":len(re.findall(r"(?:^|>)\s*BEN\.\s|\b(?:K[İI]TAP|BÖLÜM|CİLT|KISIM|PERDE|SAHNE|Kitap|Bölüm|Cilt|Kısım|Perde|Sahne)\s+(?:[IVXLC]*İ[IVXLCİ]*|BEN)\b|Şek\.\s*BEN\b",s,re.M)),
            "pg":len(re.findall(r">\s*pg_?(?:[ivxlcdm]+|\d+)\s*<|\bpg_(?:[ivxlcdm]+|\d+)|\bpg\d+\b",s))}

def _en_common(w):
    from wordfreq import zipf_frequency as Z
    return w.isascii() and len(w)>=3 and Z(w.lower(),"en")>=3.8 and Z(w.lower(),"en")-Z(w.lower(),"tr")>=1.5
def front_english(raw,translate=None):
    """first doc: text nodes before the first h2 containing >=2 common English words
    (title-case included, which the body QA treats as names). Retranslate when translate given."""
    from lxml import etree
    XH="http://www.w3.org/1999/xhtml"
    t=etree.fromstring(raw,etree.XMLParser(recover=True,huge_tree=True,resolve_entities=False))
    body=t.find(f"{{{XH}}}body"); hits=[]
    if body is None: return raw,hits
    for el in body.iter():
        if not isinstance(el.tag,str): continue
        if el.tag.split("}")[-1]=="h2": break
        if el.tag.split("}")[-1] in ("script","style"): continue
        for a in ("text","tail"):
            v=getattr(el,a)
            if not v: continue
            ws=re.findall(r"[A-Za-z]+",v)
            if sum(_en_common(w) for w in ws)>=2:
                hits.append(v.strip()[:120])
                if translate:
                    r=translate(v.strip().lower() if v.isupper() else v.strip())
                    if r: setattr(el,a,re.match(r"\s*",v).group(0)+(upper_tr(r) if v.isupper() else r)+(" " if v.endswith((" ","\n")) else ""))
        al=el.get("alt")
        if al and sum(_en_common(w) for w in re.findall(r"[A-Za-z]+",al))>=2:
            hits.append("alt:"+al[:100])
            if translate:
                r=translate(al)
                if r: el.set("alt",r)
    return (etree.tostring(t,xml_declaration=True,encoding="utf-8") if translate else raw),hits


# ---------------------------------------------------------------- person names from title/author
# Turkish/Islamic exonyms MT engines substitute for Western given names ("Abraham Lincoln" -> "İbrahim Lincoln").
EXONYMS = {
    "Abraham": ["İbrahim"], "Isaac": ["İshak"], "Jacob": ["Yakup", "Yakub"], "Joseph": ["Yusuf"],
    "Moses": ["Musa"], "David": ["Davut", "Davud"], "Solomon": ["Süleyman"], "John": ["Yahya", "Yuhanna"],
    "Mary": ["Meryem"], "Adam": ["Adem", "Âdem"], "Eve": ["Havva"], "Noah": ["Nuh"], "Jonah": ["Yunus"],
    "Job": ["Eyüp", "Eyyub"], "Elijah": ["İlyas"], "Aaron": ["Harun"], "Ishmael": ["İsmail"],
    "Zachary": ["Zekeriya"], "Zachariah": ["Zekeriya"], "Zechariah": ["Zekeriya"], "Daniel": ["Danyal"],
    "Michael": ["Mikail"], "Gabriel": ["Cebrail"], "Jesus": ["İsa"], "Joshua": ["Yeşu"], "Lot": ["Lut"],
    "Enoch": ["İdris"], "Ezra": ["Üzeyir"], "Elisha": ["Elyesa"], "Matthew": ["Matta"], "Peter": ["Petrus"],
    "Paul": ["Pavlus"], "Luke": ["Luka"], "Mark": ["Markos"], "Stephen": ["İstefanos"],
    "Alexander": ["İskender"], "Philip": ["Filip"], "Esther": ["Ester"], "Benjamin": ["Bünyamin"],
    "Samuel": ["Samuel"], "Saul": ["Talut"], "Jonathan": ["Yonatan"], "Elizabeth": ["Elisabet"],
}
_TRW = "A-Za-zÇĞİÖŞÜÂÎÛçğıöşüâîû"
_VOW = "aeıioöuüâîû"


def lower_tr(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def _silent_e(w):
    """English final silent e (Stone, Jane): pronounced with a consonant ending"""
    return len(w) > 3 and w[-1] == "e" and w[-2] not in _VOW and any(c in _VOW for c in w[:-2])


def _ends_vowel(w):
    w = lower_tr(w)
    if _silent_e(w):
        return False
    return bool(w) and (w[-1] in _VOW or (w[-1] == "y" and len(w) > 1 and w[-2] not in _VOW))


def _last_vowel(w):
    w = lower_tr(w)
    if _silent_e(w):
        w = w[:-1]
    if w.endswith("y") and len(w) > 1 and w[-2] not in _VOW:
        return "i"
    for c in reversed(w):
        if c in _VOW:
            return {"â": "a", "î": "i", "û": "u"}.get(c, c)
    return "e"


def reharmonize(name, suffix, old=""):
    """Re-attach a Turkish case suffix taken from `old` (e.g. İbrahim'in) to `name` (Abraham'ın)."""
    s = lower_tr(suffix)
    if not s:
        return s
    if old and _ends_vowel(old) and not _ends_vowel(name):
        if len(s) > 1 and s[0] in "nys" and s[1] in _VOW:
            s = s[1:]
    elif old and not _ends_vowel(old) and _ends_vowel(name) and s[0] in _VOW:
        s = ("n" if s[:2] in ("ın", "in", "un", "ün") else "y") + s
    if s[0] in "dt":
        s = ("t" if lower_tr(name)[-1:] in "çfhkpsşt" else "d") + s[1:]
    elif s[0] in "cç":
        s = ("ç" if lower_tr(name)[-1:] in "çfhkpsşt" else "c") + s[1:]
    out, lv = [], _last_vowel(name)
    for c in s:
        if c in "ıiuü":
            c = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[lv]
            lv = c
        elif c in "ae":
            c = "a" if lv in "aıou" else "e"
            lv = c
        out.append(c)
    return "".join(out)


_HONORS = ["Bay", "Bayan", "Matmazel", "Madam", "Sir", "Leydi", "Lord", "Kaptan", "Doktor", "Dr.", "Profesör",
           "Mösyö", "Küçük", "Genç", "Yaşlı"]


def _swap(new, old, apo, suf, upper):
    out = new + ((apo or "'") + reharmonize(new, suf, old) if suf else "")
    return upper_tr(out) if upper else out


def protect_names(s, names, forms=None):
    """Undo MT substitutions of person names that come from the book title/author.
    names: original name tokens to keep (e.g. {"Abraham", "Lincoln"}): their Turkish exonyms are put back.
    forms: {translated word: original name} for surnames that are ordinary words (e.g. {"Gri": "Grey"});
    replaced only right after another kept name or an honorific ("Agnes Gri" -> "Agnes Grey").
    returns (text, number of replacements)"""
    if not s or not (names or forms):
        return s, 0
    n = 0
    names = set(names or ())
    for nm in sorted(names):
        for ex in EXONYMS.get(nm, []):
            if ex == nm:
                continue
            for cand, upper in ((ex, False), (upper_tr(ex), True)):
                if cand not in s:
                    continue
                rx = re.compile(rf"(?<![{_TRW}]){re.escape(cand)}(?:(['’])([{_TRW}]+))?(?![{_TRW}])")

                def f(m, nm=nm, ex=ex, upper=upper):
                    nonlocal n
                    n += 1
                    return _swap(nm, ex, m.group(1), m.group(2), upper)
                s = rx.sub(f, s)
    if forms:
        keeps = sorted(names | set(forms.values()), key=len, reverse=True) + _HONORS
        for tw, nm in forms.items():
            for cand, upper in ((tw, False), (upper_tr(tw), True)):
                if cand not in s:
                    continue
                lead = "|".join(re.escape(upper_tr(x) if upper else x) for x in keeps)
                rx = re.compile(rf"(?<![{_TRW}])({lead})(\s+){re.escape(cand)}(?:(['’])([{_TRW}]+))?(?![{_TRW}])")

                def g(m, nm=nm, tw=tw, upper=upper):
                    nonlocal n
                    n += 1
                    return m.group(1) + m.group(2) + _swap(nm, tw, m.group(3), m.group(4), upper)
                s = rx.sub(g, s)
    return s, n


def protect_tree(t, names, forms=None):
    """apply protect_names to every text node / alt / title attribute of an lxml tree"""
    n = 0
    for el in t.iter():
        if not isinstance(el.tag, str) or el.tag.split("}")[-1] in ("script", "style"):
            continue
        for a in ("text", "tail"):
            v = getattr(el, a)
            if v:
                v2, c = protect_names(v, names, forms)
                if c:
                    setattr(el, a, v2)
                    n += c
        for at in ("alt", "title"):
            v = el.get(at)
            if v:
                v2, c = protect_names(v, names, forms)
                if c:
                    el.set(at, v2)
                    n += c
    return n


# ---------------------------------------------------------------- package metadata: <title>, nav, ncx
_HEAD_KEEP = {"Künye", "Kaynak"}


def _en_ratio(s):
    ws = [w for w in re.findall(r"[A-Za-z]{3,}", s or "")]
    if not ws:
        return 0.0
    return sum(_en_common(w) for w in ws) / len(ws)


def looks_english(s):
    """label/title text that is (mostly) untranslated English"""
    if not s or re.search(r"[çğıöşüÇĞİÖŞÜ]", s):
        return False
    ws = re.findall(r"[A-Za-z]{3,}", s)
    return bool(ws) and _en_ratio(s) >= 0.5


def _el_text(el):
    """visible text of an element: <br/> -> space, footnote refs dropped"""
    out = [el.text or ""]
    for c in el:
        if isinstance(c.tag, str):
            tag = c.tag.split("}")[-1]
            cls = c.get("class") or ""
            if tag == "br":
                out.append(" ")
            elif "noteref" in cls or "footnote" in cls or (
                    tag in ("sup", "a") and re.fullmatch(r"\s*\[?\d+\]?\s*", "".join(c.itertext()) or "")):
                pass
            elif tag not in ("script", "style"):
                out.append(_el_text(c))
        out.append(c.tail or "")
    return re.sub(r"\s+", " ", "".join(out)).strip()


_HTAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def _heading_for(doc, frag):
    """translated heading text for an anchor target (fragment id, or the first heading of the doc)"""
    body = next((e for e in doc.iter() if isinstance(e.tag, str) and e.tag.endswith("}body")), None)
    if body is None:
        return None
    if frag:
        tgt = next((e for e in body.iter() if isinstance(e.tag, str) and e.get("id") == frag), None)
        if tgt is None:
            return None
    else:
        tgt = body
    tag = tgt.tag.split("}")[-1]
    if tag in _HTAGS:
        return _el_text(tgt) or None
    for e in tgt.iter():
        if isinstance(e.tag, str) and e.tag.split("}")[-1] in _HTAGS:
            return _el_text(e) or None
    p = tgt.getparent()
    if p is not None and isinstance(p.tag, str) and p.tag.split("}")[-1] in _HTAGS:
        return _el_text(p) or None
    k = 0
    for e in tgt.itersiblings():
        if not isinstance(e.tag, str):
            continue
        k += 1
        if e.tag.split("}")[-1] in _HTAGS:
            return _el_text(e) or None
        if k >= 3 or _el_text(e):
            break
    return None


def _norm(s):
    return re.sub(r"[\W_]+", "", lower_tr(s or ""))


def meta_fix(files, title, names=None, forms=None, first=None):
    """Package-level Turkish metadata. files: {zip path: bytes} of the EPUB (at least OPF, xhtml, ncx).
    - every xhtml <head><title> (except Künye/Kaynak) -> book title; html lang en -> tr; PG generator meta removed
    - nav document: <title>, docTitle-like headings, aria-label; ncx: docTitle, xml:lang
    - TOC labels (nav + ncx) still in English, or stale (text no longer in the body), -> the translated body heading
    - person names from title/author restored in body text and TOC (protect_names)
    - first: zip path of the first content doc; its inner title h1 (id pgepubid00000) -> title
    returns ({path: new bytes} for changed files, stats)"""
    import os

    from lxml import etree
    P = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    XHN = "http://www.w3.org/1999/xhtml"
    st = {"titles": 0, "labels": 0, "labels_en_left": 0, "names": 0, "inner": 0, "meta": 0}
    out = {}
    trees = {}

    def tree(p):
        if p not in trees:
            b = files.get(p)
            if b is None:
                trees[p] = None
            else:
                try:
                    trees[p] = etree.fromstring(b, P)
                except Exception:
                    trees[p] = None
        return trees[p]
    dirty = set()
    opfp = None
    if "META-INF/container.xml" in files:
        try:
            c = etree.fromstring(files["META-INF/container.xml"], P)
            opfp = c.find(".//{*}rootfile").get("full-path")
        except Exception:
            opfp = None
    if not opfp:
        opfp = next((p for p in files if p.endswith(".opf")), None)
    base = os.path.dirname(opfp) if opfp else ""
    navp, ncxp = None, None
    if opfp and tree(opfp) is not None:
        opf = tree(opfp)
        for it in opf.iter("{*}item"):
            h = os.path.normpath(os.path.join(base, it.get("href", ""))).replace("\\", "/").lstrip("/")
            if "nav" in (it.get("properties") or ""):
                navp = h
            if it.get("media-type") == "application/x-dtbncx+xml":
                ncxp = h
        # English-only package metadata
        for m in list(opf.iter()):
            if not isinstance(m.tag, str):
                continue
            ln = m.tag.split("}")[-1]
            if ln == "subject" and m.text and looks_english(m.text):
                m.getparent().remove(m)
                st["meta"] += 1
            elif ln == "rights" and m.text and "public domain" in m.text.lower():
                m.text = "Kamu malı (ABD)"
                st["meta"] += 1
        for k in ("{http://www.w3.org/XML/1998/namespace}lang",):
            if opf.get(k) == "en":
                opf.set(k, "tr")
                st["meta"] += 1
        if st["meta"]:
            dirty.add(opfp)
    names = set(names or ())
    xhtml = [p for p in files if p.endswith((".xhtml", ".html", ".htm")) and files.get(p) is not None]
    for p in xhtml:
        t = tree(p)
        if t is None:
            continue
        ch = False
        for k in ("lang", "{http://www.w3.org/XML/1998/namespace}lang"):
            if t.get(k) == "en":
                t.set(k, "tr")
                ch = True
        for m in list(t.iter(f"{{{XHN}}}meta")):
            if "gutenberg" in (m.get("content") or "").lower() and (m.get("name") or "") in ("generator", "dtb:generator"):
                m.getparent().remove(m)
                ch = True
        for ht in t.iter(f"{{{XHN}}}title"):
            cur = (ht.text or "").strip()
            if title and cur not in _HEAD_KEEP and cur != title:
                ht.text = title
                st["titles"] += 1
                ch = True
        if p == navp:
            for nav in t.iter(f"{{{XHN}}}nav"):
                if (nav.get("aria-label") or "") and looks_english(nav.get("aria-label")):
                    nav.set("aria-label", "İçindekiler")
                    ch = True
            body = t.find(f"{{{XHN}}}body")
            if body is not None and title:
                for h in body.iter(*[f"{{{XHN}}}{x}" for x in _HTAGS]):
                    txt = _el_text(h)
                    if txt and looks_english(txt):
                        for c in list(h):
                            h.remove(c)
                        h.text = title
                        st["titles"] += 1
                        ch = True
        elif names or forms:
            c = protect_tree(t, names, forms)
            if c:
                st["names"] += c
                ch = True
        if p == first and title:
            body = t.find(f"{{{XHN}}}body")
            h = None
            if body is not None:
                h = next((e for e in body.iter(f"{{{XHN}}}h1") if e.get("id") == "pgepubid00000"), None)
            if h is not None:
                old = _el_text(h)
                letters = [c for c in old if c.isalpha()]
                caps = letters and sum(c.isupper() for c in letters) > 0.7 * len(letters)
                new = upper_tr(title) if caps else title
                if _norm(old) != _norm(new):
                    tail = h.tail
                    for c in list(h):
                        h.remove(c)
                    h.text = new
                    h.tail = tail
                    st["inner"] += 1
                    ch = True
        if ch:
            dirty.add(p)
    # TOC labels -> body headings
    bodytext = {}

    def btext(p):
        if p not in bodytext:
            t = tree(p)
            bodytext[p] = _norm("".join(t.itertext())) if t is not None else ""
        return bodytext[p]

    def resolve(src_doc, href):
        h, _, frag = href.partition("#")
        tp = os.path.normpath(os.path.join(os.path.dirname(src_doc), h)).replace("\\", "/").lstrip("/") if h else src_doc
        return tp, frag

    def new_label(src_doc, href, label):
        tp, frag = resolve(src_doc, href)
        t = tree(tp)
        if t is None:
            return None
        lab2 = protect_names(label, names, forms)[0] if (names or forms) else label
        en = looks_english(lab2)
        stale = bool(_norm(lab2)) and _norm(lab2) not in btext(tp)
        if not en and not stale:
            return lab2 if lab2 != label else None
        hd = _heading_for(t, frag)
        # stale Turkish labels are only replaced by a heading that is not much shorter (keeps label subtitles)
        if hd and len(hd) <= 250 and (en or (len(hd) >= 4 and len(hd) >= 0.6 * len(lab2)
                                             and not re.fullmatch(r"[IVXLCDM\d\W]+", hd))):
            return hd if hd != label else None
        if en:
            st["labels_en_left"] += 1
        return lab2 if lab2 != label else None
    if navp and tree(navp) is not None:
        t = tree(navp)
        for a in t.iter(f"{{{XHN}}}a"):
            href = a.get("href")
            if not href:
                continue
            lab = _el_text(a)
            nl = new_label(navp, href, lab)
            if nl:
                for c in list(a):
                    a.remove(c)
                a.text = nl
                st["labels"] += 1
                dirty.add(navp)
    if ncxp and tree(ncxp) is not None:
        t = tree(ncxp)
        if t.get("{http://www.w3.org/XML/1998/namespace}lang") == "en":
            t.set("{http://www.w3.org/XML/1998/namespace}lang", "tr")
            dirty.add(ncxp)
        for m in list(t.iter("{*}meta")):
            if m.get("name") == "dtb:generator" and "gutenberg" in (m.get("content") or "").lower():
                m.getparent().remove(m)
                dirty.add(ncxp)
        dt = t.find("{*}docTitle/{*}text")
        if dt is not None and title and (dt.text or "").strip() != title:
            dt.text = title
            st["titles"] += 1
            dirty.add(ncxp)
        for np_ in t.iter("{*}navPoint"):
            tx = np_.find("{*}navLabel/{*}text")
            ct = np_.find("{*}content")
            if tx is None or ct is None or not ct.get("src"):
                continue
            nl = new_label(ncxp, ct.get("src"), tx.text or "")
            if nl:
                tx.text = nl
                st["labels"] += 1
                dirty.add(ncxp)
    for p in dirty:
        out[p] = etree.tostring(trees[p], xml_declaration=True, encoding="utf-8")
    return out, st


def meta_fix_epub(src, dst, title, names=None, forms=None, first=None):
    """apply meta_fix to an EPUB file (src -> dst, may be the same path). returns stats or None if unchanged"""
    import os
    import zipfile
    z = zipfile.ZipFile(src)
    exts = (".xhtml", ".html", ".htm", ".ncx", ".opf", "container.xml")
    files = {n: z.read(n) for n in z.namelist() if n.endswith(exts)}
    if first is None:
        first = first_content_doc(files)
    out, st = meta_fix(files, title, names, forms, first)
    if not out:
        return None
    tmp = dst + ".mf.tmp"
    with zipfile.ZipFile(tmp, "w") as o:
        o.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for n in z.namelist():
            if n == "mimetype":
                continue
            o.writestr(z.getinfo(n), out.get(n) or z.read(n), compress_type=zipfile.ZIP_DEFLATED)
    z.close()
    os.replace(tmp, dst)
    return st


def first_content_doc(files):
    """zip path of the first spine document that is not a cover/colophon page"""
    import os

    from lxml import etree
    opfp = next((p for p in files if p.endswith(".opf")), None)
    if not opfp:
        return None
    opf = etree.fromstring(files[opfp])
    base = os.path.dirname(opfp)
    items = {it.get("id"): it for it in opf.iter("{*}item")}
    for ir in opf.iter("{*}itemref"):
        it = items.get(ir.get("idref"))
        if it is None or it.get("media-type") != "application/xhtml+xml":
            continue
        h = it.get("href", "")
        if ("cover" in (it.get("id") or "").lower() or "cover" in h.lower() or "wrap0000" in h
                or h in ("kunye.xhtml", "kaynak.xhtml")):
            continue
        return os.path.normpath(os.path.join(base, h)).replace("\\", "/").lstrip("/")
    return None
