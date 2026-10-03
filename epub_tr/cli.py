"""Command line interface: ``epub-tr translate book.epub -o out.epub --engine opencode``."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time

from . import __version__
from .cache import Cache
from .engines import ENGINES, make_engine
from .engines.base import EngineUnavailable
from .epub_io import Book
from .pipeline import Translator


def _parse_range(spec, n):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def _load_glossary(path):
    g = {}
    if not path:
        return g
    with open(path, encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for sep in ("=>", "\t", "="):
                if sep in line:
                    k, v = line.split(sep, 1)
                    g[k.strip()] = v.strip()
                    break
    return g


def cmd_translate(a):
    t0 = time.time()
    book = Book(a.input, skip_gutenberg=not a.keep_boilerplate, translate_toc=not a.no_toc)
    src = a.source or (book.language or "en").split("-")[0]
    content_docs = [d for d in book.documents if d.segments and not d.is_nav]
    chosen = _parse_range(a.chapters, len(content_docs))
    docs_segments = []
    for i, d in enumerate(content_docs, 1):
        if chosen and i not in chosen:
            continue
        docs_segments.append(list(d.segments))
    if not a.no_toc:
        docs_segments += [list(d.segments) for d in book.documents if d.is_nav and d.segments]
        if book.ncx_segments:
            docs_segments.append(list(book.ncx_segments))
    if a.limit:
        remaining, limited = a.limit, []
        for d in docs_segments:
            if remaining <= 0:
                break
            limited.append(d[:remaining])
            remaining -= len(limited[-1])
        docs_segments = limited
    total = sum(len(d) for d in docs_segments)
    chars = sum(len(s.source) for d in docs_segments for s in d)

    kw = dict(source=src, target=a.target)
    engines = []
    for i, name in enumerate([a.engine] + [e for e in (a.fallback or "").split(",") if e]):
        e = make_engine(name, model=a.model if i == 0 else None, **kw)
        try:
            e.check()
            engines.append(e)
        except EngineUnavailable as ex:
            print(f"[warn] engine {name} unavailable: {ex}", file=sys.stderr)
    if not engines:
        sys.exit("no usable engine")
    polish_engine = None
    if a.polish_engine:
        polish_engine = make_engine(a.polish_engine, model=a.polish_model, **kw)
        polish_engine.check()

    cache = Cache(a.cache, enabled=not a.no_cache)
    book_id = hashlib.sha1(open(a.input, "rb").read()).hexdigest()[:16] + f":{a.target}"

    print(f"Book: {book.title!r} by {book.creator} | {len(content_docs)} content docs | "
          f"{total} segments, {chars} chars | engines: {[e.name + ('/' + e.model_id if e.model_id else '') for e in engines]}",
          file=sys.stderr)

    try:
        from tqdm import tqdm
        bar = tqdm(total=total, unit="seg", disable=a.quiet)
        progress = bar.update
    except ImportError:
        bar, progress = None, None

    tr = Translator(engines, cache, source=src, target=a.target, workers=a.workers, chunk_chars=a.chunk_chars,
                    context_paras=a.context, polish=a.polish, polish_engine=polish_engine, dialogue=a.dialogue,
                    glossary=_load_glossary(a.glossary), book_id=book_id, retries=a.retries, progress=progress)
    stats = tr.run(docs_segments)
    if bar:
        bar.close()

    title = None
    if a.translate_title and book.title:
        title_seg = [s for d in docs_segments for s in d if s.kind == "heading" and s.enc.plain().strip().lower() == book.title.strip().lower() and s.translation]
        title = title_seg[0].translation if title_seg else None
        if title and a.bilingual:
            title = f"{book.title} / {title}"
    applied = book.apply(bilingual=a.bilingual, target_lang=a.target)
    out = a.output or os.path.splitext(a.input)[0] + (".bilingual" if a.bilingual else "") + f".{a.target}.epub"
    import re as _re
    if title:
        title = _re.sub(r"<[^>]+>", "", title)
    book.write(out, target_lang=a.target, title=title, bilingual=a.bilingual)
    dt = time.time() - t0
    summary = {
        "output": out, "seconds": round(dt, 1), "segments": total, "chars": chars,
        "translated": applied["applied"], "untranslated": applied["untranslated"],
        "selected_missing": sum(1 for d in docs_segments for s in d if not s.translation),
        "markup_fallbacks": applied["lenient"], "engine_segments": dict(stats.engine_segments),
        "engine_calls": dict(stats.calls), "failures": dict(stats.failures), "polished_segments": stats.polished,
        "cache_hits": cache.hits, "glossary_size": len(tr.glossary), "errors": stats.errors[:10],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
    if a.stats:
        with open(a.stats, "w", encoding="utf-8") as f:
            json.dump({**summary, "glossary": tr.glossary}, f, ensure_ascii=False, indent=2)
    if a.dump:
        with open(a.dump, "w", encoding="utf-8") as f:
            for d in docs_segments:
                for s in d:
                    f.write(json.dumps({"uid": s.uid, "source": s.source, "translation": s.translation,
                                        "engine": s.engine}, ensure_ascii=False) + "\n")
    missing = sum(1 for d in docs_segments for s in d if not s.translation)
    return 0 if missing == 0 else 2


def cmd_engines(a):
    for name, (desc, factory) in ENGINES.items():
        if name == "echo":
            continue
        status = "ok"
        if a.check:
            try:
                factory(source="en", target="tr").check()
            except EngineUnavailable as e:
                status = f"unavailable: {e}"
            except Exception as e:  # noqa
                status = f"error: {e}"
        print(f"{name:15s} {desc}" + (f"  [{status}]" if a.check else ""))


def cmd_inspect(a):
    book = Book(a.input)
    print(f"title={book.title!r} creator={book.creator!r} language={book.language!r} opf={book.opf_path}")
    for d in book.documents:
        print(f"  [{'nav' if d.is_nav else 'doc'}] {d.zip_path}: {len(d.segments)} segments, "
              f"{sum(len(s.source) for s in d.segments)} chars")
    print(f"  ncx: {book.ncx_path} ({len(book.ncx_segments)} labels)")
    if a.show:
        for s in book.all_segments()[: a.show]:
            print(f"    {s.uid:8s} {s.kind:7s} {s.source[:110]}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="epub-tr", description="Literary-quality EPUB translator (Turkish-first)")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("translate", help="translate an EPUB")
    t.add_argument("input")
    t.add_argument("-o", "--output")
    t.add_argument("-e", "--engine", default="opencode", help=f"one of: {', '.join(ENGINES)}")
    t.add_argument("-m", "--model", help="model for LLM engines (e.g. opencode/big-pickle, gemma3:4b)")
    t.add_argument("--fallback", default="", help="comma-separated fallback engines, e.g. google,argos")
    t.add_argument("-s", "--source", help="source language (default: from EPUB metadata)")
    t.add_argument("-t", "--target", default="tr")
    t.add_argument("--bilingual", action="store_true", help="keep original paragraphs and add the translation below")
    t.add_argument("--polish", action="store_true", help="second LLM pass: literary review/polish")
    t.add_argument("--polish-engine", help="engine for the polish pass (default: same LLM)")
    t.add_argument("--polish-model")
    t.add_argument("--dialogue", choices=["quotes", "dash"], default="quotes", help="Turkish dialogue style")
    t.add_argument("--glossary", help="glossary file (TSV, 'a => b' lines or JSON)")
    t.add_argument("-w", "--workers", type=int, help="parallel workers (chapters for LLMs, batches for MT)")
    t.add_argument("--chunk-chars", type=int, default=2500, help="source chars per LLM request")
    t.add_argument("--context", type=int, default=3, help="previous paragraphs passed as context to the LLM")
    t.add_argument("--retries", type=int, default=3)
    t.add_argument("--chapters", help="content documents to translate, 1-based, e.g. 1-3,5")
    t.add_argument("--limit", type=int, help="translate only the first N segments (testing)")
    t.add_argument("--translate-title", action="store_true", default=True)
    t.add_argument("--no-toc", action="store_true", help="do not translate TOC/nav labels")
    t.add_argument("--keep-boilerplate", action="store_true", help="also translate Project Gutenberg header/footer")
    t.add_argument("--cache", help="sqlite cache path (default ~/.cache/epub-tr/cache.sqlite3)")
    t.add_argument("--no-cache", action="store_true")
    t.add_argument("--stats", help="write JSON stats here")
    t.add_argument("--dump", help="write JSONL of source/translation pairs here")
    t.add_argument("-q", "--quiet", action="store_true")
    t.set_defaults(func=cmd_translate)

    e = sub.add_parser("engines", help="list engines")
    e.add_argument("--check", action="store_true", help="check availability")
    e.set_defaults(func=cmd_engines)

    i = sub.add_parser("inspect", help="show EPUB structure / segments")
    i.add_argument("input")
    i.add_argument("--show", type=int, default=0)
    i.set_defaults(func=cmd_inspect)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
