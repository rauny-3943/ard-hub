#!/usr/bin/env python3
"""Literature monitoring: find new publications (OpenAlex + Semantic Scholar) that are not in the corpus.

Queries are matched against titles and abstracts only (OpenAlex search.title_and_abstract);
put phrases in double quotes and combine terms with AND / OR / NOT.
Abstracts are not stored: the candidates page links to the publisher and OpenAlex records.

Outputs (in data/candidates/):
  YYYY-MM-DD.md     readable report, sorted by score
  YYYY-MM-DD.json   full data for the run
  to_screen.csv     cumulative screening list: fill in the "decision" column (keep / reject)
  state.json        date of the last successful run

Examples:
  python scripts/search.py                       # since the last run
  python scripts/search.py --since 2025-01-01    # chosen window
  python scripts/search.py --no-s2               # without Semantic Scholar
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

from common import (CANDIDATES, BudgetExhausted, get_json, last_first, load_config, load_corpus, new_key,
                    norm_doi, norm_title, openalex_params, post_json)

OA = "https://api.openalex.org/works"
SELECT = ("id,doi,display_name,publication_year,publication_date,type,authorships,primary_location,"
          "biblio,referenced_works,open_access,cited_by_count")
COLUMNS = ["decision", "score", "proposed_key", "year", "title", "authors", "venue", "doi", "openalex", "found_via",
           "cites_in_corpus", "open_access", "main_theme", "secondary_themes", "region", "country", "site",
           "origin", "trigger", "search_date"]


def short_id(oid: str) -> str:
    return (oid or "").rsplit("/", 1)[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="start date YYYY-MM-DD (default: last run)")
    ap.add_argument("--no-s2", action="store_true", help="skip Semantic Scholar")
    ap.add_argument("--max", type=int, help="overrides max_per_query")
    a = ap.parse_args()

    cfg = load_config()
    if os.environ.get("CONTACT_EMAIL"):
        cfg["contact_email"] = os.environ["CONTACT_EMAIL"]
    corpus = load_corpus()["refs"]
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    state_f = CANDIDATES / "state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {}
    since = a.since or state.get("last_run") or cfg.get("default_since", "2026-01-01")
    today = dt.date.today().isoformat()
    nmax = a.max or int(cfg.get("max_per_query", 40))
    types = "|".join(cfg.get("types", ["article"]))
    base = openalex_params(cfg)

    corpus_dois = {norm_doi(r["doi"]) for r in corpus if r.get("doi")}
    corpus_oa = {short_id(r["openalex"]): r["key"] for r in corpus if r.get("openalex")}
    corpus_titles = {norm_title(r["title"]) for r in corpus}
    rejected = set()
    f_rej = CANDIDATES / "rejected.txt"
    if f_rej.exists():
        rejected = {l.strip().lower() for l in f_rej.read_text().splitlines() if l.strip() and not l.startswith("#")}

    found: dict[str, dict] = {}
    errors: list[str] = []
    budget_out: list[bool] = []

    def add(w: dict, via: str):
        wid = short_id(w.get("id"))
        d = norm_doi(w.get("doi"))
        if not wid or wid in corpus_oa or (d and d in corpus_dois) or norm_title(w.get("display_name")) in corpus_titles:
            return
        if wid.lower() in rejected or (d and d in rejected):
            return
        c = found.setdefault(wid, {"w": w, "via": []})
        if via not in c["via"]:
            c["via"].append(via)

    def list_works(params: dict, via: str):
        if budget_out:
            return
        p = dict(base, select=SELECT, per_page=min(nmax, 100), **params)
        try:
            r = get_json(OA, p)
        except BudgetExhausted as e:
            budget_out.append(True)
            errors.append(f"OpenAlex queries stopped: {e}")
            return
        except Exception as e:  # keep going: one failed query does not stop the run
            errors.append(f"{via}: {e}")
            return
        for w in (r or {}).get("results", [])[:nmax]:
            add(w, via)

    date_filter = f"from_publication_date:{since},type:{types}"
    for q in cfg.get("queries", []):
        list_works({"search.title_and_abstract": q, "filter": date_filter}, f"query {q}")
    for k in cfg.get("follow_citations_of", []):
        ref = next((r for r in corpus if r["key"] == k), None)
        if not ref or not ref.get("openalex"):
            errors.append(f"followed paper unknown or without OpenAlex ID: {k}")
            continue
        list_works({"filter": f"cites:{short_id(ref['openalex'])},{date_filter}"}, f"cites {k}")

    if cfg.get("semantic_scholar_recommendations") and not a.no_s2:
        ids = [f"DOI:{r['doi']}" for r in corpus if r["key"] in cfg.get("follow_citations_of", []) and r.get("doi")]
        h = {"x-api-key": os.environ["S2_API_KEY"]} if os.environ.get("S2_API_KEY") else {}
        try:
            rec = post_json("https://api.semanticscholar.org/recommendations/v1/papers/?fields=externalIds,title,year,publicationDate&limit=100",
                            {"positivePaperIds": ids, "negativePaperIds": []}, h)
            for p in rec.get("recommendedPapers", []):
                doi = (p.get("externalIds") or {}).get("DOI")
                if not doi or (p.get("publicationDate") or f"{p.get('year', 0)}-01-01") < since:
                    continue
                w = get_json(f"{OA}/doi:{doi}", dict(base, select=SELECT))  # single-work lookup: free
                if w:
                    add(w, "Semantic Scholar recommendation")
        except Exception as e:
            errors.append(f"Semantic Scholar: {e}")

    # score = number of routes that found the work + 2 per corpus reference it cites
    rows = []
    keys = {r["key"] for r in corpus}
    for wid, c in found.items():
        w = c["w"]
        cites = sorted({corpus_oa[short_id(x)] for x in w.get("referenced_works") or [] if short_id(x) in corpus_oa})
        score = len(c["via"]) + 2 * len(cites)
        if score < int(cfg.get("min_score", 1)):
            continue
        authors = [last_first(au["author"]["display_name"]) for au in w.get("authorships") or [] if au.get("author")]
        key = new_key(authors, w.get("publication_year"), keys)
        keys.add(key)
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        rows.append({
            "decision": "", "score": score, "proposed_key": key, "year": w.get("publication_year"),
            "title": w.get("display_name") or "", "authors": "; ".join(authors[:6]) + (" …" if len(authors) > 6 else ""),
            "venue": src, "doi": norm_doi(w.get("doi")), "openalex": w.get("id"), "found_via": " ; ".join(c["via"]),
            "cites_in_corpus": "; ".join(cites), "open_access": (w.get("open_access") or {}).get("oa_url") or "",
            "main_theme": "", "secondary_themes": "", "region": "", "country": "", "site": "", "origin": "",
            "trigger": "", "search_date": today,
        })
    rows.sort(key=lambda l: (-l["score"], -(l["year"] or 0)))

    # output files
    (CANDIDATES / f"{today}.json").write_text(json.dumps(
        {"since": since, "date": today, "errors": errors, "candidates": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    f_csv = CANDIDATES / "to_screen.csv"
    seen, old = set(), []
    if f_csv.exists():
        with open(f_csv, encoding="utf-8-sig", newline="") as f:
            old = list(csv.DictReader(f))
        seen = {l["openalex"] for l in old}
    new = [l for l in rows if l["openalex"] not in seen]
    with open(f_csv, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, COLUMNS, extrasaction="ignore")
        wr.writeheader()
        for l in old + new:
            wr.writerow(l)

    md = [f"# Literature watch – {today}", "",
          f"Publications since {since}. {len(new)} new candidates (not in the corpus nor in the rejected list).", "",
          "To screen: open `data/candidates/to_screen.csv`, write `keep` or `reject` in the `decision` column "
          "(optionally fill in theme, region, country…) and commit: kept papers are added to the corpus automatically.", ""]
    if errors:
        md += ["## Problems", ""] + [f"- {e}" for e in errors] + [""]
    md += ["| Score | Year | Reference | Found via | Cites in corpus |", "|---:|---:|---|---|---|"]
    for l in new:
        link = f"[{l['title'].replace('|', '/')}](https://doi.org/{l['doi']})" if l["doi"] else l["title"].replace("|", "/")
        vias = l["found_via"].split(" ; ")
        via_short = " ; ".join(vias[:3]) + (f" (+{len(vias) - 3})" if len(vias) > 3 else "")
        md.append(f"| {l['score']} | {l['year']} | {l['authors'].split(';')[0]} — {link} — *{l['venue'].replace('|', '/')}* | {via_short} | {l['cites_in_corpus']} |")
    (CANDIDATES / f"{today}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if not budget_out:  # otherwise keep the previous date so the window is not lost
        state.update({"last_run": today, "last_count": len(new)})
        state_f.write_text(json.dumps(state, indent=1), encoding="utf-8")

    print(f"{len(new)} new candidates since {since}; {len(errors)} problem(s).")
    for e in errors:
        print("  -", e, file=sys.stderr)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new={len(new)}\nreport=data/candidates/{today}.md\ndate={today}\n")
    return 2 if budget_out else 0


if __name__ == "__main__":
    sys.exit(main())
