# Rules for Claude in this repository

This repository is a bibliography on acid rock drainage (ARD) for an internship (Zotero library “Stage AMAP 2026”).
Everything is in English; article titles stay in their original language.

- `data/corpus.json` is the source of truth. Only add or remove a reference when explicitly asked, or for an
  obvious duplicate or a DOI that does not resolve (say so in the pull request).
- To add DOIs: `python scripts/integrate.py --doi <DOI> [--theme … --region …]`, then fill in question, site,
  methods, results and contribution from what you have actually read.
- `reading_level` states what was read (metadata, abstract, full text). Never describe content beyond it.
- Main theme: "Geomorphology & ARD", "Hydrochemistry & ARD", "Soil & ARD", otherwise "Other – <sub-theme>".
- Region: one of the values of `REGIONS` in `scripts/build.py`.
- The synthesis is in `data/synthesis.html`; references are written `[[Key]]`.
- Before proposing a change: `python scripts/build.py && python -m pytest -q tests` must pass.
- Never add paper PDFs to the repository, and never use unauthorised access sources (Sci-Hub, etc.).
