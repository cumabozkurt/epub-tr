"""Pre-translation clean-ups and leftover-language QA (epub_tr.textfix)."""
import pytest
from lxml import etree

from epub_tr import textfix
from epub_tr.engines.base import Engine

XH = "http://www.w3.org/1999/xhtml"
needs_wf = pytest.mark.skipif(not textfix.have_wordfreq(), reason="wordfreq not installed")


def doc(body):
    return etree.fromstring(f'<html xmlns="{XH}"><body>{body}</body></html>'.encode())


def body_xml(tree):
    return etree.tostring(tree.find(f"{{{XH}}}body"), encoding="unicode")


def test_pre_poem_becomes_paragraph_with_breaks():
    t = doc("<pre>\n   Fury said to a\n     mouse, That he\n   met in the house,\n</pre>")
    assert textfix.preprocess_tree(t, words=False)
    xml = body_xml(t)
    assert "<pre" not in xml and 'class="pre-poem"' in xml
    assert xml.count("<br/>") == 2 and "Fury said to a" in xml and "met in the house," in xml


def test_pre_with_code_is_kept():
    t = doc("<pre><code>x = 1;\nprint(x);</code></pre><pre>if a == b:\n  return {};\nfoo();</pre>")
    textfix.preprocess_tree(t, words=False)
    assert body_xml(t).count("<pre") == 2


def test_pre_inline_markup_lines():
    t = doc("<pre>\n<i>Alice's Right Foot, Esq.,\n  Hearthrug,</i>\n  (<i>with love</i>).\n</pre>")
    textfix.preprocess_tree(t, words=False)
    xml = body_xml(t)
    assert "<i>Alice's Right Foot, Esq.,<br/> Hearthrug,</i>" in xml


@needs_wf
@pytest.mark.parametrize("src,want", [
    ("Beau—ootiful", "Beautiful"),
    ("e—e—evening", "evening"),
    ("beauti—FUL", "beautiful"),
    ("W—what", "What"),
])
def test_stretched_words(src, want):
    assert textfix.fix_stretched(src) == want


@needs_wf
@pytest.mark.parametrize("tok", ["said—and", "blue—grey", "I—I", "gone—gone", "well—known"])
def test_real_dash_compounds_untouched(tok):
    assert textfix.fix_stretched(tok) == tok


@needs_wf
def test_document_vocabulary_guides_choice():
    t = doc("<p>Beautiful Soup, so rich and green! Soup of the evening.</p><p>Soo—oop of the e—e—evening!</p>")
    textfix.preprocess_tree(t)
    assert "Soup of the evening!" in body_xml(t)


@needs_wf
def test_word_broken_across_br_is_joined():
    t = doc("<p>Who would not give all else for two p<br/>ennyworth only of beautiful Soup?<br/>Next line</p>")
    textfix.preprocess_tree(t)
    xml = body_xml(t)
    assert "two pennyworth only" in xml and xml.count("<br/>") == 1


def test_strip_boilerplate():
    t = doc('<section id="pg-header"><p>The Project Gutenberg eBook</p></section>'
            '<p>*** START OF THE PROJECT GUTENBERG EBOOK X ***</p><p>Story.</p>'
            '<footer class="pg-boilerplate"><h2>THE FULL PROJECT GUTENBERG LICENSE</h2></footer>')
    textfix.preprocess_tree(t, pre=False, words=False, boilerplate=True)
    assert "Gutenberg" not in body_xml(t) and "Story." in body_xml(t)


@needs_wf
def test_leftover_detection_tr():
    assert textfix.leftover_words("Kral aceleyle not defterini kapattı ve Alice güldü.") == []
    assert textfix.leftover_words("Güzel Çorba, the evening soup!") == ["the", "evening", "soup"]


class FixEngine(Engine):
    name = "fix"

    def translate_batch(self, texts):
        return [t.replace("the evening soup", "akşam çorbası").replace("soup", "çorba") for t in texts]


@needs_wf
def test_qa_retranslates_leftovers(tmp_path):
    t = doc("<p>Güzel Çorba, the evening soup!</p><p>Tamamen Türkçe.</p>")
    st = textfix.qa_tree(t, [FixEngine()])
    assert st["nodes_fixed"] == 1 and st["nodes_left"] == 0
    assert "akşam çorbası" in body_xml(t)


@needs_wf
@pytest.mark.parametrize("tok", ["depression—a", "tendency—what", "it—I"])
def test_dash_between_words_untouched(tok):
    assert textfix.fix_stretched(tok) == tok


class CapsEngine(Engine):
    name = "caps"

    def translate_batch(self, texts):
        return [{"the landing": "iniş"}.get(t, t) for t in texts]


@needs_wf
def test_qa_handles_all_caps_phrase_with_suffix():
    t = doc("<p>İlk THE LANDING'i takın</p>")
    st = textfix.qa_tree(t, [CapsEngine()])
    assert st["nodes_left"] == 0 and "İNİŞ'i" in body_xml(t)
