"""Garbled-translation detection and back-translation candidate choice (epub_tr.quality)."""
import pytest

from epub_tr import quality, textfix
from epub_tr.engines.base import Engine

needs_wf = pytest.mark.skipif(not textfix.have_wordfreq(), reason="wordfreq not installed")
SRC = "It is often the case that a boat is stove, its crew being picked up by another boat."
BAD = "It çoğu zaman durum böyledir a tekne sobadır, mürettebatı, başka bir tekne tarafından alınıyor."
GOOD = "Çoğu zaman bir tekne batar ve mürettebatı başka bir tekne tarafından kurtarılır."


@needs_wf
def test_flags():
    assert "leftover" in quality.flags(SRC, BAD)
    assert quality.flags(SRC, GOOD) == []
    assert "repeat" in quality.flags("He walked down the long road home.", "yürüdü yürüdü yürüdü yürüdü eve doğru")
    assert "length" in quality.flags(SRC, "Tekne.")


class Fwd(Engine):
    name = "fwd"

    def translate_batch(self, texts):
        return [GOOD if t == SRC else t for t in texts]


class Back(Engine):
    name = "back"

    def translate_batch(self, texts):
        return ["Often a boat is stove and its crew is picked up by another boat." if t == GOOD else t for t in texts]


class Seg:
    def __init__(self, src, tr):
        self.uid, self.source, self.translation = "0:1", src, tr


@needs_wf
def test_improve_segments_picks_best_by_back_translation():
    seg = Seg(SRC, BAD)
    st = quality.improve_segments([seg], [Fwd()], Back(), workers=1)
    assert st == {"checked": 1, "flagged": 1, "replaced": 1} and seg.translation == GOOD


@needs_wf
def test_markup_preserving_candidate_preferred():
    src = "He said <g1>no</g1> to the man who had asked him twice."
    cur = "Adama <g1>hayır</g1> dedi, ona iki kez sormuştu."
    assert quality.flags(src, cur) == []
