# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Türkçe: [CHANGELOG.tr.md](CHANGELOG.tr.md).

## [Unreleased]

### Added

- Project banner (`docs/images/banner.svg`, text outlined so it renders the same everywhere) at the top of
  both READMEs, a 1280×640 social preview (`docs/images/social-preview.png`) and `scripts/outline_banner.py`
  that builds both from `docs/images/banner.src.svg`.
- Release workflow: a `pypi` job uploads the wheel and sdist to PyPI with `twine` and verifies
  `pip install epub-tr==X.Y.Z` when the `PYPI_API_TOKEN` secret is set; otherwise it is skipped with a notice.
  Trusted publishing is documented as the alternative.
- epub-tr is on PyPI: `pip install epub-tr`. Version 1.1.0 was uploaded from the exact GitHub release files
  (SHA-256 verified). The README has a PyPI badge and `pip install` instructions, and release notes now
  start with `pip install epub-tr==X.Y.Z`.

## [1.1.0] - 2026-10-08

### Added

- Test suite: 120 offline tests (fake engines and mocked HTTP, no network) cover placeholder encoding,
  EPUB reading and writing, the pipeline, every engine adapter, the prompts and the CLI. Coverage is 93%.
- CI on Ubuntu, Windows and macOS with Python 3.10–3.13, plus ruff, codespell, markdownlint, an offline
  link check, a package build with `twine check`, a clean-venv wheel install and an EPUBCheck 5.4.0 job.
- CodeQL (Python and Actions), a weekly link check, Dependabot (pip and GitHub Actions) and pre-commit hooks.
- Tag-driven release workflow: it checks that the tag matches the version, runs the tests, builds the
  sdist and wheel, writes `SHA256SUMS.txt` and publishes a GitHub release with notes in English and Turkish.
- Release tooling: `scripts/release.py` and `scripts/release_notes.py`. Validation tooling:
  `scripts/validate_epub.py` (EPUBCheck JSON) and `scripts/check_links.py` (Markdown links and anchors).
- Community files: CONTRIBUTING (EN/TR), CODE_OF_CONDUCT, SECURITY, bilingual issue forms (bug,
  translation quality, feature) and a pull request template.
- Docs: `docs/ARCHITECTURE.md`, `docs/ENGINES.md` and `docs/AUTOMATION.md`, each with a Turkish version.
- Real OpenCode results on *The Gift of the Magi*: raw, polished and bilingual EPUBs, run logs, a
  side-by-side comparison and EPUBCheck output, all committed under `out/`.
- `engine_models` in the run summary records the model each engine actually ended on. OpenCode can
  switch models during a run.

### Changed

- OpenCode now skips to the next free model when a model returns empty output. Before, it only did
  this on rate limits. In the real run, one model returned nothing over and over.
- The engine list in the run header reads `opencode/big-pickle` instead of `opencode/opencode/big-pickle`.
- Minimum Python is now 3.10. Package metadata is complete: classifiers, URLs, keywords and `dev` extras.

### Fixed

- Bilingual output: rebuilt inline anchors kept their `id`, so EPUBs could contain duplicate IDs.
- The running glossary accepted reversed or invented entries from the model, such as
  `Hediyenin Getirdiği Mutluluk => The Gift of the Magi`. A source term is now kept only if it occurs in the chunk, and stale entries from older runs are ignored.
- MyMemory recursed forever on a single sentence longer than the 500-byte limit. Text is now split by
  sentence, then word, then character.
- Plain text taken from a segment merged words across `<br/>`.
- No pointless back-off sleep after the last retry.
- On Windows, the OpenCode agent config was written without UTF-8. Timed-out OpenCode processes are now reaped.
- The CLI no longer crashes on consoles that cannot encode Turkish characters.
- EPUB files and the cache are now closed properly.

## [1.0.0] - 2026-10-03

### Added

- Structure-preserving EPUB 2/3 reader and ZIP-level writer: XHTML, OPF language and title, and nav and
  NCX labels are rewritten; everything else is copied byte for byte.
- Inline-markup placeholders (`<gN>…</gN>`, `<xN/>`), with a lenient fallback that keeps anchors and links.
- Engines:
  - OpenCode: free Zen models, with automatic model switching on rate limits.
  - Ollama.
  - Google: free endpoints.
  - Bing, Yandex and ModernMT, through `translators`.
  - MyMemory, Lingva and LibreTranslate.
  - Argos: offline.
  - OpenAI-compatible presets: OpenRouter, Gemini, Groq, Mistral and OpenAI.
- Literary LLM pipeline:
  - chunking with stable segment IDs, a context window and a running glossary;
  - proper-name detection;
  - a Turkish literary prompt and a choice of dialogue style (`quotes` or `dash`);
  - an optional polish pass.
- Bilingual output, a fallback chain for each chunk, retries, SQLite cache and resume, chapter and
  segment selection, and stats and JSONL dumps.
- TOC harmonisation and re-wrapping of single-element segments. Gutenberg boilerplate is skipped by default.
- Test report on two Project Gutenberg books (EPUBCheck: no new errors) and a survey of 15 open-source translators.

[Unreleased]: https://github.com/cumabozkurt/epub-tr/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/cumabozkurt/epub-tr/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/cumabozkurt/epub-tr/releases/tag/v1.0.0
