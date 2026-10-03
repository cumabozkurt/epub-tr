# epub-tr — literary-quality EPUB translator (Turkish first)

[Türkçe README](README.tr.md) · MIT License

`epub-tr` translates EPUB books into **natural, literary Turkish** (other target languages work too)
while keeping the book intact: HTML formatting, images, CSS, fonts, TOC (nav + NCX), metadata and
internal links survive. All engines are **free** (no paid API key required).

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
