# Automation: CI, checks and releases

Türkçe: [AUTOMATION.tr.md](AUTOMATION.tr.md) · Back to [README](../README.md)

## Workflows

| workflow | trigger | what it does |
|---|---|---|
| [CI](../.github/workflows/ci.yml) | push and PR to `main`, manual | **lint**: ruff, codespell, markdownlint, relative links and anchors, release-notes build · **test**: pytest with coverage on Ubuntu, Windows and macOS × Python 3.10, 3.11, 3.12, 3.13, plus a CLI smoke test · **package**: sdist and wheel, `twine check --strict`, version consistency, wheel installed in a clean venv that translates a sample offline · **epubcheck**: EPUBCheck 5.4.0 on monolingual and bilingual outputs of both sample books; fails if an output has more errors than its source |
| [CodeQL](../.github/workflows/codeql.yml) | push, PR, weekly | `security-and-quality` queries for Python and GitHub Actions |
| [Links](../.github/workflows/links.yml) | Markdown changes, weekly | relative links, anchors and external URLs in every tracked Markdown file |
| [Release](../.github/workflows/release.yml) | tag `v*`, manual (with a tag) | tag = `pyproject.toml` = `epub_tr.__version__` check, ruff, pytest, build, `twine check`, `SHA256SUMS.txt`, notes from both changelogs, then `gh release create --verify-tag` with the wheel, sdist and checksums; finally checks that all three assets are on the release |
| [Dependabot](../.github/dependabot.yml) | weekly | updates pip dependencies and GitHub Actions |

Tests never use the network. Engines are faked and HTTP is mocked. That keeps CI deterministic and
independent of free-tier quotas. Real-engine results live in [TEST_REPORT.md](../TEST_REPORT.md).

## Local equivalents

```bash
pip install -e ".[dev]"
ruff check . && codespell && python -m pytest -q --cov=epub_tr
python scripts/check_links.py            # add --offline to skip external URLs
npx markdownlint-cli2@0.23.3 "**/*.md"
python -m build && twine check --strict dist/*
python scripts/validate_epub.py          # needs Java + epubcheck (or EPUBCHECK_JAR)
python scripts/release_notes.py v1.1.0   # preview the release notes
```

## Releasing

1. Add the changes under a new `## [X.Y.Z] - YYYY-MM-DD` heading in **both** `CHANGELOG.md` and
   `CHANGELOG.tr.md`, and commit.
2. `python scripts/release.py X.Y.Z --dry-run`, then `python scripts/release.py X.Y.Z`. The script
   refuses to run unless you are on `main` with a clean tree, the tag is new, and both changelog
   sections exist. It then bumps `pyproject.toml` and `epub_tr/__init__.py`, runs ruff and pytest,
   commits `release: vX.Y.Z`, creates an annotated tag and pushes `main` and the tag. It never force-pushes.
3. The **Release** workflow builds and publishes. Verify the assets with `sha256sum -c SHA256SUMS.txt`.

## PyPI

The **pypi** job in the Release workflow uploads the same wheel and sdist to
PyPI (`pypi.org/project/epub-tr`) with `twine`, then installs `epub-tr==X.Y.Z` from PyPI in a clean
venv to prove it works. It runs only when the repository secret `PYPI_API_TOKEN` exists. Without it the job
logs a "PyPI skipped" notice and the release still succeeds.

- **Token setup (current):** create an API token on PyPI (first upload: an account-wide token; afterwards
  a token scoped to `epub-tr`), then
  `gh secret set PYPI_API_TOKEN -R cumabozkurt/epub-tr` and paste it at the prompt.
- **Publish an existing tag:** Actions → Release → *Run workflow* with e.g. `v1.1.0`. Uploads use
  `--skip-existing`, so rerunning is safe.
- **Trusted publishing (alternative, no secret):** on PyPI add a trusted publisher for owner `cumabozkurt`,
  repository `epub-tr`, workflow `release.yml` (environment `pypi`). Then give the job
  `environment: pypi` and `permissions: id-token: write`, and replace the twine step with
  `uses: pypa/gh-action-pypi-publish@release/v1` (`packages-dir: dist/`, after removing `SHA256SUMS.txt`
  from `dist/`). Delete the token secret afterwards.

Until the first upload, install from the wheel attached to the GitHub release or from `git+https://…@vX.Y.Z`.

## Release evidence

| version | date | release | workflow | assets |
|---|---|---|---|---|
| v1.0.0 | 2026-10-03 | [release](https://github.com/cumabozkurt/epub-tr/releases/tag/v1.0.0) | created manually with `gh release create` (before the workflow existed) | – |
| v1.1.0 | 2026-10-08 | [release](https://github.com/cumabozkurt/epub-tr/releases/tag/v1.1.0) | [Release run 37689167063](https://github.com/cumabozkurt/epub-tr/actions/runs/37689167063) ✅ (test + build, publish) | `epub_tr-1.1.0-py3-none-any.whl`, `epub_tr-1.1.0.tar.gz`, `SHA256SUMS.txt` (verified with `sha256sum -c`) |
