# pdfs/ folder

Put your paper PDFs here (subfolders are fine). This folder is ignored by git: the PDFs are never published.

Naming a file after its DOI helps identify it, for example `10.1016_j.scitotenv.2021.146070.pdf`.

Then:

```bash
python scripts/compare_local.py   # what is missing, what is outside the corpus
python scripts/pdf_notes.py --all # "full text" reading notes drafted by an LLM, to be reviewed
```

You can also point directly at the Zotero storage folder:
`python scripts/compare_local.py --folder ~/Zotero/storage`.
