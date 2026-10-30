"""Shared helpers for the repository scripts: paths, polite HTTP access, corpus I/O."""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CORPUS = DATA / "corpus.json"
NOTES = DATA / "notes"
CANDIDATES = DATA / "candidates"
CONFIG = ROOT / "config" / "search.yaml"
SITE = ROOT / "site"
BUILD = ROOT / "build"
REPORTS = ROOT / "reports"   # ignored by git: reports about your local PDFs
PDFS = ROOT / "pdfs"         # ignored by git: your PDFs are never published

USER_AGENT = "ard-hub/1.0 (literature monitoring)"


class BudgetExhausted(RuntimeError):
    """OpenAlex refused the request for lack of budget (no API key, or daily budget used up)."""


def load_corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def save_corpus(d: dict) -> None:
    CORPUS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_config() -> dict:
    import yaml  # PyYAML
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def get_json(url: str, params: dict | None = None, tries: int = 4, pause: float = 1.5, headers: dict | None = None):
    """GET JSON with retries (429/5xx). Returns None on 404."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    h.update(headers or {})
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                body = e.read().decode("utf-8", "replace")
                if "budget" in body.lower():
                    raise BudgetExhausted("OpenAlex budget exhausted: add a free key (secret OPENALEX_API_KEY)") from e
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(pause * (2 ** i))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if i < tries - 1:
                time.sleep(pause * (2 ** i))
                continue
            raise


def post_json(url: str, body: dict, headers: dict, tries: int = 3):
    data = json.dumps(body).encode("utf-8")
    h = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    h.update(headers)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method="POST"), timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and i < tries - 1:
                time.sleep(5 * (2 ** i))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e


def norm_doi(doi: str | None) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi)
    return doi.rstrip(".;,)")


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return re.sub(r"[^a-z0-9]", "", t)[:80]


def last_name(author: str) -> str:
    return author.split(",")[0].strip()


def plain_ascii(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^A-Za-z]", "", s.encode("ascii", "ignore").decode())


def new_key(authors: list[str], year: int, existing: set[str]) -> str:
    """“LastnameYear” key, with b, c… suffixes for homonyms (same convention as the corpus)."""
    base = plain_ascii(last_name(authors[0])) if authors else "Anonymous"
    base = (base or "Anonymous") + str(year or "")
    if base not in existing:
        return base
    for s in "bcdefghijklmnopqrstuvwxyz":
        if base + s not in existing:
            return base + s
    raise ValueError(base)


def last_first(display_name: str) -> str:
    """“Jane M. Doe” -> “Doe, Jane M.” (heuristic: last word = last name)."""
    p = display_name.split()
    if "," in display_name or len(p) < 2:
        return display_name
    return f"{p[-1]}, {' '.join(p[:-1])}"


def openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = sorted((i, w) for w, idx in inv.items() for i in idx)
    return " ".join(w for _, w in pos)


def openalex_params(cfg: dict) -> dict:
    p = {}
    if os.environ.get("OPENALEX_API_KEY"):
        p["api_key"] = os.environ["OPENALEX_API_KEY"]
    if cfg.get("contact_email"):
        p["mailto"] = cfg["contact_email"]
    return p
