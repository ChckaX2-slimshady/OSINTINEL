"""Model discovery — list the models actually installed at an OpenAI-compatible endpoint.

Lets a UI offer "pick from what you have" instead of making the operator type model names. Pure
parsing (``parse_model_ids``) plus a tiny, error-swallowing HTTP probe (``list_installed_models``)
so a stopped/missing server never breaks the caller — it just returns ``[]``.
"""

from __future__ import annotations

import json
import urllib.request


def parse_model_ids(text: str) -> list[str]:
    """Pull installed model names from an OpenAI ``/v1/models`` *or* Ollama ``/api/tags`` body."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    out: list[str] = []
    if isinstance(data, dict):
        for row in data.get("data") or []:                      # OpenAI /v1/models → data[].id
            if isinstance(row, dict) and row.get("id"):
                out.append(str(row["id"]))
        for row in data.get("models") or []:                    # Ollama /api/tags → models[].name
            name = (row or {}).get("name") or (row or {}).get("model") if isinstance(row, dict) \
                else None
            if name:
                out.append(str(name))
    return list(dict.fromkeys(out))                             # de-dupe, keep order


def _http_get(url: str, timeout: float = 1.5) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (localhost only)
        return resp.read().decode("utf-8")


def list_installed_models(base_url: str | None, *, fetch=None) -> list[str]:
    """Models installed at an OpenAI-compatible endpoint (e.g. local Ollama). ``[]`` on any error,
    so a missing/stopped server never breaks the UI — it just falls back to the typed default."""
    if not base_url:
        return []
    fetch = fetch or _http_get
    try:
        return parse_model_ids(fetch(base_url.rstrip("/") + "/models"))
    except Exception:                                           # unreachable/timeout/garbage → none
        return []
