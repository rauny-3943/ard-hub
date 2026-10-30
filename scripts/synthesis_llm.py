#!/usr/bin/env python3
"""Draft an update of the synthesis (data/synthesis.html) with an LLM, for review before use.

Two modes:
  --new (default)   writes paragraphs for references that the synthesis does not cite yet
                    → data/synthesis_proposals.md
  --full            rewrites the whole synthesis through successive summaries (theme by theme, then regions)
                    → data/synthesis_draft.html  (compare it with data/synthesis.html)

The published synthesis is never replaced automatically: copy what you keep into data/synthesis.html
(references are written [[CorpusKey]] and become clickable links).
The LLM only receives corpus fields (not the PDFs) and must respect the reading level.
"""
from __future__ import annotations

import argparse
import re
import sys

import llm
from common import DATA, load_corpus

RULES = """You write, in English, a literature synthesis on natural acid rock drainage (ARD) in mountains,
for an ecology intern (Zotero library “Stage AMAP 2026”), with priority on the Pyrenees and the Cordillera Blanca.
Strict rules:
- Use only the cards provided; add no outside facts.
- A card at the "metadata" level only allows you to mention its topic, never its results.
- Cite each reference by its key in double brackets, e.g. [[Zarroca2021]], right after the idea it supports.
- Short sentences, active voice, neutral tone, no superlatives or filler phrases."""


def card(r: dict, size: int = 420) -> str:
    content = r.get("results") or r.get("contribution") or "(not read yet: mention the topic only)"
    return (f"[[{r['key']}]] {r['year']} · {r['region']} · {r['main_theme']} · reading level: {r['reading_level']}\n"
            f"Title: {r['title']}\nResults/contribution: {content[:size]}\n")


def batches(refs: list[dict], size: int):
    for i in range(0, len(refs), size):
        yield refs[i:i + size]


def clean(txt: str, keys: set[str]) -> tuple[str, list[str]]:
    unknown = sorted({k for k in re.findall(r"\[\[([^\]]+)\]\]", txt) if k not in keys})
    for k in unknown:  # an invented key is removed, not turned into a link
        txt = txt.replace(f"[[{k}]]", "")
    return txt, unknown


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--batch-size", type=int, default=20, help="cards per call (adapt to the model limits)")
    ap.add_argument("--dry-run", action="store_true", help="do not call the LLM, show the batching")
    a = ap.parse_args()

    refs = load_corpus()["refs"]
    keys = {r["key"] for r in refs}
    syn = (DATA / "synthesis.html").read_text(encoding="utf-8")
    cited = set(re.findall(r"\[\[([A-Za-z0-9]+)\]\]", syn))
    print(f"Model: {llm.describe()}")

    if not a.full:
        new = [r for r in refs if r["key"] not in cited and not r.get("context")]
        new.sort(key=lambda r: (r["main_theme"], r["year"]))
        print(f"{len(new)} reference(s) not cited in the synthesis.")
        if a.dry_run or not new:
            return 0
        outputs = []
        for b in batches(new, a.batch_size):
            u = ("Here are references that the current synthesis does not cite yet. For each one that adds something, "
                 "propose one or two sentences to insert, naming the target section "
                 "(Geomorphology, Hydrochemistry, Soil, Other, Cordillera Blanca, Pyrenees, Gaps). "
                 "Group by section, in Markdown.\n\n" + "\n".join(card(r) for r in b))
            outputs.append(llm.call(RULES, u, max_tokens=1800))
        txt, unknown = clean("\n\n".join(outputs), keys)
        out = DATA / "synthesis_proposals.md"
        out.write_text(f"# Proposals for the synthesis ({llm.describe()})\n\nTo be reviewed before copying into data/synthesis.html.\n\n{txt}\n",
                       encoding="utf-8")
        print(f"Written: {out.relative_to(DATA.parent)}" + (f"; invented keys removed: {unknown}" if unknown else ""))
        return 0

    # full mode: notes per theme (map), then writing (reduce)
    families = {"Geomorphology": [], "Hydrochemistry": [], "Soil": [], "Other": []}
    for r in sorted(refs, key=lambda r: r["year"]):
        f = next((k for k in families if r["main_theme"].startswith(k)), "Other")
        families[f].append(r)
    notes = {}
    for f, rs in families.items():
        bs = list(batches(rs, a.batch_size))
        print(f"{f}: {len(rs)} references, {len(bs)} call(s)")
        if a.dry_run:
            continue
        parts = [llm.call(RULES, "Summarise as chronological notes (foundational works, turning points, key results), "
                          "with the [[...]] keys:\n\n" + "\n".join(card(r, 300) for r in b), max_tokens=1200) for b in bs]
        notes[f] = "\n".join(parts)
    if a.dry_run:
        return 0
    sections = []
    for f, n in notes.items():
        sections.append(llm.call(RULES, f"From these notes, write the “{f}” subsection of the history of ideas in HTML "
                                 f"(<h4>…</h4> then <p>…</p>), 250 words at most, keeping the [[...]] keys:\n\n{n}", max_tokens=1500))
    regions = llm.call(RULES, "From these notes, write in HTML (<h4>, <p>) a comparison of the Cordillera Blanca, the Pyrenees and other regions, "
                       "then a <ul> list of gaps and directions for the internship:\n\n" + "\n".join(notes.values())[:20000], max_tokens=2000)
    page = ("<section class=\"syn\" id=\"syn-ideas\">\n<h3>1. History of ideas by theme</h3>\n" + "\n".join(sections) +
            "\n</section>\n<section class=\"syn\" id=\"syn-regions\">\n<h3>2. Comparison between regions, gaps and directions</h3>\n"
            "<!--TABLE_REGIONS-->\n" + regions + "\n</section>\n")
    page, unknown = clean(page, keys)
    out = DATA / "synthesis_draft.html"
    out.write_text(page, encoding="utf-8")
    print(f"Written: {out.relative_to(DATA.parent)}" + (f"; invented keys removed: {unknown}" if unknown else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
