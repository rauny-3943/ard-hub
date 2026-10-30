# ARD Hub — a bibliography on acid rock drainage

Working repository for an internship bibliography (Zotero library “Stage AMAP 2026”): natural acid rock drainage (ARD) in mountains and cold regions, with priority on the **Pyrenees** and the **Cordillera Blanca**.

The repository does four things:

1. **Publishes the map**: whenever the corpus changes, GitHub rebuilds the *ARD Literature Map* (timeline, citation graph, filters, reference cards, synthesis), the reading table (.xlsx / .csv) and the BibLaTeX file, and publishes them on GitHub Pages.
2. **Runs a literature watch**: every Monday, an OpenAlex search (plus Semantic Scholar recommendations) proposes new publications in a *pull request* for you to screen.
3. **Compares your PDFs with the library**: on your computer, a script lists which corpus papers you are missing, which PDFs are outside the corpus, and how your Zotero library differs from the corpus.
4. **Summarises with an LLM**: “full text” reading notes drafted from your PDFs, and synthesis proposals, always subject to your review.

> **PDFs are never published.** The repository is public: it only contains metadata and reading notes. PDFs stay in `pdfs/` (ignored by git) or in Zotero.

---

## Contents

- [Repository layout](#repository-layout)
- [Going live (once)](#going-live-once)
- [Day-to-day use](#day-to-day-use)
- [Zotero](#zotero)
- [LLM options and costs](#llm-options-and-costs)
- [Sources: what is used and what is not](#sources-what-is-used-and-what-is-not)
- [Useful open-source tools](#useful-open-source-tools)
- [Corpus format](#corpus-format)

---

## Repository layout

```
data/
  corpus.json            source of truth: one entry per reference (see “Corpus format”)
  synthesis.html         written synthesis; references are written [[Key]]
  notes/<Key>.json       reading notes drafted from a PDF (pdf_notes.py), merged at build time
  candidates/            literature watch: reports, to_screen.csv, rejected.txt, state.json
config/search.yaml       scope of the watch: queries, followed papers, dates
templates/map_template.html   map template (HTML + CSS + JS, D3 from cdnjs)
scripts/
  build.py               corpus -> site/ (map, .xlsx, .csv, .bib) + consistency check
  search.py              OpenAlex + Semantic Scholar watch -> data/candidates/
  integrate.py           screened candidates or DOIs entered by hand -> corpus
  compare_local.py       local PDFs / Zotero / corpus -> reports/ (private)
  pdf_notes.py           local PDF -> JSON reading note drafted by an LLM (to review)
  synthesis_llm.py       synthesis proposals drafted by an LLM (to review)
  llm.py, common.py      shared helpers
tests/test_consistency.py  same keys and DOIs in the map, table and .bib; no invented key in the synthesis
.github/workflows/       publish, check, literature watch, integrate screening, draft synthesis, Claude
pdfs/                    your PDFs (ignored by git)
```

## Going live (once)

1. **Create the repository** on GitHub: *New repository* → name `ard-hub` → **Public** → without a README (there already is one).
2. **Push this folder** from your computer:
   ```bash
   cd ard-hub
   git remote add origin https://github.com/<your-account>/ard-hub.git
   git push -u origin main
   ```
3. **Turn on GitHub Pages**: *Settings → Pages → Build and deployment → Source: GitHub Actions*.
   The “Publish the map” workflow runs; the map appears at `https://<your-account>.github.io/ard-hub/`.
   If the first run happened before you changed this setting, re-run it from the *Actions* tab.
4. **Allow automatic pull requests**: *Settings → Actions → General → Workflow permissions*:
   tick *Read and write permissions* and *Allow GitHub Actions to create and approve pull requests*.
5. **Add the secrets** (*Settings → Secrets and variables → Actions → New repository secret*):

   | Secret | Required? | Where to get it |
   |---|---|---|
   | `OPENALEX_API_KEY` | **yes** for the watch | free account on openalex.org, then openalex.org/settings/api (free budget of $1/day, plenty for this use) |
   | `CONTACT_EMAIL` | recommended | your address, sent politely to OpenAlex |
   | `S2_API_KEY` | optional | “Request an API key” form on semanticscholar.org/product/api |
   | `ANTHROPIC_API_KEY` | optional | only for the `@claude` workflow (pay-as-you-go) |

   Without an OpenAlex key the watch stops quickly: the keyless budget is shared by the whole IP address of the GitHub servers.

6. **Test**: *Actions* tab → “Literature watch” → *Run workflow* (start date, e.g. `2026-01-01`).

### Locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/build.py && python -m pytest -q tests   # builds site/; open site/index.html
```

For the watch or integration on your machine, export `OPENALEX_API_KEY` first.

## Day-to-day use

### Literature watch and screening

1. Every Monday, the workflow opens a pull request “Literature watch …: N candidates to screen”. Its description lists candidates by **score** = number of routes that found the paper (queries, citations of followed papers, recommendations) + 2 × the number of corpus references it cites.
2. In the pull request, open `data/candidates/to_screen.csv` (pencil icon on GitHub, or in a spreadsheet) and write `keep` or `reject` in the `decision` column. You can also fill in `main_theme`, `region`, `country`, `site`, `origin`, `trigger`.
3. Commit on the same branch: the “Integrate screening” workflow adds the kept references to `corpus.json`, files the rejected ones in `rejected.txt` (they will not come back), rebuilds and checks.
4. Merge the pull request: the online map is updated. (If you close it without merging, the same candidates may come back next week.)

New references enter at the **“metadata”** reading level, with the OpenAlex abstract in `openalex_abstract`. Then complete question, methods, results and contribution (by hand, with `pdf_notes.py`, or by asking `@claude`).

### Adding DOIs by hand

```bash
python scripts/integrate.py --doi 10.xxxx/aaaa 10.yyyy/bbbb --theme "Soil & ARD" --region Pyrenees --country Spain
python scripts/build.py
```

Main themes: `Geomorphology & ARD`, `Hydrochemistry & ARD`, `Soil & ARD`, otherwise `Other – <sub-theme>`.
Regions: `Cordillera Blanca`, `Pyrenees`, `Alps`, `Rocky Mountains`, `Arctic & subarctic`, `Other Andes`, `Antarctica`, `Himalaya & Tibet`, `Other`, `Global / no location`, `To be specified`.

### Comparing your PDFs with the library

```bash
python scripts/compare_local.py                                     # pdfs/ folder
python scripts/compare_local.py --folder ~/Zotero/storage --zotero data/zotero.bib
```

The report `reports/comparison_<date>.md` (never published) lists:
- corpus references **without a local PDF**, by priority (initial bibliography first, then the least-read cards), with the open-access link when there is one;
- **PDFs outside the corpus**, with a ready-to-copy `integrate.py --doi …` command;
- **unidentified PDFs** (rename them with their DOI, or install `pdf2doi`);
- with a Zotero export: what is in the corpus but not in Zotero, and the reverse.

### “Full text” notes from your PDFs

```bash
python scripts/compare_local.py          # builds the PDF -> key matches
python scripts/pdf_notes.py --all --dry-run
python scripts/pdf_notes.py --all        # or: --pdf pdfs/x.pdf --key Zarroca2021
```

Each note goes to `data/notes/<Key>.json` with `"reviewed": false`. Read it, correct it, set `"reviewed": true`, then `python scripts/build.py`: the map shows “full text” and a note records where the card came from. Commit the notes (they are summaries, not the papers).

### Synthesis

- `data/synthesis.html` is the published text. References are written `[[Key]]` and become links to the cards. `<!--TABLE_REGIONS-->` inserts the computed regional table.
- “Draft synthesis” workflow (*Actions → Run workflow*): `new` mode (paragraphs for references not cited yet) or `full` mode (complete draft). The result arrives in a pull request; keys invented by the model are removed automatically. Nothing is published without your review.
- Figures written out in the synthesis (e.g. “12 references”) are not updated automatically: check them after large additions.

### Asking Claude in an issue (optional)

With the `ANTHROPIC_API_KEY` secret, write for example in an issue:
“@claude add 10.1016/j.xxx to the corpus, theme Soil & ARD, region Pyrenees, fill in the card from the abstract, and propose a sentence for the synthesis”.
Claude follows `CLAUDE.md` (repository rules) and opens a pull request. Only you and your collaborators can trigger it (public repository).

### Republishing the map on Claude

`build/ard_map_fragment.html` is the same map in Claude artifact format: ask Claude to republish this file to the “ARD Literature Map” artifact to keep both versions aligned.

## Zotero

- **Keep a .bib up to date in the repository**: with [Better BibTeX](https://retorque.re/zotero-better-bibtex/exporting/auto/), right-click the “Stage AMAP 2026” collection → *Export Collection* → format *Better BibLaTeX* → tick **Keep updated** → save as `ard-hub/data/zotero.bib`. Zotero rewrites the file at every change; `compare_local.py` reads it. It is ignored by git by default (remove the line from `.gitignore` to publish it).
- **Import the corpus into Zotero**: *File → Import* → `site/ARD_corpus.bib` (or the “Open ARD_corpus.bib” link on the map). The keywords `theme: …`, `location: …`, `origin: …`, `status: …`, `reading: …` become Zotero tags.
- **Get PDFs legally**: *Edit → Settings → General → Locate → OpenURL resolver* (your university library's) and your institution's proxy; Zotero also finds open-access versions (Unpaywall) with “Find Available PDF”.
- **Chat with your library**: [zotero-mcp](https://github.com/54yyyu/zotero-mcp) connects Zotero to Claude Desktop (semantic search, reading PDFs and annotations).
- **Storage**: 300 MB free on Zotero, then paid plans, or your own WebDAV server.

## LLM options and costs

`scripts/llm.py` picks the service with `LLM_PROVIDER`:

| Provider | Settings | Cost | Notes |
|---|---|---|---|
| `github` (default) | `GITHUB_TOKEN` (automatic in Actions with `models: read`; locally, a personal access token with the *Models* permission); `LLM_MODEL=openai/gpt-4.1-mini` | free within the free tier limits | per-request size limits: keep `--batch-size` and `--max-chars` modest |
| `openai` | `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` for any compatible service | pay-as-you-go | |
| `anthropic` | `ANTHROPIC_API_KEY`, `LLM_MODEL` (a Claude model ID) | pay-as-you-go | |
| `ollama` | `LLM_MODEL=llama3.1` (Ollama installed) | free, local | nothing leaves your machine; quality depends on the model |

For **sourced question answering over your PDFs** (“which sites measure Al and Ni in rock glacier springs?”), [PaperQA2](https://github.com/future-house/paper-qa) works directly on the `pdfs/` folder: `pip install paper-qa`, then `cd pdfs && pqa ask "…"` (OpenAI by default; Claude or Ollama also work).

## Sources: what is used and what is not

- **Used**: OpenAlex (metadata, citations, abstracts), Semantic Scholar (recommendations), doi.org (DOI checks), and Crossref / Unpaywall through the OpenAlex metadata.
- **Google Scholar**: no official API; automated scraping is blocked by captchas and against its terms of use. Use it by hand, with the Zotero browser connector.
- **Sci-Hub and similar sites**: not used; they give unauthorised access to copyrighted papers. For PDFs: open access (Unpaywall, HAL, CORE, institutional repositories), your library's access, interlibrary loan, or asking the authors.

## Useful open-source tools

| Tool | What it is useful for here |
|---|---|
| [pyalex](https://github.com/J535D165/pyalex) | Python client for OpenAlex, to write your own queries |
| [paper-search-mcp](https://github.com/openags/paper-search-mcp) | multi-source search (HAL, CORE, Europe PMC…) from Claude; keep its Sci-Hub option disabled |
| [Local Citation Network](https://github.com/LocalCitationNetwork/LocalCitationNetwork.github.io) | load the corpus DOIs to see the “Top Cited / Top Citing” papers that are missing |
| [ASReview](https://github.com/asreview/asreview) | assisted screening when a watch returns hundreds of candidates (import `to_screen.csv`) |
| [pdf2doi](https://pypi.org/project/pdf2doi/) / [GROBID](https://grobid.readthedocs.io/) | identify and structure difficult PDFs |
| [zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily) | example of a watch ranked by similarity with your Zotero library (preprints only) |

## Corpus format

Each entry of `data/corpus.json` (`refs`) has: `key, doi, openalex, url, oa_url, year, authors ("Last, First"), title, venue, volume, issue, pages, publisher, doc_type, peer_reviewed, status ("initial bibliography" | "new"), context, main_theme, secondary_themes, region, country, site, origin, trigger, question, methods, results, contribution, reading_level ("metadata" | "abstract" | "full text"), cites (corpus keys cited), found_via, doi_verified, note`.
“Cited by” is not stored: `build.py` computes it by inverting `cites`. `meta.history` keeps track of automated changes.

The reading notes were originally written in French and translated into English; article titles are left in their original language.

## Licence

Code under the MIT licence (see `LICENSE`). Data: OpenAlex metadata (CC0) and reading notes written for this project; choose their licence before wider distribution.
