#!/usr/bin/env python3
"""Copy screening decisions sent from the "New candidates" page into data/candidates/to_screen.csv.

The page opens a GitHub issue titled "Screening decisions …" whose body has one line per paper:
    keep W4391234567 | theme=Soil & ARD | region=Pyrenees  # title (ignored)
    reject W4398765432  # title (ignored)
The "Apply screening decisions" workflow passes the issue body in the ISSUE_BODY environment variable,
runs this script, then scripts/integrate.py.

Local use: python scripts/apply_screening.py --file decisions.txt
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

from common import CANDIDATES

MAIN_THEMES = ["Geomorphology & ARD", "Hydrochemistry & ARD", "Soil & ARD"]
REGIONS = ["Cordillera Blanca", "Pyrenees", "Alps", "Rocky Mountains", "Arctic & subarctic", "Other Andes",
           "Antarctica", "Himalaya & Tibet", "Other", "Global / no location", "To be specified"]
LINE = re.compile(r"^\s*(keep|reject)\s+(W[A-Za-z0-9]+)\s*(.*)$", re.I)


def parse(body: str) -> list[dict]:
    out = []
    for raw in body.splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        extra = m.group(3).split("#", 1)[0]
        d = {"decision": m.group(1).lower(), "id": m.group(2), "main_theme": "", "region": ""}
        for part in extra.split("|"):
            if "=" in part:
                k, v = (s.strip() for s in part.split("=", 1))
                if k == "theme" and (v in MAIN_THEMES or v.startswith("Other – ")):
                    d["main_theme"] = v
                elif k == "region" and v in REGIONS:
                    d["region"] = v
        out.append(d)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="text file with decision lines (default: ISSUE_BODY environment variable)")
    ap.add_argument("--summary", default="screening_summary.md", help="where to write a short summary")
    a = ap.parse_args()
    body = Path(a.file).read_text(encoding="utf-8") if a.file else os.environ.get("ISSUE_BODY", "")
    decisions = parse(body)
    f_csv = CANDIDATES / "to_screen.csv"
    if not decisions:
        msg = "No decision line found (expected lines such as `keep W123…` or `reject W123…`)."
        Path(a.summary).write_text(msg + "\n", encoding="utf-8"); print(msg)
        return 1
    if not f_csv.exists():
        msg = "data/candidates/to_screen.csv does not exist: run the literature watch first."
        Path(a.summary).write_text(msg + "\n", encoding="utf-8"); print(msg)
        return 1
    with open(f_csv, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols, rows = list(rd.fieldnames or []), list(rd)
    for c in ("decision", "main_theme", "region"):
        if c not in cols:
            cols.append(c)
    by_id = {r["openalex"].rsplit("/", 1)[-1]: r for r in rows}
    applied, missing = 0, []
    for d in decisions:
        r = by_id.get(d["id"])
        if r is None:
            missing.append(d["id"]); continue
        r["decision"] = d["decision"]
        if d["main_theme"]: r["main_theme"] = d["main_theme"]
        if d["region"]: r["region"] = d["region"]
        applied += 1
    tmp = f_csv.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, cols)
        wr.writeheader(); wr.writerows(rows)
    tmp.replace(f_csv)  # write the whole file first, then swap: never leaves a half-written sheet
    keep = sum(d["decision"] == "keep" for d in decisions if d["id"] in by_id)
    msg = (f"Applied {applied} decision(s): {keep} keep, {applied - keep} reject."
           + (f" Not found in the screening sheet (already handled?): {', '.join(missing)}." if missing else ""))
    Path(a.summary).write_text(msg + "\n", encoding="utf-8")
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
