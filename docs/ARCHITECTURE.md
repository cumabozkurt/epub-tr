# Architecture

Türkçe: [ARCHITECTURE.tr.md](ARCHITECTURE.tr.md) · Back to [README](../README.md)

`epub-tr` does three things in order. It **reads** the book into segments, **translates** the segments
through one or more engines, and **writes** a new EPUB in which only the translated parts differ from the
original.

```text
book.epub
  │
  ├─ epub_io.Book ─ ebooklib (metadata, manifest, spine) + lxml (XHTML, OPF, nav, NCX)
  │     └─ blocks.encode(): block element → Segment(enc="Della <g1>counted</g1> it.<x2/>")
  │
  ├─ pipeline.Translator
  │     ├─ MT engines   → batches of segments (engine.max_chars), thread pool
  │     ├─ LLM engines  → chunks of <seg id=N>…</seg> (--chunk-chars) per document, documents in parallel
  │     │                 + context (previous paragraphs + their translations)
  │     │                 + running glossary + detected proper names + literary prompt (prompts.py)
  │     │                 → optional --polish pass (same or another LLM)
  │     ├─ cache.Cache  → SQLite, key = engine + model + stage + languages + source text; glossary per book
  │     └─ fallback chain per chunk, retries with back-off, fast rate-limit detection
  │
  ├─ pipeline.harmonize_toc(): TOC labels follow the translated chapter headings
  │
  └─ Book.apply() + Book.write()
        ├─ blocks.decode_into(): placeholders → original elements with all attributes
        │     (lenient fallback keeps the text, anchors and link targets if an engine broke the tags)
        └─ ZIP rewrite: every entry copied byte for byte, in the same order (mimetype first, stored);
           only translated XHTML, OPF (dc:language, title), nav and NCX are replaced
```

## Segments and placeholders

A **segment** is one block-level element that holds text: `p`, `h1`–`h6`, `li`, `td`, `blockquote`,
`dd` and so on, plus TOC labels. Its inline content is encoded so that engines never see real markup:

| source | sent to the engine |
|---|---|
| `<i>`, `<em>`, `<span class=…>`, `<a href=…>` | `<g1>…</g1>` (paired, numbered) |
| `<br/>`, `<img/>`, empty `<a id=…/>` | `<x2/>` (self-closing) |

After translation, `decode_into()` rebuilds the element. Every original attribute comes back, and the
tags may be reordered when the target language needs it. If the engine dropped or invented a tag, the
**lenient** path keeps the translated text and re-attaches anchors and links, so internal links and
footnotes never break. The run summary reports this as `markup_fallbacks`.

Never translated: `script`, `style`, `pre`, `code`, `math`, `svg`, elements with `translate="no"` or
class `notranslate`, paragraphs without letters (digits only, ornaments), and (by default) the Project Gutenberg header and licence.

## The LLM path

1. **Chunking.** The segments of one document are packed into chunks of about `--chunk-chars` characters.
   Each segment travels as `<seg id="N">…</seg>`, and the answer is matched back by id. Segments missing
   from the answer are asked again, up to two rounds, and then go to the fallback engine.
2. **Context.** The last `--context` source paragraphs and their translations go with each chunk, so
   tone, sen/siz and names stay consistent across chunk borders.
3. **Glossary.** The model may append `<glossary>source => target</glossary>`. An entry is learnt only
   if its source term occurs in the chunk, which blocks reversed or invented pairs. Entries are saved per
   book in the cache, and on load only the entries that occur in the current text are used.
   `--glossary` entries always win.
4. **Names.** Capitalised words that recur mid-sentence are detected and passed as "keep these names".
   Turkish suffixes are attached with an apostrophe (*Della'nın*).
5. **Polish** (`--polish`). A second pass gets the source and the draft and returns an edited
   version. If the polish fails, the draft is kept.

## Writing

`Book.write()` never re-serialises files it did not change. Fonts, images, CSS, encryption info and
unknown files keep their original bytes. The OPF gets `dc:language` set to the target language and a
translated title. In **bilingual** mode, the translated copy is inserted after each source block, with
ids removed so the document stays valid.

## Modules

| module | responsibility |
|---|---|
| `epub_tr/cli.py` | argument parsing, engine and fallback setup, summary, stats and dump; safe console encoding |
| `epub_tr/epub_io.py` | EPUB reading (segments, TOC labels, boilerplate detection), applying translations, ZIP writing |
| `epub_tr/blocks.py` | block element ⇄ placeholder string encoding, lenient decode |
| `epub_tr/pipeline.py` | chunking, context, glossary, names, polish, concurrency, retries, fallback, TOC harmonisation |
| `epub_tr/prompts.py` | system, user and polish prompts; Turkish literary rules; dialogue style |
| `epub_tr/cache.py` | SQLite cache (WAL, retry on lock), per-book glossary |
| `epub_tr/engines/` | `base.py` interface, `llm.py` (OpenCode, Ollama, OpenAI-compatible), `mt.py` (Google, translators, MyMemory, Lingva, LibreTranslate, Argos) |

See [ENGINES.md](ENGINES.md) for engine details and [AUTOMATION.md](AUTOMATION.md) for CI and releases.
