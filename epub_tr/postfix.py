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
