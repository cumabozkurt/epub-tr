# Engines

Türkçe: [ENGINES.tr.md](ENGINES.tr.md) · Back to [README](../README.md)

Every engine is free to use. Some need a free install or a free key; none needs a paid key.
`epub-tr engines --check` shows which ones work on your machine.

## Measured ranking (literary Turkish)

The test text is O. Henry's *The Gift of the Magi*: 51 segments, 11,237 characters. Full data is in
[TEST_REPORT.md](../TEST_REPORT.md), and the outputs are in [`out/`](../out).

| # | engine / setup | quality | time (whole story) | coverage | notes |
|---|---|---|---|---|---|
| 1 | **`opencode --polish`** (`opencode/space-bunny-free`) | best: idiomatic, literary, correct register | 6,932 s | 43/51 in the first run, 51/51 after one resume | very slow free tier; use `--fallback` |
| 2 | `opencode` (draft only, same model) | very good, but has typos | 3,730 s | 45/51 | "beni böyle **srma**", "**uyacak**" (for *uzayacak*), "Şapkanını" |
| 3 | `bing` | most natural MT | 42.8 s | 51/51 | "cent" kept; "diye ağladı" for *she cried* |
| 4 | `google` | fluent, literal on idioms | 1.7 s | 51/51 | "buldozerlerle ezerek", straight quotes |
| 5 | `yandex` ≈ `modernmt` | like Google, more calques | 16–18 s | 51/51 | ModernMT adds spaces before punctuation |
| 6 | `ollama` aya-expanse:8b | idiomatic, but changes numbers | 221 s / 16 seg | partial | "otuz yedi sent" instead of 87 cents |
| 7 | `ollama` gemma3:4b (± polish) | invents words | 481 s / 720 s | 51/51 | "melekse", "Şaptonu"; 4B is too small |
| 8 | `argos` (offline) | literal, often ungrammatical | 820 s | 51/51 | plain text only |

**Recommendation**

- Best quality: `--engine opencode --polish --fallback bing` (or `--fallback google`). Run it again
  later to fill the gaps: cached segments are reused, and only missing ones go to the model.
- Fast and good: `--engine bing` (needs `pip install translators`), or `--engine google` with no setup.
- Private or offline: `--engine ollama -m aya-expanse:8b` (or a larger model if you have the RAM), or `argos`.

Even the best output still benefits from a human edit before publication.

## OpenCode (free Zen models)

`opencode run` runs inside a private agent directory whose `opencode.json` defines a tool-less `epubtr`
agent. That agent's system prompt is the literary-translation prompt. The free models are tried in this
order:

`big-pickle`, `nemotron-3-ultra-free`, `longcat-2.5-preview-free`, `mimo-v2.6-flash-free`,
`muse-spark-1.3-contributor-free`, `space-bunny-free`, `ling-3.0-flash-fin-free`,
`nemotron-3.5-lightning-free`, `ling-3.1-flash-free`, `fledge-alpha-free`

What we saw in the real run (2026-10-05, 11:08–14:48 TRT):

- The free tier is **rate-limited per IP**. The first five models answered `Rate limit exceeded`
  within about 2 s each, and epub-tr moved on to `opencode/space-bunny-free`. **Every** translated or
  polished segment came from that model (checked in OpenCode's session database). The summary's
  `engine_models` now records this.
- `space-bunny-free` is slow: about 290 s per call on average. Some calls hit the 600 s timeout, and
  some returned empty output (exit 0). epub-tr now switches models on empty output too.
- Two parallel OpenCode workers occasionally hit `database is locked` inside OpenCode's own SQLite
  database. The retry handles it. Use `--workers 1` if you see it often.
- Quotas reset after a few hours. `scripts/opencode_when_available.sh` waits for a working model and
  then runs the draft, polish and bilingual passes.

Options: `-m opencode/<model>` or `EPUB_TR_OPENCODE_MODEL` picks the first model, and
`EPUB_TR_OPENCODE_TIMEOUT` sets seconds per call (default 600).

## Other engines

| engine | type | needs | notes |
|---|---|---|---|
| `ollama` | local LLM | [Ollama](https://ollama.com) running, a pulled model | `EPUB_TR_OLLAMA_MODEL`, `OLLAMA_HOST`, `EPUB_TR_OLLAMA_CTX`, `EPUB_TR_OLLAMA_MAX_TOKENS` |
| `google` | free web endpoints | – | 4,500 characters per request, 4 workers |
| `bing`, `yandex`, `modernmt` | free web translators | `pip install translators` (GPL-3, optional) | 1,000 characters per request |
| `mymemory` | REST API | – | about 5,000 chars/day per IP anonymously; `MYMEMORY_EMAIL` raises it to 50,000 |
| `lingva` | Google front-end | a working instance (`LINGVA_URL`) | public instances are often down |
| `libretranslate` | REST API | own server (`LIBRETRANSLATE_URL`) or a key | |
| `argos` | offline MT | `pip install argostranslate` | the en→tr model downloads on first use |
| `openrouter`, `gemini`, `groq`, `mistral`, `openai` | OpenAI-compatible APIs | free-tier key in `*_API_KEY` | model and URL can be overridden with `EPUB_TR_<PRESET>_MODEL` and `_BASE_URL` |
| `echo` | no-op | – | for structure tests |

LLM engines (`opencode`, `ollama`, the API presets) use the full literary pipeline: context, glossary,
names and polish. MT engines get batches of segments with placeholders.
