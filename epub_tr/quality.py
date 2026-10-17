"""Segment-level quality check without an LLM (``--quality``).

Cheap heuristics flag likely garbled machine translations (abnormal length ratio, repeated words,
too few target-language words, leftover source words). For flagged segments the module asks the
MT engines again (whole segment, sentence by sentence when there is no inline markup) and keeps
the candidate whose back-translation is closest to the source.
"""
from __future__ import annotations

import difflib
import html
import re
from concurrent.futures import ThreadPoolExecutor

from . import textfix

TAG = re.compile(r"</?g\d+>|<x\d+/>")
SENT = re.compile(r"(?<=[.!?;:])\s+(?=[\"“‘'(A-Z])")
TARGET_CHARS = {"tr": set("çğıöşüÇĞİÖŞÜ")}
STRAY = {"en": re.compile(r"\b(It|a|an|is|to|in|of|by|as|or)\b")}


def plain(s: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", TAG.sub(" ", s or ""))).strip()


def words(s: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", (s or "").lower())


def target_ratio(text: str, source="en", target="tr") -> float:
    """Share of words that look like the target language (or names / short words)."""
    zf = textfix.zipf_frequency
    ws = re.findall(r"[^\W\d_]+", text)
    if not ws or zf is None:
        return 1.0
    chars = TARGET_CHARS.get(target, set())
    ok = sum(1 for w in ws if any(c in chars for c in w) or w[0].isupper() or len(w) <= 2
             or (zf(w.lower(), target) >= 2.5 and not textfix.is_source_word(w, source, target)))
    return ok / len(ws)


def flags(src: str, tgt: str, source="en", target="tr") -> list[str]:
    s, t = plain(src), plain(tgt)
    out = []
    if textfix.leftover_words(t, source, target):
        out.append("leftover")
    if len(s) < 25:
        return out
    ratio = len(t) / max(1, len(s))
    if ratio < 0.5 or ratio > 2.0:
        out.append("length")
    tw = words(t)
    if any(tw[i] == tw[i + 1] == tw[i + 2] for i in range(len(tw) - 2)):
        out.append("repeat")
    if len(tw) >= 6 and target_ratio(t, source, target) < 0.75:
        out.append("language")
    stray = STRAY.get(source)
    if stray and len(stray.findall(t)) >= 2 and "leftover" not in out:
        out.append("leftover")
    if t == s:
        out.append("same")
    return out


def back_score(src: str, cand: str, back) -> float:
    try:
        bt = back.translate_batch([plain(cand)])[0]
    except Exception:
        return 0.0
    return difflib.SequenceMatcher(None, words(plain(src)), words(bt)).ratio()


def _ask(engine, text):
    try:
        r = engine.translate_batch([text])[0]
        return r if r and r.strip() else None
    except Exception:
        return None


def candidates(src: str, current: str, engines) -> dict:
    out = {"current": current}
    has_tags = bool(TAG.search(src))
    for e in engines:
        if has_tags and not getattr(e, "supports_tags", True):
            continue
        r = _ask(e, src)
        if r:
            out[e.name] = r
        if not has_tags and e is engines[0]:
            parts = [x for x in SENT.split(src) if x.strip()]
            if len(parts) > 1:
                rs = [_ask(e, x) for x in parts]
                if all(rs):
                    out[e.name + "_sentences"] = " ".join(x.strip() for x in rs)
    return out


def best_candidate(src: str, current: str, engines, back, source="en", target="tr"):
    cands = candidates(src, current, engines)
    scores = {}
    for name, val in cands.items():
        fl = flags(src, val, source, target)
        pen = 0.15 * len([f for f in fl if f not in ("leftover", "same")])
        pen += 0.5 if "leftover" in fl else 0
        pen += 0.3 if "same" in fl else 0
        if TAG.search(src) and len(TAG.findall(val)) != len(TAG.findall(src)):
            pen += 0.3                                   # broken inline markup
        scores[name] = back_score(src, val, back) - pen
    name = max(scores, key=scores.get)
    return name, cands[name], scores


def improve_segments(segments, engines, back, source="en", target="tr", workers=4, log=None) -> dict:
    """Re-translate flagged segments in place. Returns stats."""
    todo = [s for s in segments if s.translation and flags(s.source, s.translation, source, target)]
    stats = {"checked": len(segments), "flagged": len(todo), "replaced": 0}

    def one(seg):
        return seg, best_candidate(seg.source, seg.translation, engines, back, source, target)

    with ThreadPoolExecutor(max(1, workers)) as ex:
        for seg, (name, val, _scores) in ex.map(one, todo):
            if name != "current" and val != seg.translation:
                if log is not None:
                    log.append({"uid": seg.uid, "old": plain(seg.translation), "new": plain(val), "pick": name})
                seg.translation = val
                stats["replaced"] += 1
    return stats
