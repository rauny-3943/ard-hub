# ARD Hub

A living bibliography on **natural acid rock drainage (ARD)** in mountain and cold regions, with a focus on the **Pyrenees** and the **Cordillera Blanca**.

**→ [Open the literature map](https://rauny-3943.github.io/ard-hub/)** · **→ [See the new candidates](https://rauny-3943.github.io/ard-hub/candidates.html)**

---

## Explore the literature

The **literature map** gathers 215 references (24 from the initial bibliography, 191 found by citation searching).

- **Search and filter** by keyword, theme (geomorphology, hydrochemistry, soil, other), region, country, origin (natural, mixed, mining) and reading level.
- **Timeline** shows when each topic took off; **citation graph** shows which papers build on which.
- **Reference cards** give the question, site, methods, key results and contribution of each paper, with links to the papers it builds on and those that follow it up.
- **Synthesis** at the bottom: history of ideas by theme, comparison between regions, gaps and directions for the internship.

Each card states its **reading level**: *full text*, *abstract* or *metadata*. A card never says more than what was actually read.

## Find new papers

Every Monday, a search on [OpenAlex](https://openalex.org) (plus Semantic Scholar recommendations) looks for recent papers that are not in the corpus yet. They appear on the **[New candidates](https://rauny-3943.github.io/ard-hub/candidates.html)** page.

**How candidates are ranked.** Score = number of searches that found the paper + 2 for each corpus paper it cites. Papers that cite the corpus are usually the relevant ones; a score of 1 is often noise. The page also shows which search brought each candidate, so noisy queries are easy to spot.

**How to screen them.**

1. On the candidates page, click **Keep** or **Reject** under each paper. For kept papers you can pick a theme and a region.
2. Click **Send decisions to GitHub** at the bottom of the screen. GitHub opens a pre-filled issue: click **Create**.
3. A few minutes later the issue is closed with a short report, kept papers are on the map, and rejected papers never come back.

Your choices are remembered in your browser until you send them. You need to be signed in to GitHub as the owner (or a collaborator) of the repository.

**Search now or change the search.** Run it any time from **Actions → Literature watch → Run workflow**. Queries and the papers whose citations are followed are listed in [`config/search.yaml`](config/search.yaml) (titles and abstracts only; `"exact phrase"`, `AND`, `OR`, `NOT` allowed).

## Download

From the map (**Downloads** section):

| File | Use |
|---|---|
| `ARD_corpus.bib` | import into Zotero (*File → Import*); keywords become tags: `theme:`, `location:`, `origin:`, `status:`, `reading:` |
| `ARD_reading_table.xlsx` / `.csv` | one row per paper: year, authors, theme, site, methods, key results, citations |

## On your own computer (optional)

With Python installed, two scripts work on files that stay on your machine:

- `python scripts/compare_local.py` compares your PDFs (folder `pdfs/`, never uploaded) and your Zotero library with the corpus, and lists what is missing.
- `python scripts/pdf_notes.py --all` drafts “full text” reading cards from your PDFs with an LLM, for you to review.

## Sources and limits

Metadata and citations come from OpenAlex and Crossref; open-access links from Unpaywall via OpenAlex. Google Scholar has no API and is not queried automatically; paywalled PDFs are never shared. Some cards rest on abstracts or metadata only, and Spanish-language regional literature is probably incomplete. The full list of choices and limits is on the map.

---

Setting up or maintaining the repository: see [`docs/SETUP.md`](docs/SETUP.md). Code under the MIT licence; reading cards written for this project.
