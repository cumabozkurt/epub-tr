"""Placeholder encoding/decoding of inline markup (epub_tr.blocks)."""
import pytest
from lxml import etree

from epub_tr.blocks import TagMismatch, decode_into, encode, localname, validate

NS = "http://www.w3.org/1999/xhtml"


def el(xml, tag="p"):
    return etree.fromstring(f'<{tag} xmlns="{NS}" id="p1" class="c">{xml}</{tag}>')


def html(e):
    return etree.tostring(e, encoding="unicode")


def test_plain_text_has_no_tags():
    enc = encode(el("Just   some\n text."))
    assert enc.text == "Just some text." and not enc.has_tags and enc.plain() == "Just some text."


def test_nested_and_empty_elements():
    enc = encode(el('A <em>b <strong>c</strong></em> d<br/><img src="x.png" alt=""/> e'))
    assert enc.text == "A <g1>b <g2>c</g2></g1> d<x3/><x4/> e"
    assert [k for k, _ in enc.tagmap.values()] == ["g", "g", "x", "x"]
    assert enc.plain() == "A b c d e"


def test_entities_are_escaped_and_restored():
    e = el("Tom &amp; Jerry &lt;3")
    enc = encode(e)
    assert enc.text == "Tom &amp; Jerry &lt;3"
    assert enc.plain() == "Tom & Jerry <3"
    assert decode_into(e, "Tom &amp; Jerry &lt;3 sonsuza", enc)
    assert "Tom &amp; Jerry &lt;3 sonsuza" in html(e)


def test_comments_are_dropped_but_tail_kept():
    enc = encode(el("before<!-- note -->after"))
    assert enc.text == "beforeafter" and not enc.has_tags


def test_roundtrip_keeps_attributes_and_order():
    e = el('Go <a href="ch2.xhtml#x" class="l">there</a> <span lang="fr">vite</span>.')
    enc = encode(e)
    assert decode_into(e, "<g2>Çabuk</g2> <g1>oraya</g1> git.", enc)  # reordering is allowed
    out = html(e)
    assert out.index('lang="fr"') < out.index('href="ch2.xhtml#x"')
    assert 'class="l">oraya</a>' in out and e.get("id") == "p1" and e.get("class") == "c"


def test_tail_text_inside_nested_elements():
    e = el("<i>a <b>b</b> c</i> d")
    enc = encode(e)
    assert decode_into(e, "<g1>A <g2>B</g2> C</g1> D", enc)
    assert html(e).endswith("<i>A <b>B</b> C</i> D</p>")


def test_engine_whitespace_variants_in_tokens_are_accepted():
    e = el("x <i>y</i><br/>")
    enc = encode(e)
    assert decode_into(e, "X < g1 >Y</ g1 ><X2 />", enc)
    assert "<i>Y</i><br/>" in html(e)


@pytest.mark.parametrize("bad, why", [
    ("Merhaba", "missing"),
    ("<g1>a</g1><g1>b</g1>", "duplicate"),
    ("<g1>a", "unclosed"),
    ("a</g1>", "unbalanced"),
    ("<g1/>", "selfclosed"),
    ("<g1><x2/></g1><g9>z</g9>", "unknown"),
    ("<x1/><x2/>", "wrong kind"),
])
def test_validate_rejects(bad, why):
    enc = encode(el("<i>a</i><br/>"))
    with pytest.raises(TagMismatch):
        validate(bad, enc)


def test_validate_accepts_exact_structure():
    validate("<g1>a</g1><x2/>", encode(el("<i>a</i><br/>")))


def test_strict_decode_raises():
    e = el("<i>a</i>")
    with pytest.raises(TagMismatch):
        decode_into(e, "a", encode(e), strict=True)


def test_lenient_decode_keeps_ids_and_empty_elements():
    e = el('<a id="anchor"/>Hello <b>world</b><br/>')
    enc = encode(e)
    assert decode_into(e, "Merhaba <b>dünya</b> <g7>!</g7>", enc, strict=False) is False
    out = html(e)
    assert 'id="anchor"' in out and "<br/>" in out and "Merhaba dünya !" in out and "<b>" not in out


def test_stray_tags_from_engines_are_removed():
    e = el("<i>a</i> b")
    enc = encode(e)
    assert decode_into(e, "<g1>A</g1> <em>B</em>", enc)
    assert "<em>" not in html(e) and html(e).endswith("<i>A</i> B</p>")


def test_localname():
    assert localname("{%s}P" % NS) == "p" and localname("div") == "div" and localname(None) == ""
