"""Encode XHTML block elements into compact placeholder strings and back.

Inline markup is replaced by numbered placeholder tags so that translation
engines only see short, neutral tags:

    <p>He said <i>no</i>.<br/>Then...</p>   ->   'He said <g1>no</g1>.<x2/>Then...'

``g`` tags wrap content (i, em, b, span, a ...), ``x`` tags are empty
elements (br, img, empty anchors).  After translation the string is parsed
again and the original elements (with all attributes) are rebuilt.
"""
from __future__ import annotations

import copy
import html
import re
from dataclasses import dataclass, field

TOKEN_RE = re.compile(r"<\s*(/?)\s*([gxGX])\s*(\d+)\s*(/?)\s*>")
WS_RE = re.compile(r"\s+")
# Any other tag-looking thing an engine may have invented (e.g. <i>, </em>)
STRAY_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9:-]*(\s[^<>]*)?/?>")


class TagMismatch(ValueError):
    """Placeholders in the translation do not match the source."""


def localname(tag) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class Encoded:
    text: str
    tagmap: dict = field(default_factory=dict)  # id -> (kind, element-copy-without-children)

    @property
    def has_tags(self) -> bool:
        return bool(self.tagmap)

    def plain(self) -> str:
        """Text without any placeholder tags (for engines that cannot keep tags)."""
        # empty elements (<br/>, <img/>) separate words; wrapping tags do not
        text = TOKEN_RE.sub(lambda m: " " if m.group(2).lower() == "x" else "", self.text)
        return html.unescape(WS_RE.sub(" ", text)).strip()


def encode(el) -> Encoded:
    tagmap: dict[int, tuple[str, object]] = {}
    counter = [0]

    def shallow(ch):
        c = copy.copy(ch)
        for sub in list(c):
            c.remove(sub)
        c.text = None
        c.tail = None
        return c

    def walk(e) -> str:
        parts = []
        if e.text:
            parts.append(_esc(e.text))
        for ch in e:
            if not isinstance(ch.tag, str):  # comments / PIs are dropped
                if ch.tail:
                    parts.append(_esc(ch.tail))
                continue
            counter[0] += 1
            n = counter[0]
            if len(ch) == 0 and not (ch.text or "").strip():
                tagmap[n] = ("x", shallow(ch))
                parts.append(f"<x{n}/>")
            else:
                tagmap[n] = ("g", shallow(ch))
                parts.append(f"<g{n}>{walk(ch)}</g{n}>")
            if ch.tail:
                parts.append(_esc(ch.tail))
        return "".join(parts)

    raw = walk(el)
    text = WS_RE.sub(" ", raw).strip()
    return Encoded(text=text, tagmap=tagmap)


def _append_text(parent, text: str):
    if not text:
        return
    if len(parent):
        last = parent[-1]
        last.tail = (last.tail or "") + text
    else:
        parent.text = (parent.text or "") + text


def _clean_text(s: str) -> str:
    s = STRAY_TAG_RE.sub("", s)
    return html.unescape(s)


def validate(translated: str, enc: Encoded) -> None:
    """Raise TagMismatch if the placeholder structure is not identical."""
    stack: list[int] = []
    seen: list[int] = []
    for m in TOKEN_RE.finditer(translated):
        closing, kind, num, selfclose = m.group(1), m.group(2).lower(), int(m.group(3)), m.group(4)
        if num not in enc.tagmap or enc.tagmap[num][0] != kind:
            raise TagMismatch(f"unknown placeholder {m.group(0)}")
        if kind == "x":
            seen.append(num)
            continue
        if closing:
            if not stack or stack[-1] != num:
                raise TagMismatch(f"unbalanced {m.group(0)}")
            stack.pop()
        else:
            if selfclose:
                raise TagMismatch(f"self-closed g tag {m.group(0)}")
            stack.append(num)
            seen.append(num)
    if stack:
        raise TagMismatch("unclosed placeholders")
    if sorted(seen) != sorted(enc.tagmap):
        raise TagMismatch(f"placeholders {sorted(seen)} != {sorted(enc.tagmap)}")


def _clear(el):
    for ch in list(el):
        el.remove(ch)
    el.text = None


def decode_into(el, translated: str, enc: Encoded, strict: bool = True) -> bool:
    """Replace the children of ``el`` with the translated content.

    Returns True if markup was fully restored, False if the lenient
    fallback (plain text + preserved anchors) was used.
    """
    translated = translated.strip()
    try:
        validate(translated, enc)
        ok = True
    except TagMismatch:
        if strict:
            raise
        ok = False

    _clear(el)
    if ok:
        stack = [el]
        pos = 0
        for m in TOKEN_RE.finditer(translated):
            _append_text(stack[-1], _clean_text(translated[pos:m.start()]))
            pos = m.end()
            closing, kind, num = m.group(1), m.group(2).lower(), int(m.group(3))
            if kind == "x":
                stack[-1].append(copy.copy(enc.tagmap[num][1]))
            elif closing:
                stack.pop()
            else:
                new = copy.copy(enc.tagmap[num][1])
                stack[-1].append(new)
                stack.append(new)
        _append_text(stack[-1], _clean_text(translated[pos:]))
        return True

    # Lenient: keep empty elements and anything carrying an id (link targets),
    # then the plain translated text.
    for kind, node in enc.tagmap.values():
        if kind == "x" or node.get("id"):
            n = copy.copy(node)
            el.append(n)
    _append_text(el, _clean_text(TOKEN_RE.sub("", translated)).strip())
    return False
