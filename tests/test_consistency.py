"""Checks run at every publication and on every pull request (python -m pytest -q tests)."""
import csv
import json
import re
from pathlib import Path

import openpyxl

R = Path(__file__).resolve().parents[1]
CORPUS = json.loads((R / "data" / "corpus.json").read_text(encoding="utf-8"))
REFS = CORPUS["refs"]
KEYS = {r["key"] for r in REFS}
DOIS = {r["doi"].lower() for r in REFS if r.get("doi")}
FIELDS = ["key", "doi", "year", "authors", "title", "status", "main_theme", "region", "origin",
          "reading_level", "cites"]


def test_required_fields():
    for r in REFS:
        missing = [c for c in FIELDS if c not in r]
        assert not missing, f"{r.get('key')}: missing fields {missing}"
        assert r["reading_level"] in {"metadata", "abstract", "full text"}, r["key"]
        assert r["status"] in {"initial bibliography", "new"}, r["key"]


def test_no_duplicates():
    assert len(KEYS) == len(REFS), "duplicate keys"
    dois = [r["doi"].lower() for r in REFS if r.get("doi")]
    assert len(dois) == len(set(dois)), "duplicate DOIs"


def test_internal_citations():
    for r in REFS:
        assert set(r["cites"]) <= KEYS, f"{r['key']} cites a key that is not in the corpus"


def test_three_deliverables_match():
    site = R / "site"
    xl = openpyxl.load_workbook(site / "ARD_reading_table.xlsx")["Reading table"]
    xk = {row[0] for row in xl.iter_rows(min_row=2, values_only=True)}
    with open(site / "ARD_reading_table.csv", encoding="utf-8-sig") as f:
        ck = {l["Key"] for l in csv.DictReader(f)}
    bib = (site / "ARD_corpus.bib").read_text(encoding="utf-8")
    bk = set(re.findall(r"^@\w+\{([^,]+),", bib, re.M))
    bd = {d.lower() for d in re.findall(r"^  doi = \{([^}]+)\}", bib, re.M)}
    page = (site / "index.html").read_text(encoding="utf-8")
    pk = {d["k"] for d in json.loads(re.search(r"const DATA = (\[.*?\]);\n", page, re.S).group(1))}
    assert xk == ck == bk == pk == KEYS
    assert bd == DOIS


def test_synthesis_cites_existing_keys():
    syn = (R / "data" / "synthesis.html").read_text(encoding="utf-8")
    unknown = set(re.findall(r"\[\[([A-Za-z0-9]+)\]\]", syn)) - KEYS
    assert not unknown, f"unknown keys in the synthesis: {unknown}"


def test_candidates_page_built():
    page = (R / "site" / "candidates.html").read_text(encoding="utf-8")
    cands = json.loads(re.search(r"const CANDS = (\[.*?\]);\n", page, re.S).group(1))
    for c in cands:
        assert set(c["cites"]) <= KEYS
