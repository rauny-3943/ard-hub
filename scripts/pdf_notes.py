#!/usr/bin/env python3
"""Write a reading note for a paper from its local PDF (question, site, methods, results, contribution).

Run it on your own machine: the PDFs never leave your computer, except towards the LLM service you choose
(see scripts/llm.py; Ollama keeps everything local).

    python scripts/pdf_notes.py --pdf pdfs/zarroca2021.pdf --key Zarroca2021
    python scripts/pdf_notes.py --all             # every PDF matched by compare_local.py
    python scripts/pdf_notes.py --all --dry-run   # show what would be processed, without calling the LLM

Each note goes to data/notes/<key>.json with "reviewed": false. Read it, correct it, set "reviewed" to true,
then run scripts/build.py: the map will show "full text".
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import llm
from common import NOTES, REPORTS, load_corpus

SYSTEM = """You write reading notes in English for a scientific bibliography on acid rock drainage (ARD).
Rules:
- Use only the text provided. Invent nothing; if a piece of information is missing, write "not specified in the text".
- Paraphrase: do not copy long passages from the paper. Keep key figures with their units.
- Plain style, short sentences, no superlatives. Each field: 120 words at most.
Answer only with a JSON object with the keys: question, site, methods, results, contribution."""


def text(pdf: Path, max_chars: int) -> str:
    from pypdf import PdfReader
    r = PdfReader(str(pdf))
    t = "\n".join((p.extract_text() or "") for p in r.pages)
    if len(t) > max_chars:  # keep the beginning (introduction, methods, results) and the end (conclusions)
        t = t[: int(max_chars * 0.75)] + "\n[…]\n" + t[-int(max_chars * 0.25):]
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="path of the PDF")
    ap.add_argument("--key", help="corpus key matching the PDF")
    ap.add_argument("--all", action="store_true", help="every PDF listed in reports/matches.json")
    ap.add_argument("--redo", action="store_true", help="overwrite existing notes")
    ap.add_argument("--max-chars", type=int, default=40000, help="maximum length of the text sent (characters)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    refs = {r["key"]: r for r in load_corpus()["refs"]}
    work: list[tuple[str, Path]] = []
    if a.pdf:
        if not a.key or a.key not in refs:
            raise SystemExit("Give --key with a corpus key (see the table or the map).")
        work.append((a.key, Path(a.pdf)))
    elif a.all:
        f = REPORTS / "matches.json"
        if not f.exists():
            raise SystemExit("Run first: python scripts/compare_local.py")
        seen = set()
        for c in json.loads(f.read_text()).values():
            k = c.get("key")
            if k and k in refs and k not in seen and Path(c["file"]).exists():
                seen.add(k)
                work.append((k, Path(c["file"])))
    else:
        ap.print_help()
        return 1

    NOTES.mkdir(parents=True, exist_ok=True)
    print(f"Model: {llm.describe()}")
    n = 0
    for k, pdf in work:
        out = NOTES / f"{k}.json"
        if out.exists() and not a.redo:
            print(f"= {k}: note already exists (use --redo to rewrite it)")
            continue
        r = refs[k]
        t = text(pdf, a.max_chars)
        if len(t) < 2000:
            print(f"! {k}: almost no text ({len(t)} chars) — scanned PDF? Run OCR on it first.")
            continue
        if a.dry_run:
            print(f"~ {k}: {pdf.name}, {len(t)} characters would be sent")
            continue
        u = (f"Reference: {r['title']} ({r['year']}), {r['venue']}.\n"
             f"Current card (level {r['reading_level']}): question = {r['question']!r}; site = {r['site']!r}.\n\n"
             f"TEXT OF THE PAPER:\n{t}")
        try:
            note = llm.extract_json(llm.call(SYSTEM, u, max_tokens=1500))
        except Exception as e:
            print(f"! {k}: failed ({e})")
            continue
        note.update({"key": k, "reading_level": "full text", "date": dt.date.today().isoformat(),
                     "generated_by": llm.describe(), "reviewed": False, "source": "local PDF (not published)"})
        out.write_text(json.dumps(note, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n += 1
        print(f"+ {k} → {out.relative_to(NOTES.parent.parent)}")
    print(f"{n} note(s) written. Review them, set \"reviewed\": true, then: python scripts/build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
