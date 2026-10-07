# Research: Open-source ebook / document translation tools

Star counts and licenses were pulled live from the GitHub REST API (`gh api repos/<owner>/<repo>`)
on **2026-10-03 (TRT)**. Candidates were found with `gh api search/repositories` queries
("epub translate", "ebook translation", "document translation", "pdf translate", "bilingual book", …),
sorted by stars, then filtered down to tools that actually translate *documents/books* (generic
documentation-translation repos such as "You-Dont-Know-JS translated" were excluded).

## Top 15 (by stars)

| # | Repo | Stars | License | EPUB? | Engines (main) |
|---|------|------:|---------|:-----:|----------------|
| 1 | [PDFMathTranslate/PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) | 37,307 | AGPL-3.0 | ✗ (PDF) | Google, Bing, DeepL/DeepLX, OpenAI & compatible, Azure, Gemini, Ollama, Xinference, Zhipu, Silicon, DeepSeek, Groq, Grok, Tencent, Dify, AnythingLLM, Argos … |
| 2 | [immersive-translate/immersive-translate](https://github.com/immersive-translate/immersive-translate) | 19,169 | none (closed core) | ✓ (web app) | Google, Microsoft, DeepL, OpenAI, Claude, Gemini, many more (mostly via paid "Pro") |
| 3 | [LibreTranslate/LibreTranslate](https://github.com/LibreTranslate/LibreTranslate) | 16,978 | AGPL-3.0 | ✓ (file API via argos-translate-files) | Argos Translate (offline OpenNMT/CTranslate2 models) |
| 4 | [windingwind/zotero-pdf-translate](https://github.com/windingwind/zotero-pdf-translate) | 11,970 | AGPL-3.0 | ✗ (Zotero PDF/EPUB reader selections) | Google, Bing, DeepL, OpenAI/GPT, Gemini, Claude, Baidu, Youdao, Tencent, many |
| 5 | [yihong0618/bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | 9,824 | MIT | ✓ | OpenAI/ChatGPT, Claude, Gemini, Groq, xAI, DeepL (+free), Google, Caiyun, TranSmart, Qwen, Ollama/any OpenAI-compatible |
| 6 | [funstory-ai/BabelDOC](https://github.com/funstory-ai/BabelDOC) | 9,639 | AGPL-3.0 | ✗ (PDF) | OpenAI-compatible LLMs (the engine behind PDFMathTranslate 2.x) |
| 7 | [argosopentech/argos-translate](https://github.com/argosopentech/argos-translate) | 6,521 | MIT | ✓ (via argos-translate-files) | Offline neural MT models (incl. en→tr) |
| 8 | [oomol-lab/pdf-craft](https://github.com/oomol-lab/pdf-craft) | 6,338 | MIT | ✓ (PDF→EPUB, + translation) | DeepSeek-OCR + any OpenAI-compatible LLM |
| 9 | [bookfere/Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | 2,643 | GPL-3.0 | ✓ (+MOBI/AZW3/DOCX… via Calibre) | Google (free & API), Microsoft Edge free, DeepL, ChatGPT/Azure, Gemini, Claude, DeepSeek, Baidu, Youdao, custom |
| 10 | [hydropix/TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs) | 2,455 | AGPL-3.0 | ✓ (+DOCX, PDF, SRT, TXT) | Ollama, LM Studio, OpenAI-compatible, Gemini, Mistral, DeepSeek, Poe, OpenRouter |
| 11 | [deusyu/translate-book](https://github.com/deusyu/translate-book) | 2,059 | MIT | ✓ (+PDF/DOCX via Calibre/Pandoc) | Agent "skill" for Codex, Claude Code, OpenClaw (parallel sub-agents) |
| 12 | [jesselau76/ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | 1,734 | MIT | ✓ (+TXT/DOCX/PDF/MOBI) | OpenAI, Azure, OpenAI-compatible, Codex CLI, Claude Code CLI, Gemini CLI |
| 13 | OmniDocX/PolyglotPDF (repo returns 404 since 2026-10) | 1,324 | GPL-3.0 | partial (PDF, ebook PDFs) | OpenAI-compatible, DeepSeek, Doubao, Qwen, Grok, Ollama, Bing/Google |
| 14 | [xunbu/docutranslate](https://github.com/xunbu/docutranslate) | 1,322 | MPL-2.0 | ✓ (+PDF/DOCX/XLSX/MD/SRT/JSON) | Any OpenAI-compatible LLM (+ MinerU for PDF parsing) |
| 15 | [oomol-lab/epub-translator](https://github.com/oomol-lab/epub-translator) | 857 | MIT | ✓ (bilingual) | Any OpenAI-compatible LLM |

Honourable mentions (verified): ogkalu2/comic-translate 2,962 (Apache-2.0, comics/manga images, not ebooks),
quantrancse/epub-translator 301 (MIT, Google Translate + custom dictionary, EPUB),
sharplab/epub-translator 176 (Apache-2.0, DeepL API, EPUB, Java), lukaszliniewicz/Pandrator 630 (MIT, audiobooks).

## Strengths / weaknesses

| Repo | Strengths | Weaknesses (esp. for literary Turkish EPUB) |
|------|-----------|---------------------------------------------|
| PDFMathTranslate | Best-in-class PDF layout/formula preservation, huge engine list, GUI/CLI/Docker/MCP/Zotero | PDF only, scientific focus; no literary prompt tuning, no EPUB |
| immersive-translate | Polished UX, bilingual reading, EPUB/PDF/subtitles | Not really open source (repo = issues/releases), many features paid, browser-bound |
| LibreTranslate | Fully self-hosted, offline, file API incl. EPUB | Argos en→tr quality is mediocre/literal; no context or style |
| zotero-pdf-translate | Excellent for research reading in Zotero | Translates selections/annotations, not whole books |
| bilingual_book_maker | Most popular EPUB tool, MIT, many engines, bilingual output, resume | Paragraph-by-paragraph with little context; no glossary/consistency, simple prompts; formatting inside paragraphs often flattened |
| BabelDOC | Strong PDF layout engine, used as a library | PDF only, AGPL |
| argos-translate | Offline, MIT, Python API, en→tr model available | Sentence-level NMT, literal, weak on idioms/dialogue |
| pdf-craft | Converts scanned PDFs to clean EPUB/Markdown with OCR | Translation is secondary; needs GPU/OCR stack |
| Ebook-Translator-Calibre-Plugin | Many formats through Calibre, GUI review/edit of each paragraph, glossary, cache | Requires Calibre GUI; GPL; LLM context limited |
| TranslateBooksWithLLMs | Context-aware chunking, resume, no size limit, many LLM backends, web UI | AGPL; heavier setup; no free cloud engine out of the box |
| translate-book | Clever use of coding agents + parallel sub-agents; whole-book quality | Requires paid agent runtimes (Codex/Claude Code); EPUB re-built via Pandoc/Calibre (structure not byte-preserved) |
| ebook-GPT-translator | Uses CLI agents (Codex/Claude/Gemini CLI) as engines, GUI | Output EPUB is re-generated, formatting may be lost |
| PolyglotPDF | Layout-preserving PDF with LLMs, formulas | PDF only, GPL |
| docutranslate | Many formats, glossary, async, Web UI | LLM-only (needs API key); PDF→markdown loses layout |
| oomol epub-translator | Clean bilingual EPUB, MIT, Python API | LLM-only (paid key), bilingual focus |

## Lessons applied to `epub-tr`

* Keep the original EPUB zip *as is* and only rewrite translated XHTML/OPF/NCX entries
  (bilingual_book_maker / calibre plugin approach) → images, CSS, fonts, TOC survive.
* Translate block-by-block but **with context** (previous paragraphs) and a **running glossary**
  (TranslateBooksWithLLMs / docutranslate idea) for name and term consistency.
* Batch several paragraphs per LLM call with stable segment IDs (fewer calls, more context).
* Use a coding-agent CLI as a free LLM backend (translate-book / ebook-GPT-translator idea) →
  here: **OpenCode CLI** with its free "Zen" models.
* SQLite cache + resume (calibre plugin, TranslateBooksWithLLMs), engine fallback chain.
* None of the 15 tools ships a Turkish-specific literary prompt (Turkish dialogue punctuation,
  vowel harmony in suffixes on proper names, "siz/sen" register) — that is the niche of `epub-tr`.
