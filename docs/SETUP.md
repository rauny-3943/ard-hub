# Setup and maintenance

Technical notes for whoever maintains the repository. Users only need the [README](../README.md).

## One-time setup

1. Repository **public** (GitHub Pages is free for public repositories only).
2. *Settings → Pages → Source*: **GitHub Actions**.
3. *Settings → Actions → General → Workflow permissions*: **Read and write permissions**.
4. *Settings → Secrets and variables → Actions*:

| Secret | Needed for |
|---|---|
| `OPENALEX_API_KEY` | literature watch and screening (free key at openalex.org/settings/api) |
| `CONTACT_EMAIL` | recommended, sent to OpenAlex |
| `S2_API_KEY` | optional, Semantic Scholar recommendations |
| `ANTHROPIC_API_KEY` | optional, `@claude` in issues |

## How it works

| Workflow | Trigger | What it does |
|---|---|---|
| `publish.yml` | push to `main` (data, templates, scripts), or called by the others | builds `site/` (map, candidates page, .bib, .xlsx, .csv), runs the tests, deploys to Pages |
| `watch.yml` | Monday 06:17 UTC, or by hand | `scripts/search.py` → commits `data/candidates/` → calls `publish.yml` |
| `screening.yml` | issue titled “Screening decisions …” opened by the owner/collaborators (sent from the candidates page) | `scripts/apply_screening.py` writes the decisions into `to_screen.csv`, then `integrate.py` → commits → calls `publish.yml` → comments and closes the issue |
| `integrate.yml` | push that changes `data/candidates/to_screen.csv` (manual editing of the sheet) | `scripts/integrate.py` (keep → corpus, reject → `rejected.txt`) → commits → calls `publish.yml` |
| `check.yml` | pull requests | build + tests |
| `synthesis.yml` | by hand | drafts synthesis text with GitHub Models, opens a pull request for review |
| `claude.yml` | `@claude` in an issue (owner/collaborators only) | Claude edits the corpus following `CLAUDE.md`, opens a pull request |

## Files

```
data/corpus.json            source of truth (one entry per reference)
data/synthesis.html         synthesis text; references written [[Key]]
data/notes/<Key>.json       reading cards drafted from PDFs (pdf_notes.py), merged at build time
data/candidates/            YYYY-MM-DD.json/.md per watch, to_screen.csv, rejected.txt, state.json
config/search.yaml          watch queries, followed papers, min_score, max_per_query
templates/                  map_template.html, candidates_template.html
scripts/                    build, search, integrate, compare_local, pdf_notes, synthesis_llm, llm, common
tests/test_consistency.py   map, table and .bib contain exactly the same keys and DOIs
```

## Local use

```bash
python -m venv .venv && .venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py && python -m pytest -q tests  # then open site/index.html
```

- Edit the screening sheet by hand: in `to_screen.csv` the first column is `decision`, so each pending line starts with a comma; type `keep` or `reject` before that first comma.
- Add DOIs by hand: `python scripts/integrate.py --doi 10.xxxx/yyyy --theme "Soil & ARD" --region Pyrenees`
- Compare PDFs and Zotero: `python scripts/compare_local.py [--folder ~/Zotero/storage] [--zotero data/zotero.bib]`
  (keep a Zotero export up to date with Better BibTeX → *Export Collection* → *Better BibLaTeX* → *Keep updated*)
- Reading cards from PDFs: `python scripts/pdf_notes.py --all`, then set `"reviewed": true` in `data/notes/<Key>.json`
- LLM provider for local scripts: `LLM_PROVIDER` = `github` (token with *Models* permission), `openai`, `anthropic` or `ollama`; model in `LLM_MODEL`.

## Vocabularies

- Main theme: `Geomorphology & ARD`, `Hydrochemistry & ARD`, `Soil & ARD`, or `Other – <sub-theme>`.
- Region: `Cordillera Blanca`, `Pyrenees`, `Alps`, `Rocky Mountains`, `Arctic & subarctic`, `Other Andes`, `Antarctica`, `Himalaya & Tibet`, `Other`, `Global / no location`, `To be specified`.
- Reading level: `metadata`, `abstract`, `full text`. Status: `initial bibliography`, `new`.

## Rules

PDFs and abstracts are never committed (copyright). No Sci-Hub or similar sources. Google Scholar is used by hand only.
