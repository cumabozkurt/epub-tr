"""Prompt building (epub_tr.prompts)."""
from epub_tr import prompts


def test_lang_name():
    assert prompts.lang_name("tr") == "Turkish" and prompts.lang_name("en-US") == "English"
    assert prompts.lang_name("xx") == "xx"


def test_turkish_rules_and_dialogue():
    q, d = prompts.rules_for("tr", "quotes"), prompts.rules_for("tr-TR", "dash")
    assert "TDK" in q and "quotation marks" in q and "em dash" in d
    assert prompts.rules_for("tr", "unknown") == q


def test_generic_rules():
    r = prompts.rules_for("fr")
    assert "French" in r and "TDK" not in r


def test_format_segments():
    assert prompts.format_segments([(1, "a"), (2, "b <g1>c</g1>")]) == '<seg id="1">a</seg>\n<seg id="2">b <g1>c</g1></seg>'


def test_glossary_part():
    assert prompts.glossary_part({}, None) == ""
    g = prompts.glossary_part({"Della": "Della"}, ["Jim"])
    assert "Della => Della" in g and "Jim" in g and g.endswith("\n")


def test_context_part():
    assert prompts.context_part([]) == ""
    c = prompts.context_part([("src", "kaynak")])
    assert "[source] src" in c and "[translation] kaynak" in c and "do NOT translate" in c


def test_system_prompt_formats():
    s = prompts.SYSTEM_PROMPT.format(src="English", tgt="Turkish", rules=prompts.rules_for("tr"))
    assert "<seg id=" in s and "<glossary>" in s and "{" not in s.replace("{src}", "")
