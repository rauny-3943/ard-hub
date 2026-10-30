#!/usr/bin/env python3
"""Compare your local PDFs (and your exported Zotero library) with the corpus.

    python scripts/compare_local.py                          # PDFs in pdfs/
    python scripts/compare_local.py --folder ~/Zotero/storage --zotero data/zotero.bib

Each PDF is identified by its DOI (metadata, file name, text of the first pages, then pdf2doi if installed,
without web search), or failing that by its title. Writes to reports/ (ignored by git):
  comparison_YYYY-MM-DD.md   what is missing where
  matches.json               PDF -> DOI -> corpus key (also used by pdf_notes.py)
Nothing is published: your file names and paths stay on your machine.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from common import PDFS, REPORTS, ROOT, load_corpus, norm_doi, norm_title

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>{}]+", re.I)


def sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def clean_doi(d: str) -> str:
    d = norm_doi(d)
    d = re.sub(r"(\.pdf|/full|/abstract|/epdf)$", "", d)
    return d.rstrip(".,;:)]")


def pdf_text(p: Path, pages: int = 3) -> tuple[str, dict]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", {}
    try:
        r = PdfReader(str(p))
        meta = {k.strip("/").lower(): str(v) for k, v in (r.metadata or {}).items()}
        txt = "\n".join((r.pages[i].extract_text() or "") for i in range(min(pages, len(r.pages))))
        return txt, meta
    except Exception:
        return "", {}


def doi_from_pdf2doi(p: Path) -> str:
    try:
        import pdf2doi  # optional: pip install pdf2doi
    except ImportError:
        return ""
    try:
        pdf2doi.config.set("verbose", False)
        pdf2doi.config.set("websearch", False)   # no Google queries
        r = pdf2doi.pdf2doi(str(p))
        if r and r.get("identifier_type") == "DOI":
            return clean_doi(r["identifier"])
    except Exception:
        pass
    return ""


def read_bib(f: Path) -> list[dict]:
    """Minimal reader for a BibTeX/BibLaTeX export (Better BibTeX): key, doi, title, file."""
    t = f.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in re.finditer(r"@\w+\{([^,\s]+),(.*?)\n\}", t, re.S):
        body = m.group(2)
        def field(n):
            mm = re.search(rf"^\s*{n}\s*=\s*\{{(.*?)\}},?\s*$", body, re.M | re.I | re.S)
            return mm.group(1).strip() if mm else ""
        out.append({"key": m.group(1), "doi": clean_doi(field("doi")), "title": re.sub(r"[{}]", "", field("title")),
                    "file": field("file")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=str(PDFS), help="PDF folder (searched recursively)")
    ap.add_argument("--zotero", help="Zotero .bib export (Better BibTeX); default data/zotero.bib if it exists")
    a = ap.parse_args()

    refs = load_corpus()["refs"]
    by_doi = {norm_doi(r["doi"]): r for r in refs if r.get("doi")}
    by_title = {norm_title(r["title"]): r for r in refs}
    REPORTS.mkdir(exist_ok=True)
    f_match = REPORTS / "matches.json"
    cache = json.loads(f_match.read_text()) if f_match.exists() else {}

    pdfs = sorted(Path(a.folder).expanduser().rglob("*.pdf"))
    results = []
    for p in pdfs:
        h = sha1(p)
        if h in cache and cache[h].get("doi") is not None:
            c = dict(cache[h], file=str(p))
        else:
            txt, meta = pdf_text(p)
            doi, method = "", ""
            for source, val in [("metadata", " ".join(meta.values())), ("file name", p.stem.replace("_", "/")), ("text", txt)]:
                m = DOI_RE.search(val or "")
                if m:
                    doi, method = clean_doi(m.group(0)), source
                    break
            if not doi:
                doi = doi_from_pdf2doi(p)
                method = "pdf2doi" if doi else ""
            key = by_doi[doi]["key"] if doi in by_doi else ""
            if not key:  # fallback: a corpus title found in the file name or at the start of the text
                start = norm_title(p.stem), re.sub(r"[^a-z0-9]", "", txt.lower()[:3000])
                for nt, r in by_title.items():
                    if len(nt) > 25 and (nt[:40] in start[0] or nt[:40] in start[1]):
                        key, method = r["key"], (method + " + title").strip(" +")
                        break
            c = {"file": str(p), "doi": doi, "key": key, "method": method}
        cache[h] = c
        results.append(c)
    f_match.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    with_pdf = {c["key"] for c in results if c["key"]}
    outside = [c for c in results if not c["key"] and c["doi"]]
    unknown = [c for c in results if not c["key"] and not c["doi"]]
    no_pdf = [r for r in refs if r["key"] not in with_pdf]
    order = {"metadata": 0, "abstract": 1, "full text": 2}
    no_pdf.sort(key=lambda r: (r["status"] != "initial bibliography", order.get(r["reading_level"], 0), -r["year"]))

    zot_md = []
    fz = Path(a.zotero) if a.zotero else (ROOT / "data" / "zotero.bib")
    if fz.exists():
        zot = read_bib(fz)
        zd = {z["doi"] for z in zot if z["doi"]}
        zt = {norm_title(z["title"]) for z in zot}
        corpus_not_in_zotero = [r for r in refs if norm_doi(r.get("doi")) not in zd and norm_title(r["title"]) not in zt]
        zotero_not_in_corpus = [z for z in zot if z["doi"] not in by_doi and norm_title(z["title"]) not in by_title]
        zotero_no_file = [z for z in zot if not z["file"] and (z["doi"] in by_doi)]
        zot_md = [f"## Zotero ({fz.name}, {len(zot)} entries)", "",
                  f"- Corpus references missing from Zotero: **{len(corpus_not_in_zotero)}**",
                  f"- Zotero entries outside the corpus: **{len(zotero_not_in_corpus)}**",
                  f"- Zotero entries of the corpus without an attached file: **{len(zotero_no_file)}**", "",
                  "### Corpus references missing from Zotero", ""] + \
                 [f"- `{r['key']}` — {r['title']}" + (f" — https://doi.org/{r['doi']}" if r.get('doi') else "") for r in corpus_not_in_zotero] + \
                 ["", "### Zotero entries outside the corpus (add with integrate.py --doi?)", ""] + \
                 [f"- `{z['key']}` — {z['title']}" + (f" — `python scripts/integrate.py --doi {z['doi']}`" if z['doi'] else "") for z in zotero_not_in_corpus] + [""]

    today = dt.date.today().isoformat()
    md = [f"# Local PDFs vs corpus — {today}", "",
          f"Folder scanned: `{a.folder}` — {len(pdfs)} PDFs.", "",
          f"- Corpus references with a local PDF: **{len(with_pdf)} / {len(refs)}**",
          f"- PDFs identified but outside the corpus: **{len(outside)}**",
          f"- Unidentified PDFs: **{len(unknown)}**", "",
          "## To fetch first (corpus references without a local PDF)", "",
          "Order: initial bibliography first, then the least-read cards.", "",
          "| Key | Reading level | Status | Title | Open access |", "|---|---|---|---|---|"]
    md += [f"| `{r['key']}` | {r['reading_level']} | {r['status']} | {r['title'][:90].replace('|', '/')} | {r.get('oa_url') or ''} |" for r in no_pdf]
    md += ["", "## PDFs outside the corpus", ""] + [f"- {Path(c['file']).name} — DOI {c['doi']} — `python scripts/integrate.py --doi {c['doi']}`" for c in outside]
    md += ["", "## Unidentified PDFs", "", "Rename them with their DOI (e.g. `10.1016_j.xxx.pdf`) or install pdf2doi, then run again.", ""]
    md += [f"- {c['file']}" for c in unknown]
    md += ["", "## Corpus PDFs found", ""] + [f"- `{c['key']}` ← {Path(c['file']).name} ({c['method']})" for c in results if c["key"]]
    md += [""] + zot_md
    out = REPORTS / f"comparison_{today}.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(pdfs)} PDFs: {len(with_pdf)} in the corpus, {len(outside)} outside, {len(unknown)} unidentified. "
          f"{len(no_pdf)} corpus references without a local PDF. Report: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
