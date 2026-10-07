"""Translation pipeline: batching, fallback chain, LLM chunking/glossary/polish, cache and resume."""
import pytest
from conftest import FailingEngine, FakeLLM, UpperMT

from epub_tr.cache import Cache
from epub_tr.engines.base import EngineUnavailable, RateLimited
from epub_tr.epub_io import Book
from epub_tr.pipeline import SEG_RE, Translator, detect_names, harmonize_toc


def doc_segments(book):
    return [list(d.segments) for d in book.documents if d.segments]


def content(book):
    return [s for d in book.documents if not d.is_nav for s in d.segments]


def run(book, engines, cache=None, **kw):
    tr = Translator(engines, cache, **kw)
    stats = tr.run(doc_segments(book))
    return tr, stats


# ------------------------------------------------------------------ MT
def test_mt_translates_everything_in_batches(epub_path):
    eng = UpperMT()
    with Book(epub_path) as b:
        tr, stats = run(b, [eng])
        segs = b.all_segments(include_toc=False)
        assert all(s.translation for s in segs)
        assert segs[1].translation == "DELLA COUNTED THE COINS <g1>THREE</g1> TIMES.<x2/>IT WAS ALL SHE HAD."
        assert all(sum(len(t) for t in batch) <= eng.max_chars or len(batch) == 1 for batch in eng.batches)
        assert stats.engine_segments["upper"] == len(segs) and not stats.failures


def test_fallback_chain_uses_next_engine(epub_path):
    broken, good = FailingEngine(), UpperMT()
    with Book(epub_path) as b:
        tr, stats = run(b, [broken, good], retries=2)
        assert all(s.engine == "upper" for s in b.all_segments(include_toc=False))
    assert broken.calls >= 2 and stats.failures["broken"] >= 2 and stats.engine_segments["upper"] > 0


def test_rate_limited_engine_falls_back(epub_path):
    with Book(epub_path) as b:
        _, stats = run(b, [FailingEngine(exc=RateLimited), UpperMT()], retries=1)
        assert all(s.translation for s in b.all_segments(include_toc=False))
    assert any("boom" in e for e in stats.errors)


def test_unavailable_engine_is_skipped_without_retries(epub_path):
    broken = FailingEngine(exc=EngineUnavailable)
    with Book(epub_path) as b:
        run(b, [broken, UpperMT()], retries=3)
        assert all(s.engine == "upper" for s in b.all_segments(include_toc=False))
    assert broken.calls == 1  # one unit (whole book fits max_chars), EngineUnavailable is never retried


def test_all_engines_failing_leaves_segments_untranslated(epub_path):
    with Book(epub_path) as b:
        _, stats = run(b, [FailingEngine()], retries=1)
        assert not any(s.translation for s in b.all_segments())
    assert stats.failures["broken"] > 0


def test_tagless_engine_gets_plain_text_and_titles_are_rewrapped(epub_path):
    class Plain(UpperMT):
        name = "plain"
        supports_tags = False
    eng = Plain()
    with Book(epub_path) as b:
        run(b, [eng])
        sent = [t for batch in eng.batches for t in batch]
        assert not any("<g" in t or "<x" in t for t in sent)
        nav = next(d for d in b.documents if d.is_nav)
        assert nav.segments[0].translation == "<g1>CHAPTER ONE</g1>"  # link text survives


def test_mt_result_count_mismatch_is_an_error(epub_path):
    class Short(UpperMT):
        name = "short"
        def translate_batch(self, texts):
            return super().translate_batch(texts)[:-1]
    with Book(epub_path) as b:
        _, stats = run(b, [Short(), UpperMT()], retries=1)
        assert all(s.translation for s in b.all_segments(include_toc=False))
    assert stats.failures["short"] > 0


# ------------------------------------------------------------------ LLM
def test_llm_chunks_context_and_glossary(epub_path):
    llm = FakeLLM()
    with Book(epub_path) as b:
        tr, stats = run(b, [llm], chunk_chars=60, context_paras=2, glossary={"Jim": "Cim"})
        segs = content(b)
        assert all(s.translation and s.translation.startswith("[tr] ") for s in segs)
    assert len(llm.prompts) > 3                                   # chunked
    system, first_user = llm.prompts[0]
    assert "Turkish" in system and "TDK" in system
    assert "Jim => Cim" in first_user                             # seed glossary sent
    assert any("PREVIOUS PASSAGE" in u for _, u in llm.prompts[1:])  # context passed on
    assert tr.glossary["Della"] == "Della"                        # glossary learnt from the model


def test_llm_missing_segments_are_retried(epub_path):
    llm = FakeLLM(drop={2})
    with Book(epub_path) as b:
        run(b, [llm], chunk_chars=10_000)
        assert all(s.translation for s in b.all_segments(include_toc=False))
    assert any('<seg id="1">' in u and u.count("<seg id=") == 1 for _, u in llm.prompts[1:])


def test_llm_without_seg_output_falls_back(epub_path):
    class Chatty(FakeLLM):
        name = "chatty"
        def complete(self, system, user):
            return "Sure! Here is your translation."
    with Book(epub_path) as b:
        _, stats = run(b, [Chatty(), UpperMT()], retries=1)
        assert all(s.engine == "upper" for s in b.all_segments(include_toc=False))
    assert any("no <seg>" in e for e in stats.errors)


def test_polish_pass(epub_path):
    llm = FakeLLM()
    with Book(epub_path) as b:
        _, stats = run(b, [llm], polish=True, chunk_chars=10_000)
        segs = content(b)
        b_all = b.all_segments(include_toc=False)
        assert all(s.translation.endswith("(polished)") for s in segs)
    assert stats.polished == len(b_all)  # nav labels are polished too, then harmonised


def test_dialogue_dash_rule_in_prompt():
    tr = Translator([FakeLLM()], None, dialogue="dash")
    assert "em dash" in tr.system
    assert "quotation marks" in Translator([FakeLLM()], None).system


def test_non_turkish_target_uses_generic_rules():
    tr = Translator([FakeLLM()], None, target="de")
    assert "German" in tr.system and "TDK" not in tr.system


# ------------------------------------------------------------------ cache / resume
def test_cache_resume_skips_engine(tmp_path, epub_path):
    cache = Cache(str(tmp_path / "c.sqlite3"))
    with Book(epub_path) as b:
        run(b, [UpperMT()], cache=cache, book_id="b1")
    second = UpperMT()
    with Book(epub_path) as b:
        _, stats = run(b, [second], cache=cache, book_id="b1")
        assert all(s.translation for s in b.all_segments(include_toc=False))
    assert second.batches == [] and stats.engine_segments["upper (cache)"] > 0 and cache.hits > 0


def test_llm_cache_resume_and_glossary_persistence(tmp_path, epub_path):
    path = str(tmp_path / "c.sqlite3")
    with Book(epub_path) as b:
        run(b, [FakeLLM()], cache=Cache(path), book_id="b1")
    again = FakeLLM()
    with Book(epub_path) as b:
        tr, _ = run(b, [again], cache=Cache(path), book_id="b1")
    assert again.prompts == [] and tr.glossary.get("Della") == "Della"


def test_partial_failure_is_resumed_later(tmp_path, epub_path):
    cache = Cache(str(tmp_path / "c.sqlite3"))

    class Flaky(UpperMT):
        name = "upper"
        def translate_batch(self, texts):
            if any("div" in t for t in texts):
                raise RateLimited("quota")
            return super().translate_batch(texts)

    with Book(epub_path) as b:
        run(b, [Flaky()], cache=cache, retries=1)
        failed = [s.source for s in b.all_segments(include_toc=False) if not s.translation]
    assert failed and any("div" in t for t in failed)
    later = UpperMT()
    with Book(epub_path) as b:
        run(b, [later], cache=cache)
        assert all(s.translation for s in b.all_segments(include_toc=False))
    resent = [t for batch in later.batches for t in batch]
    assert sorted(resent) == sorted(failed)  # only the missing ones went to the engine again


def test_cache_disabled(tmp_path):
    c = Cache(str(tmp_path / "x.sqlite3"), enabled=False)
    c.put("e", "m", "mt", "en", "tr", "a", "b")
    assert c.get("e", "m", "mt", "en", "tr", "a") is None and c.load_glossary("b") == {}


def test_cache_keys_separate_engine_model_stage_and_languages(tmp_path):
    c = Cache(str(tmp_path / "x.sqlite3"))
    c.put("e", "m1", "llm", "en", "tr", "hello", "merhaba")
    assert c.get("e", "m1", "llm", "en", "tr", "hello") == "merhaba"
    for args in (("e", "m2", "llm", "en", "tr"), ("e", "m1", "llm-polished", "en", "tr"),
                 ("e", "m1", "llm", "en", "de"), ("x", "m1", "llm", "en", "tr")):
        assert c.get(*args, "hello") is None
    c.save_glossary("book", {"Della": "Della"})
    assert Cache(str(tmp_path / "x.sqlite3")).load_glossary("book") == {"Della": "Della"}


def test_default_cache_path_honours_env(tmp_path, monkeypatch):
    from epub_tr.cache import default_cache_path
    monkeypatch.setenv("EPUB_TR_CACHE", str(tmp_path / "deep" / "dir" / "c.sqlite3"))
    p = default_cache_path()
    assert p.endswith("c.sqlite3") and (tmp_path / "deep" / "dir").is_dir()


# ------------------------------------------------------------------ helpers
def test_seg_regex_variants():
    out = 'x <seg id="1">Bir</seg>\n<SEG id=2>İki <g1>a</g1></SEG> <seg id = "3" >\nÜç\n</seg>'
    assert [(i, t.strip()) for i, t in SEG_RE.findall(out)] == [("1", "Bir"), ("2", "İki <g1>a</g1>"), ("3", "Üç")]


def test_detect_names():
    names = detect_names(["Then Della cried. And Della laughed.", "So did Jim and then Jim smiled. The end."])
    assert "Della" in names and "Jim" in names and "The" not in names


def test_rewrap_strips_spurious_quotes():
    with _Dummy() as seg:
        assert Translator._rewrap(None, seg, '"Saatçi"') == "Saatçi"
        assert Translator._rewrap(None, seg, "") == ""


class _Dummy:
    def __enter__(self):
        from lxml import etree

        from epub_tr.blocks import encode
        from epub_tr.epub_io import Segment
        e = etree.fromstring("<p>The Clockmaker</p>")
        return Segment(uid="0:0", doc=None, element=e, enc=encode(e))

    def __exit__(self, *a):
        return False


def test_harmonize_toc_copies_heading_translation(epub_path):
    with Book(epub_path) as b:
        segs = b.all_segments()
        for s in segs:
            if s.kind == "heading":
                s.translation = "Birinci Bölüm" if "One" in s.source else "İkinci Bölüm"
        harmonize_toc(segs)
        nav = next(d for d in b.documents if d.is_nav)
        assert nav.segments[0].translation == "<g1>Birinci Bölüm</g1>"
        assert [s.translation for s in b.ncx_segments] == ["Birinci Bölüm", "İkinci Bölüm"]


def test_translator_requires_engines():
    with pytest.raises(ValueError):
        Translator([], None)


def test_glossary_rejects_reversed_or_invented_entries(epub_path):
    """Seen in a real OpenCode run: 'Hediyenin Getirdiği Mutluluk => The Gift of the Magi' was learnt."""
    llm = FakeLLM(glossary="Della => Della\nSaatçinin Kızı => The Clockmaker\nUnicorn => Tek boynuzlu at")
    with Book(epub_path) as b:
        tr, _ = run(b, [llm], chunk_chars=10_000)
    assert tr.glossary == {"Della": "Della"}


def test_stale_cached_glossary_entries_are_ignored(epub_path, tmp_path):
    cache = Cache(str(tmp_path / "c.sqlite3"))
    cache.save_glossary("book", {"Hediyenin Getirdiği Mutluluk": "The Gift of the Magi", "Della": "Della"})
    with Book(epub_path) as b:
        tr, _ = run(b, [FakeLLM(glossary="")], cache, glossary={"Sofronie": "Sofronie"})
    assert "Hediyenin Getirdiği Mutluluk" not in tr.glossary
    assert tr.glossary["Della"] == "Della" and tr.glossary["Sofronie"] == "Sofronie"
    cache.close()
