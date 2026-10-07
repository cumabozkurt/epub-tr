# Contributing to epub-tr

Thanks for helping. Bug reports, translation-quality samples, new engines and doc fixes are all welcome.
Türkçe: [CONTRIBUTING.tr.md](CONTRIBUTING.tr.md).

## Ground rules

- Be kind. This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security problems privately. See [SECURITY.md](SECURITY.md).
- Keep the book intact. A change must not add EPUBCheck errors, lose markup, images or links, or reorder the spine.
- No paid services by default. Every engine has to keep working with no paid key.
- Never commit API keys, cookies or copyrighted books. `samples/` holds only public-domain Project Gutenberg texts.

## Development setup

```bash
git clone https://github.com/cumabozkurt/epub-tr.git && cd epub-tr
python3 -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install                                 # optional: ruff, codespell, markdownlint on commit
```

## Checks (the same ones CI runs)

```bash
ruff check .                                  # lint (pyflakes, pycodestyle, bugbear, isort, pyupgrade)
codespell                                     # spelling (Turkish files are skipped)
python -m pytest -q --cov=epub_tr             # 120 offline tests, no network needed
python scripts/check_links.py --offline       # Markdown links and anchors
npx markdownlint-cli2@0.23.3 "**/*.md"        # Markdown style
python -m build && twine check --strict dist/*  # packaging
python scripts/validate_epub.py               # EPUBCheck on the sample books (needs Java + epubcheck)
```

Tests never touch the network. Engines are faked (`tests/conftest.py`), and HTTP engines are tested
with a mocked `requests`. If a test really needs the internet, mark it `@pytest.mark.network`.

## Making a change

1. Open an issue first for anything bigger than a small fix, so we can agree on the approach.
2. Branch from `main`, keep the change focused, and add or extend a test in `tests/`.
3. For translation-quality changes (prompts, glossary, polish), include a before/after sample.
   `scripts/compare.py` builds a side-by-side table from `--dump` files.
4. Update `README.md` **and** `README.tr.md` when you change behaviour or options, and add a line under
   `## [Unreleased]` in **both** `CHANGELOG.md` and `CHANGELOG.tr.md`.
5. Open a pull request. The template asks for the checks above.

## Adding an engine

Subclass `epub_tr.engines.base.Engine`, then:

- implement `translate_one()` or `translate_batch()` for machine translation, or `complete(system, user)`
  for an LLM (and set `is_llm = True`);
- implement `check()` so it raises `EngineUnavailable` with an install hint;
- register the engine in `ENGINES` in `epub_tr/engines/__init__.py`;
- add tests with a mocked transport, and a row in [docs/ENGINES.md](docs/ENGINES.md) and both READMEs.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how segments, placeholders and the pipeline fit together.

## Releases (maintainer)

Releases come from tags. See [docs/AUTOMATION.md](docs/AUTOMATION.md):

```bash
python scripts/release.py 1.2.0 --dry-run   # checks branch, tree, changelog sections, tests
python scripts/release.py 1.2.0             # bumps, commits, tags v1.2.0, pushes; the workflow publishes
```
