"""Minimal, dependency-free LLM client: GitHub Models (default), any OpenAI-compatible API, Ollama or Anthropic.

Environment variables:
  LLM_PROVIDER   github (default) | openai | ollama | anthropic
  LLM_MODEL      e.g. openai/gpt-4.1-mini (GitHub Models), gpt-4.1-mini (OpenAI), llama3.1 (Ollama),
                 or a Claude model ID for anthropic (see the model list on docs.claude.com)
  GITHUB_TOKEN   for github: provided automatically in GitHub Actions (permission models: read),
                 or a personal access token with the "Models" permission when run locally
  OPENAI_API_KEY / LLM_BASE_URL   for openai (LLM_BASE_URL allows any compatible service)
  ANTHROPIC_API_KEY               for anthropic
"""
from __future__ import annotations

import json
import os
import re

from common import post_json

DEFAULTS = {
    "github": ("https://models.github.ai/inference/chat/completions", "openai/gpt-4.1-mini"),
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4.1-mini"),
    "ollama": ("http://localhost:11434/v1/chat/completions", "llama3.1"),
    "anthropic": ("https://api.anthropic.com/v1/messages", ""),
}


def config() -> tuple[str, str, str]:
    p = os.environ.get("LLM_PROVIDER", "github").lower()
    if p not in DEFAULTS:
        raise SystemExit(f"Unknown LLM_PROVIDER: {p} (github, openai, ollama, anthropic)")
    url, model = DEFAULTS[p]
    url = os.environ.get("LLM_BASE_URL", url)
    model = os.environ.get("LLM_MODEL", model)
    if not model:
        raise SystemExit("Set the model with LLM_MODEL (e.g. a Claude model ID).")
    return p, url, model


def describe() -> str:
    try:
        p, _, m = config()
        return f"{p}:{m}"
    except SystemExit as e:
        return str(e)


def call(system: str, user: str, max_tokens: int = 2000, temperature: float = 0.2) -> str:
    p, url, model = config()
    if p == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY") or _missing("ANTHROPIC_API_KEY")
        r = post_json(url, {"model": model, "max_tokens": max_tokens, "temperature": temperature, "system": system,
                            "messages": [{"role": "user", "content": user}]},
                      {"x-api-key": key, "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in r.get("content", []))
    if p == "github":
        key = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_MODELS_TOKEN") or _missing("GITHUB_TOKEN")
    elif p == "openai":
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or _missing("OPENAI_API_KEY")
    else:
        key = "ollama"
    r = post_json(url, {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                  {"Authorization": f"Bearer {key}"})
    return r["choices"][0]["message"]["content"]


def _missing(v: str):
    raise SystemExit(f"Missing environment variable: {v}")


def extract_json(txt: str) -> dict:
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("Answer contains no JSON: " + txt[:300])
    return json.loads(m.group(0))
