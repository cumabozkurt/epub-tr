"""Book-title cleanup for translated metadata: keep only the book name (+ volume), like a printed book.

``short_title(translated, source, target)``
  * cuts subtitles after ':' ';' ' — ' and ", or ..." style alternatives (in source and translation),
  * drops edition words ("Complete", "A Novel", "Illustrated", Turkish "Tamamlandı", "Bir Roman" ...),
  * re-appends a normalised volume/part taken from the source title ("Cilt 2, Kısım 3" for Turkish).
"""
from __future__ import annotations
import re

_NUM = r"([ivxlc]+|\d+|one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|fourth|fifth|sixth)"
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
_LABELS = {"tr": ("Cilt", "Kitap", "Kısım"), "de": ("Band", "Buch", "Teil"), "fr": ("Tome", "Livre", "Partie"),
           "es": ("Tomo", "Libro", "Parte")}
_JUNK = {"tr": r"Tamamlandı|Tam Metin|Bir Roman|Roman|Resimli|Kısaltılmamış|Açıklamalı",
         "en": r"Complete|Unabridged|Illustrated|Annotated|A Novel|A Romance|A Tale"}
_VOL_TR = r"(?:Cilt|Kitap|Kısım|Bölüm|Cild|Volume|Vol\.?|Part|Book)\s+[\dIVXLC]+"


def _num(s: str) -> int | None:
    s = s.lower()
    if s.isdigit():
        return int(s)
    if s in _WORDS:
        return _WORDS[s]
    if not re.fullmatch(r"[ivxlc]+", s):
        return None
    v = 0
    for i, c in enumerate(s):
        v += -_ROMAN[c] if i + 1 < len(s) and _ROMAN[s[i + 1]] > _ROMAN[c] else _ROMAN[c]
    return v


def volume(source: str, target: str = "tr") -> str | None:
    """'Oliver Twist, Vol. 2 (of 3)' -> 'Cilt 2'; 'Don Quixote, Volume 2, Part 34' -> 'Cilt 2, Kısım 34'."""
    labels = _LABELS.get(target, ("Vol.", "Book", "Part"))
    out = []
    for kw, lab in ((r"volume|vol\.?|tome|band", labels[0]), (r"book", labels[1]), (r"part", labels[2])):
        m = re.search(r"\b(?:" + kw + r")\s+" + _NUM + r"\b(?!\s+of\s+the\s+\w+\s+\w+)", source, re.I)
        if m and _num(m.group(1)):
            out.append(f"{lab} {_num(m.group(1))}")
    return ", ".join(out) or None


def _cut(t: str) -> str:
    t = re.split(r"\s*[:;]\s*|\s+[—–]\s+|,\s+or,?\s+|,\s*(?:veya|ya da|yahut)\s+", t)[0]
    return t.strip(" ,.-—–")


def short_title(translated: str, source: str = "", target: str = "tr") -> str:
    t = re.sub(r"\s+", " ", translated or "").strip()
    junk = "|".join(x for x in (_JUNK.get(target), _JUNK["en"]) if x)
    for _ in range(3):
        t = re.sub(r"\s*[-—–,:]*\s*\(?\s*" + _VOL_TR + r"(?:\s*\(?\s*/?\s*(?:of\s*)?\d*\s*\)?)?\s*\)?\s*$", "", t, flags=re.I)
        t = re.sub(r"\s*[-—–,]*\s*\b(?:" + junk + r")\b\.?\s*$", "", t, flags=re.I).strip(" ,.-—–")
    t = re.sub(r"\s*\[[^\]]*\]?\s*$", "", t)
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
    t = _cut(t) or t
    v = volume(source, target) if source else None
    return f"{t} - {v}" if v and t else t
