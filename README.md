# epub-tr — literary-quality EPUB translator (Turkish first)

[Türkçe README](README.tr.md) · [MIT License](LICENSE) · Python ≥ 3.9

`epub-tr` translates EPUB books into **natural, literary Turkish** (other target languages work too)
while keeping the book intact: HTML formatting, images, CSS, fonts, TOC (nav + NCX), metadata and
internal links survive. All engines are **free** (no paid API key required).

**Contents:** [Features](#features) · [Engines](#engines) · [Install](#install) · [Quick start](#quick-start) ·
[Usage](#usage) · [Configuration](#configuration) · [Architecture](#architecture) ·
[Troubleshooting](#troubleshooting) · [Tests](#tests) · [Contributing](#contributing) · [License](#license)

## Features

* **Structure-preserving EPUB I/O** – read with `ebooklib` (metadata, manifest, spine) + `lxml`;
  write at ZIP level: every original entry is copied byte-for-byte, only translated XHTML, OPF
  (`dc:language` → `tr`, translated title) and NCX/nav labels are replaced. Output validates with
  EPUBCheck as well as the input does.
* **Inline markup kept** – `<i>`, `<em>`, `<a id=…>`, `<br/>`, footnote refs… are turned into neutral
  placeholders (`<g1>…</g1>`, `<x2/>`) for the engine and rebuilt afterwards with all attributes.
  If an engine breaks them, a lenient fallback keeps the text and every anchor/link target.
* **Bilingual mode** (`--bilingual`) – translation inserted under each original paragraph.
* **Literary LLM pipeline**
  * paragraphs batched into chunks (`--chunk-chars`) with stable `<seg id>`s,
  * **context window**: previous paragraphs (source + translation) sent with every chunk,
  * **running glossary**: the model reports name/term decisions which are reused for the rest of
    the book (and persisted in the cache → consistent on resume); seed your own with `--glossary`,
  * automatic **proper-name detection** (names kept, Turkish suffixes with apostrophe: *Della'nın*),
  * Turkish literary system prompt: idiomatic, tone/style/period preserving, TDK spelling,
    sen/siz consistency, dialogue punctuation (`--dialogue quotes|dash`),
  * optional **second review/polish pass** (`--polish`, optionally with another engine
    `--polish-engine`).
* **Speed & robustness** – thread-pool concurrency (chapters in parallel for LLMs, batches for MT),
  SQLite cache = **resume** for free, retries with back-off, per-chunk **fallback chain**
  (`--fallback google,argos`), fast fail on OpenCode free-tier rate limits with automatic switching
  between OpenCode free models.

## Engines

| engine | type | needs |
|---|---|---|
| `opencode` | LLM via `opencode run` (OpenCode Zen **free** models: big-pickle, nemotron-3-ultra-free, mimo-v2.6-flash-free, …) | `npm i -g opencode-ai` |
| `ollama` | local LLM (default `gemma3:4b`, try `aya-expanse:8b`, `qwen2.5:7b`, `gemma3:12b`) | Ollama running |
| `google` | Google Translate free web endpoints (+ deep-translator fallback) | – |
| `bing`, `yandex`, `modernmt` | free web translators via the optional `translators` package (GPL-3) | `pip install translators` |
| `mymemory` | MyMemory API (anonymous ~5k chars/day/IP; `MYMEMORY_EMAIL` → 50k) | – |
| `lingva` | Lingva public instances (`LINGVA_URL`) | – |
| `libretranslate` | LibreTranslate server (`LIBRETRANSLATE_URL`, `LIBRETRANSLATE_API_KEY`) | self-host or key |
| `argos` | Argos Translate, fully offline (en→tr model auto-installed) | `pip install argostranslate` |
| `openrouter`, `gemini`, `groq`, `mistral`, `openai` | OpenAI-compatible APIs – free tiers (e.g. OpenRouter `:free` models, Gemini free tier) | `OPENROUTER_API_KEY` / `GEMINI_API_KEY` / … |

`epub-tr engines --check` shows what is usable on your machine.

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .                 # core
pip install -e '.[argos,extra]'  # offline Argos + Bing/Yandex/ModernMT
npm i -g opencode-ai             # OpenCode CLI (free LLMs)
```

## Quick start

```bash
git clone https://github.com/cumabozkurt/epub-tr.git && cd epub-tr
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
epub-tr engines --check                                  # which engines work here?
epub-tr inspect samples/pg7256.epub --show 10           # what will be translated
epub-tr translate samples/pg7256.epub -e google -o magi.tr.epub   # ~2 s, no setup needed
```

## Usage

```bash
# best quality, free: OpenCode free LLM + polish pass, Google as safety net
epub-tr translate book.epub -o book.tr.epub --engine opencode --polish --fallback google

# pick an OpenCode model explicitly
epub-tr translate book.epub --engine opencode -m opencode/nemotron-3-ultra-free

# local & private
epub-tr translate book.epub --engine ollama -m aya-expanse:8b --chunk-chars 1500

# fast MT, bilingual edition
epub-tr translate book.epub --engine google --bilingual -o book.en-tr.epub

# only chapters 1-3, first 50 paragraphs, Turkish dash-style dialogue, own glossary
epub-tr translate book.epub --chapters 1-3 --limit 50 --dialogue dash --glossary names.tsv

epub-tr inspect book.epub --show 20      # see what will be translated
```

Useful options: `--source en` (default: from metadata), `--target tr`, `--workers N`,
`--context 3`, `--retries 3`, `--no-toc`, `--keep-boilerplate` (also translate Project Gutenberg
header/licence; skipped by default), `--cache PATH`, `--no-cache`, `--stats out.json`,
`--dump pairs.jsonl`.

Environment: `EPUB_TR_OPENCODE_MODEL`, `EPUB_TR_OPENCODE_TIMEOUT`, `EPUB_TR_OLLAMA_MODEL`,
`OLLAMA_HOST`, `EPUB_TR_CACHE`, plus the API keys above.

## Configuration

### `epub-tr translate` options

| option | default | meaning |
|---|---|---|
| `input` | – | source `.epub` |
| `-o, --output` | `<input>.<target>.epub` (`<input>.bilingual.<target>.epub` with `--bilingual`) | output path |
| `-e, --engine` | `opencode` | main engine (see [Engines](#engines)) |
| `-m, --model` | engine default | model for LLM engines (`opencode/big-pickle`, `gemma3:4b`, …) |
| `--fallback` | – | comma-separated engines tried per chunk when the main one fails, e.g. `google,argos` |
| `-s, --source` | from `dc:language`, else `en` | source language |
| `-t, --target` | `tr` | target language |
| `--bilingual` | off | keep the original paragraph and add the translation below it |
| `--polish` | off | second LLM pass: literary review/polish |
| `--polish-engine`, `--polish-model` | same LLM | engine/model for the polish pass |
| `--dialogue` | `quotes` | Turkish dialogue style: `quotes` (“…”) or `dash` (— …) |
| `--glossary` | – | seed glossary (see below) |
| `-w, --workers` | engine default | parallel workers (chapters for LLMs, batches for MT) |
| `--chunk-chars` | `2500` | source characters per LLM request |
| `--context` | `3` | previous paragraphs sent to the LLM as context |
| `--retries` | `3` | retries per chunk (exponential back-off) |
| `--chapters` | all | content documents to translate, 1-based: `1-3,5` |
| `--limit` | – | only the first N segments (handy for testing) |
| `--no-toc` | off | do not translate nav/NCX labels |
| `--keep-boilerplate` | off | also translate the Project Gutenberg header/licence |
| `--cache` / `--no-cache` | `~/.cache/epub-tr/cache.sqlite3` | SQLite translation cache (resume) |
| `--stats FILE` | – | write a JSON summary (incl. the final glossary) |
| `--dump FILE` | – | write JSONL `{uid, source, translation, engine}` pairs |
| `-q, --quiet` | off | no progress bar |
| `-v, --verbose` (global) | off | INFO logging |

Other sub-commands: `epub-tr engines [--check]`, `epub-tr inspect BOOK [--show N]`, `epub-tr --version`.

**Exit code:** `0` when every selected segment was translated, `2` when some segments are still
untranslated (they are kept in the source language; rerun later to fill them from the remaining engines/cache).
A JSON summary (segments, engine usage, failures, cache hits, glossary size, first errors) is always printed to stderr.

### Glossary file

`--glossary` accepts JSON (`{"Della": "Della", "Madame Sofronie": "Madam Sofronie"}`) or a text file with one
entry per line, using `=>`, a TAB or `=` as separator; empty lines and `#` comments are ignored:

```text
# names.tsv
Madame Sofronie => Madam Sofronie
the Magi	Müneccimler
```

### Environment variables

| variable | used by | default |
|---|---|---|
| `EPUB_TR_CACHE` | cache path | `$XDG_CACHE_HOME/epub-tr/cache.sqlite3` |
| `EPUB_TR_OPENCODE_MODEL` | opencode | `opencode/big-pickle` |
| `EPUB_TR_OPENCODE_TIMEOUT` | opencode (seconds per call) | `600` |
| `OPENCODE_BIN` | opencode binary | `opencode` on `PATH`, then `~/.opencode/bin/opencode` |
| `EPUB_TR_OLLAMA_MODEL` | ollama | `gemma3:4b` |
| `OLLAMA_HOST` | ollama | `http://localhost:11434` |
| `EPUB_TR_OLLAMA_CTX` / `EPUB_TR_OLLAMA_MAX_TOKENS` / `EPUB_TR_OLLAMA_TIMEOUT` | ollama | `8192` / auto / `1800` |
| `MYMEMORY_EMAIL` | mymemory (raises the daily quota) | – |
| `LINGVA_URL` | lingva instance | built-in public list |
| `LIBRETRANSLATE_URL`, `LIBRETRANSLATE_API_KEY` | libretranslate | `http://localhost:5000` |
| `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, `OPENAI_API_KEY` | API presets | – |
| `EPUB_TR_<PRESET>_MODEL`, `EPUB_TR_<PRESET>_BASE_URL`, `OPENAI_BASE_URL` | override preset model / endpoint | see `epub_tr/engines/llm.py` |

Default preset models: openrouter `meta-llama/llama-3.3-70b-instruct:free`, gemini `gemini-2.5-flash`,
groq `llama-3.3-70b-versatile`, mistral `mistral-small-latest`, openai `gpt-4o-mini`.

## Architecture

```text
book.epub ──► epub_io.Book (ebooklib + lxml) ── documents, spine, OPF, nav, NCX
                 │  blocks.py: each block element → Segment, inline markup → <g1>…</g1>/<x2/> placeholders
                 ▼
          pipeline.Translator
            ├─ MT engines:  batched segments, thread pool
            └─ LLM engines: chunks of <seg id=…> (--chunk-chars) + context window + running glossary
                            + Turkish literary prompt (prompts.py) → optional --polish pass
            ├─ cache.py: SQLite cache keyed by engine+model+stage+languages+text (resume); glossary stored per book
            └─ fallback chain per chunk, retries/back-off, rate-limit detection
                 ▼
          Book.apply() rebuilds elements with all attributes (lenient fallback keeps anchors/links)
          Book.write() copies the original ZIP byte-for-byte, replaces only XHTML, OPF, nav, NCX ──► book.tr.epub
```

| module | responsibility |
|---|---|
| `epub_tr/cli.py` | argument parsing, engine/fallback setup, summary/stats/dump |
| `epub_tr/epub_io.py` | EPUB reading (segments, TOC labels, Gutenberg boilerplate detection) and ZIP-level writing |
| `epub_tr/blocks.py` | XHTML block ⇄ placeholder string encoding |
| `epub_tr/pipeline.py` | chunking, context, glossary, name detection, polish, concurrency, fallback, TOC harmonisation |
| `epub_tr/prompts.py` | system/user prompts (Turkish literary rules, dialogue style) |
| `epub_tr/cache.py` | SQLite cache (WAL, lock retry) |
| `epub_tr/engines/` | `base.py` interface, `llm.py` (OpenCode, Ollama, OpenAI-compatible), `mt.py` (Google, translators, MyMemory, Lingva, LibreTranslate, Argos) |
| `scripts/` | `compare.py` (side-by-side engine comparison), `run_ollama.sh`, `opencode_when_available.sh` (waits for the OpenCode free quota, then runs) |
| `samples/`, `out/` | Project Gutenberg test books and the test-run outputs referenced in `TEST_REPORT.md` |

**Adding an engine:** subclass `epub_tr.engines.base.Engine`; implement `translate_one()` (MT, or
`translate_batch()`) or `complete(system, user)` (LLM, set `is_llm = True`) plus `check()` raising
`EngineUnavailable`, then register it in `ENGINES` in `epub_tr/engines/__init__.py`.

## Troubleshooting

| symptom | cause / fix |
|---|---|
| `[warn] engine opencode unavailable` | install the CLI (`npm i -g opencode-ai`) or point `OPENCODE_BIN` at it |
| OpenCode: `FreeUsageLimitError` / HTTP 429 | the Zen free tier is limited per IP for hours. Use `--fallback google` (or another engine) and rerun later; cached chunks are reused. `scripts/opencode_when_available.sh` can wait for the quota. |
| `ollama not running at http://localhost:11434` | `ollama serve` and `ollama pull gemma3:4b` (or set `OLLAMA_HOST`) |
| Ollama very slow / loops | use a smaller `--chunk-chars` (e.g. 1500), a smaller model, or cap with `EPUB_TR_OLLAMA_MAX_TOKENS` |
| `bing`/`yandex`/`modernmt` unavailable | `pip install -e '.[extra]'` (`translators`, GPL-3) |
| `argos` unavailable | `pip install -e '.[argos]'`; the en→tr model downloads on first use |
| `mymemory` returns quota warnings | the anonymous quota per IP is used up; set `MYMEMORY_EMAIL` or switch engine |
| exit code `2` | some segments stayed untranslated (all engines failed for them); see `errors` in the summary and rerun |
| formatting lost on some paragraphs | the summary's `markup_fallbacks` counts paragraphs rebuilt leniently (text and anchors kept, inline styling dropped); LLMs that respect placeholders (or `google`) avoid it |
| want a clean re-translation | `--no-cache` or delete/point `--cache` to a new file |
| Gutenberg header is not translated | intended; add `--keep-boilerplate` |

## Notes on OpenCode free models

`opencode run` is executed in a private directory with a generated `opencode.json` that defines a
tool-less `epubtr` agent whose system prompt is the literary-translation prompt (`--pure`,
`--title` avoids the extra title request, `--format json` for robust parsing). The Zen free tier is
rate-limited **per IP**; when the quota is exhausted (`FreeUsageLimitError`, `retry-after` header of
several hours) `epub-tr` fails fast, tries the other free models and then falls back to the next
engine in `--fallback`. Run again later – cached chunks are not re-translated.

## Tests

```bash
pip install pytest && python -m pytest -q
```

See `RESEARCH.md` (survey of 15 popular open-source translators) and `TEST_REPORT.md`.

## Contributing

Issues and pull requests are welcome. Please:

1. create a virtualenv and `pip install -e '.[dev]'`;
2. keep changes focused and add/extend a test in `tests/` (the `echo` engine lets you test structure without network);
3. run `python -m pytest -q` before opening a PR;
4. if you touch the prompts, include a before/after sample (e.g. with `scripts/compare.py`).

## License

[MIT](LICENSE) © Cuma Bozkurt. The optional `translators` package (Bing/Yandex/ModernMT) is GPL-3;
it is not a hard dependency. Sample books in `samples/` are public-domain Project Gutenberg texts.
