"""Command line interface, end to end on synthetic and real EPUBs (offline engines only)."""
import json
import subprocess
import sys
import zipfile

import pytest
from conftest import MAGI, WALLPAPER, FailingEngine, UpperMT

from epub_tr import __version__, cli
from epub_tr.engines import ENGINES
from epub_tr.epub_io import Book


@pytest.fixture
def fake_engines(monkeypatch):
    monkeypatch.setitem(ENGINES, "upper", ("test", lambda **kw: UpperMT(**kw)))
    monkeypatch.setitem(ENGINES, "broken", ("test", lambda **kw: FailingEngine(**kw)))


def test_parse_range():
    assert cli._parse_range("1-3,5", 9) == {1, 2, 3, 5}
    assert cli._parse_range("", 9) is None and cli._parse_range(None, 9) is None


def test_load_glossary_formats(tmp_path):
    t = tmp_path / "g.tsv"
    t.write_text("# comment\n\nDella => Della\nthe Magi\tMüneccimler\nMadame Sofronie = Madam Sofronie\nnoseparator\n",
                 encoding="utf-8")
    assert cli._load_glossary(str(t)) == {"Della": "Della", "the Magi": "Müneccimler",
                                          "Madame Sofronie": "Madam Sofronie"}
    j = tmp_path / "g.json"
    j.write_text(json.dumps({"Jim": "Jim"}), encoding="utf-8")
    assert cli._load_glossary(str(j)) == {"Jim": "Jim"} and cli._load_glossary(None) == {}


def test_version_and_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and capsys.readouterr().out.strip() == __version__
    with pytest.raises(SystemExit):
        cli.main([])


def test_engines_list(capsys):
    cli.main(["engines"])
    out = capsys.readouterr().out
    assert "opencode" in out and "google" in out and "echo" not in out


def test_inspect(epub_path, capsys):
    cli.main(["inspect", epub_path, "--show", "3"])
    out = capsys.readouterr().out
    assert "title='The Clockmaker'" in out and "OEBPS/ch1.xhtml: 8 segments" in out and "ncx: OEBPS/toc.ncx (2 labels)" in out
    assert "heading Chapter One" in out


def test_translate_full_with_stats_and_dump(tmp_path, epub_path, fake_engines, capsys):
    out, stats, dump = tmp_path / "o.epub", tmp_path / "s.json", tmp_path / "d.jsonl"
    rc = cli.main(["translate", epub_path, "-e", "upper", "-o", str(out), "--stats", str(stats),
                   "--dump", str(dump), "-q", "--no-cache"])
    assert rc == 0
    s = json.loads(stats.read_text(encoding="utf-8"))
    assert "engine_models" in s
    assert s["untranslated"] == 0 and s["translated"] == s["segments"] == 14 and s["engine_segments"]["upper"] == 14
    rows = [json.loads(line) for line in dump.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 14 and rows[0] == {"uid": "0:0", "source": "Chapter One", "translation": "CHAPTER ONE",
                                           "engine": "upper"}
    with Book(str(out)) as b:
        assert b.language == "tr" and b.title == "The Clockmaker"  # title only changes when a heading matches it


def test_translate_default_output_names(tmp_path, epub_path, fake_engines):
    assert cli.main(["translate", epub_path, "-e", "upper", "-q", "--no-cache"]) == 0
    assert (tmp_path / "book.tr.epub").exists()
    assert cli.main(["translate", epub_path, "-e", "upper", "-q", "--no-cache", "--bilingual", "-t", "de"]) == 0
    assert (tmp_path / "book.bilingual.de.epub").exists()


def test_translate_chapters_limit_and_no_toc(tmp_path, epub_path, fake_engines):
    out, stats = tmp_path / "o.epub", tmp_path / "s.json"
    cli.main(["translate", epub_path, "-e", "upper", "-o", str(out), "--chapters", "2", "--no-toc",
              "--stats", str(stats), "-q", "--no-cache"])
    s = json.loads(stats.read_text(encoding="utf-8"))
    assert s["segments"] == 2  # chapter two only: heading + paragraph
    z = zipfile.ZipFile(out)
    assert b"THE END CAME QUIETLY." in z.read("OEBPS/ch2.xhtml") and b"CHAPTER ONE" not in z.read("OEBPS/ch1.xhtml")
    cli.main(["translate", epub_path, "-e", "upper", "-o", str(out), "--limit", "3", "--stats", str(stats), "-q",
              "--no-cache"])
    assert json.loads(stats.read_text(encoding="utf-8"))["segments"] == 3


def test_translate_fallback_and_exit_code(tmp_path, epub_path, fake_engines):
    out = tmp_path / "o.epub"
    assert cli.main(["translate", epub_path, "-e", "broken", "--fallback", "upper", "-o", str(out), "-q",
                     "--no-cache", "--retries", "1"]) == 0
    assert cli.main(["translate", epub_path, "-e", "broken", "-o", str(out), "-q", "--no-cache", "--retries", "1"]) == 2


def test_translate_no_usable_engine(tmp_path, epub_path, monkeypatch):
    monkeypatch.setenv("OPENCODE_BIN", str(tmp_path / "none"))
    with pytest.raises(SystemExit, match="no usable engine"):
        cli.main(["translate", epub_path, "-e", "opencode", "-q"])


def test_translate_uses_cache_between_runs(tmp_path, epub_path, fake_engines):
    cache, stats = tmp_path / "c.sqlite3", tmp_path / "s.json"
    for _ in range(2):
        cli.main(["translate", epub_path, "-e", "upper", "-o", str(tmp_path / "o.epub"), "--cache", str(cache),
                  "--stats", str(stats), "-q"])
    assert json.loads(stats.read_text(encoding="utf-8"))["cache_hits"] == 14


@pytest.mark.parametrize("sample", [MAGI, WALLPAPER])
def test_echo_roundtrip_on_real_books(tmp_path, sample):
    """Module entry point as a subprocess, like a user would run it."""
    out = tmp_path / "o.epub"
    r = subprocess.run([sys.executable, "-m", "epub_tr.cli", "translate", sample, "-e", "echo", "-o", str(out),
                        "--no-cache", "-q"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    with Book(sample) as a, Book(str(out)) as b:
        assert [s.enc.plain() for s in a.all_segments()] == [s.enc.plain() for s in b.all_segments()]
        assert b.language == "tr"
    assert zipfile.ZipFile(out).namelist() == zipfile.ZipFile(sample).namelist()
