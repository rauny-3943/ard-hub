#!/usr/bin/env python3
"""Add screened candidates, or DOIs entered by hand, to the corpus.

1) After a literature watch: in data/candidates/to_screen.csv, write "keep" or "reject" in the decision
   column (you can also fill in main_theme, region, country, site, origin, trigger), then:
       python scripts/integrate.py
   Rejected rows go to data/candidates/rejected.txt (they will not come back).

2) Add one or more DOIs directly:
       python scripts/integrate.py --doi 10.1016/j.scitotenv.2021.146070 --theme "Hydrochemistry & ARD" --region Pyrenees

New references enter with reading_level = "metadata": complete them with scripts/pdf_notes.py (if you have
the PDF) or by hand, then run scripts/build.py again.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
import urllib.parse

from common import (CANDIDATES, get_json, last_first, load_config, load_corpus, new_key, norm_doi,
                    openalex_abstract, openalex_params, save_corpus)

OA = "https://api.openalex.org/works"
TYPES = {"article": "article", "review": "article", "book-chapter": "chapter", "book": "book",
         "dissertation": "thesis", "report": "report", "preprint": "preprint"}
KEEP = {"keep", "k", "yes", "y", "x", "1"}
REJECT = {"reject", "r", "no", "n", "0"}
MAIN_THEMES = ["Geomorphology & ARD", "Hydrochemistry & ARD", "Soil & ARD"]


def doi_resolves(doi: str) -> bool:
    try:
        r = get_json("https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/"))
        return bool(r and r.get("responseCode") == 1)
    except Exception:
        return False


def entry(w: dict, keys: set[str], corpus_oa: dict, extra: dict, via: str) -> dict:
    authors = [last_first(a["author"]["display_name"]) for a in w.get("authorships") or [] if a.get("author")]
    src = (w.get("primary_location") or {}).get("source") or {}
    b = w.get("biblio") or {}
    pages = "-".join(p for p in [b.get("first_page"), b.get("last_page")] if p)
    doi = norm_doi(w.get("doi"))
    t = w.get("type") or "article"
    theme = extra.get("main_theme") or "Other – to be classified"
    return {
        "key": new_key(authors, w.get("publication_year"), keys),
        "doi": doi, "openalex": w.get("id"), "url": f"https://doi.org/{doi}" if doi else (w.get("id") or ""),
        "oa_url": (w.get("open_access") or {}).get("oa_url") or "", "year": w.get("publication_year"),
        "authors": authors, "title": w.get("display_name") or "", "venue": src.get("display_name") or "",
        "volume": b.get("volume") or "", "issue": b.get("issue") or "", "pages": pages,
        "publisher": src.get("host_organization_name") or "", "doc_type": TYPES.get(t, "article"),
        "peer_reviewed": t in ("article", "review"), "status": "new", "context": False,
        "main_theme": theme,
        "secondary_themes": [s.strip() for s in (extra.get("secondary_themes") or "").split(";") if s.strip()],
        "region": extra.get("region") or "To be specified", "country": extra.get("country") or "", "site": extra.get("site") or "",
        "origin": extra.get("origin") or "to be specified", "trigger": extra.get("trigger") or "to be specified",
        "question": "", "methods": "", "results": "", "contribution": "",
        "reading_level": "metadata",
        "cites": sorted({corpus_oa[x.rsplit('/', 1)[-1]] for x in w.get("referenced_works") or [] if x.rsplit('/', 1)[-1] in corpus_oa}),
        "found_via": via, "doi_verified": bool(doi) and doi_resolves(doi),
        "note": "Added by integrate.py: card to be completed (question, methods, results, contribution)."
                + ("" if theme in MAIN_THEMES or theme.startswith("Other – ") else " Theme not in the list, to be checked."),
        "openalex_abstract": openalex_abstract(w.get("abstract_inverted_index")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doi", nargs="*", help="DOIs to add directly")
    for c in ["theme", "region", "country", "site", "origin", "trigger"]:
        ap.add_argument(f"--{c}", default="")
    ap.add_argument("--dry-run", action="store_true", help="show what would be done without writing anything")
    a = ap.parse_args()

    cfg = load_config()
    D = load_corpus()
    refs = D["refs"]
    keys = {r["key"] for r in refs}
    dois = {norm_doi(r["doi"]) for r in refs if r.get("doi")}
    corpus_oa = {r["openalex"].rsplit("/", 1)[-1]: r["key"] for r in refs if r.get("openalex")}
    base = openalex_params(cfg)
    added, rejected = [], []
    today = dt.date.today().isoformat()

    def add(w, extra, via):
        if not w:
            return
        d = norm_doi(w.get("doi"))
        if d and d in dois:
            print(f"Already in the corpus: {d}")
            return
        e = entry(w, keys, corpus_oa, extra, via)
        keys.add(e["key"]); dois.add(d); corpus_oa[e["openalex"].rsplit('/', 1)[-1]] = e["key"]
        added.append(e)

    if a.doi:
        extra = {"main_theme": a.theme, "region": a.region, "country": a.country, "site": a.site,
                 "origin": a.origin, "trigger": a.trigger}
        for doi in a.doi:
            w = get_json(f"{OA}/doi:{norm_doi(doi)}", base)
            if not w:
                print(f"DOI not found in OpenAlex: {doi}", file=sys.stderr)
                continue
            add(w, extra, f"added by hand ({today})")
    else:
        f_csv = CANDIDATES / "to_screen.csv"
        if not f_csv.exists():
            print("Nothing to integrate: data/candidates/to_screen.csv does not exist (run search.py first).")
            return 0
        with open(f_csv, encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            columns, rows = rd.fieldnames, list(rd)
        remaining = []
        for l in rows:
            dec = (l.get("decision") or "").strip().lower()
            if dec in KEEP:
                w = get_json(f"{OA}/{l['openalex'].rsplit('/', 1)[-1]}", base)
                add(w, l, f"literature watch of {l.get('search_date')}: {l.get('found_via')}")
            elif dec in REJECT:
                rejected.append(l.get("doi") or l["openalex"].rsplit("/", 1)[-1])
            else:
                remaining.append(l)
        if not a.dry_run:
            with open(f_csv, "w", encoding="utf-8-sig", newline="") as f:
                wr = csv.DictWriter(f, columns)
                wr.writeheader(); wr.writerows(remaining)
            if rejected:
                with open(CANDIDATES / "rejected.txt", "a", encoding="utf-8") as f:
                    f.write("\n".join(x.lower() for x in rejected) + "\n")

    for e in added:
        print(f"+ {e['key']} — {e['title'][:90]} (cites {len(e['cites'])} corpus refs; DOI verified: {e['doi_verified']})")
    print(f"{len(added)} added, {len(rejected)} rejected.")
    if added and not a.dry_run:
        refs.extend(added)
        D["meta"].setdefault("history", []).append(
            {"date": today, "step": "integrate.py", "note": f"{len(added)} reference(s) added: " + ", ".join(e["key"] for e in added)})
        save_corpus(D)
        print("Corpus updated. Now run: python scripts/build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
