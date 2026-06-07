"""Evidence→hypothesis relevance judgment (doc 11 §2, Phase M milestone 2 — the `task` tier).

Deciding whether a fetched piece of evidence *supports* or *contradicts* each competing
hypothesis is exactly the kind of bounded, structured judgment a small specialized model does
well — and it is what the deterministic ``_relevance_link`` stand-ins in the scenarios were
placeholders for. This module makes that a swappable port:

* ``HeuristicRelevanceJudge`` — reproducible keyword/tag rules; the default, the CI behavior,
  and the safety net.
* ``LLMRelevanceJudge`` — asks the gateway's ``task`` tier for a JSON map of hypothesis-id →
  signed weight; on any malformed/empty result it falls back to the heuristic, so a flaky or
  offline model never breaks a run.

Both return ``{hypothesis_id: weight in [-1, 1]}`` (positive = supports, negative = contradicts,
absent = irrelevant), which the caller writes onto the EvidenceObject.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..inference.providers.openai_compat import _maybe_json

# Signal keywords + per-kind weight magnitudes preserved from the scenario stand-ins, so the
# heuristic judge reproduces prior behavior exactly (byte-identical demo/slice runs).
_SIGNAL = ("mast", "tower", "telecom", "communications", "relay", "antenna")
_KIND_WEIGHTS = {"archive_snapshot": (0.8, -0.3), "osm_feature": (0.6, -0.2)}
_STOPWORDS = frozenset((
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "of", "to", "in", "on", "at",
    "and", "or", "for", "with", "by", "as", "it", "its", "this", "that", "from", "into", "near",
    "structure", "located", "site", "the"))


def _extract_json_object(text: str) -> dict | None:
    """Find the first balanced ``{...}`` object in free-form model text (models often add prose)."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


@dataclass(frozen=True)
class Candidate:
    hypothesis_id: str
    statement: str


@runtime_checkable
class RelevanceJudge(Protocol):
    def score(self, *, kind: str, summary: str, structured: dict,
              candidates: list[Candidate]) -> dict[str, float]: ...


def _overlap(statement: str, words: tuple[str, ...]) -> int:
    s = statement.lower()
    return sum(1 for w in words if w in s)


class HeuristicRelevanceJudge:
    """Keyword/tag rules + lexical overlap — deterministic, reproducible, no model."""

    def score(self, *, kind: str, summary: str, structured: dict,
              candidates: list[Candidate]) -> dict[str, float]:
        if not candidates:
            return {}
        if kind in _KIND_WEIGHTS:
            man_made = (structured.get("tags") or {}).get("man_made")
            title = (structured.get("title") or "").lower()
            signalled = ((kind == "archive_snapshot" and ("telecom" in title or "mast" in title))
                         or (kind == "osm_feature" and man_made in {"mast", "tower"}))
            if not signalled:
                return {}
            sup_w, con_w = _KIND_WEIGHTS[kind]
            target = max(candidates, key=lambda c: _overlap(c.statement, _SIGNAL))
            weights = {target.hypothesis_id: sup_w}
            for c in candidates:
                if c.hypothesis_id != target.hypothesis_id:
                    weights[c.hypothesis_id] = con_w
            return weights
        # generic lexical relevance for arbitrary text (web pages, notes): support the candidate
        # whose statement shares the most distinctive words with the evidence.
        return self._lexical(summary, structured, candidates)

    @staticmethod
    def _words(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in _STOPWORDS}

    def _lexical(self, summary: str, structured: dict,
                 candidates: list[Candidate]) -> dict[str, float]:
        ev_words = self._words(summary + " " + " ".join(str(v) for v in structured.values()))
        scored = [(c, len(self._words(c.statement) & ev_words)) for c in candidates]
        best, best_n = max(scored, key=lambda t: t[1])
        return {best.hypothesis_id: 0.5} if best_n else {}


class LLMRelevanceJudge:
    """Asks the gateway's ``task`` tier; falls back to the heuristic on any bad output."""

    def __init__(self, gateway, *, tier: str = "task",
                 fallback: RelevanceJudge | None = None) -> None:
        self.gateway = gateway
        self.tier = tier
        self.fallback = fallback or HeuristicRelevanceJudge()

    _SYSTEM = (
        "You are a precise relevance judge for an intelligence system. Given one piece of "
        "evidence and a list of competing hypotheses, decide for each whether the evidence "
        "supports or contradicts it. Respond with ONLY a JSON object mapping each relevant "
        "hypothesis id to a signed weight in [-1,1] (positive = supports, negative = "
        "contradicts). Omit hypotheses the evidence does not bear on. No prose.")

    def _prompt(self, kind: str, summary: str, structured: dict,
                candidates: list[Candidate]) -> str:
        cand = "\n".join(f"- {c.hypothesis_id}: {c.statement}" for c in candidates)
        return (f"Evidence (kind={kind}): {summary}\n"
                f"Structured: {json.dumps(structured, default=str)[:600]}\n\n"
                f"Hypotheses:\n{cand}\n\nJSON:")

    def score(self, *, kind: str, summary: str, structured: dict,
              candidates: list[Candidate]) -> dict[str, float]:
        try:
            resp = self.gateway.complete(
                tier=self.tier, role="relevance",
                payload={"system": self._SYSTEM,
                         "prompt": self._prompt(kind, summary, structured, candidates),
                         "max_tokens": 200, "temperature": 0.0,
                         "response_schema": {"type": "object"}})
        except Exception:
            resp = None
        weights = self._parse(resp, candidates) if resp else None
        if weights is None:
            return self.fallback.score(kind=kind, summary=summary, structured=structured,
                                       candidates=candidates)
        return weights

    @staticmethod
    def _parse(resp: dict, candidates: list[Candidate]) -> dict[str, float] | None:
        data = resp.get("structured")
        if not isinstance(data, dict):
            text = resp.get("text", "") or ""
            data = _maybe_json(text) or _extract_json_object(text)
        if not isinstance(data, dict):
            return None
        valid = {c.hypothesis_id for c in candidates}
        out: dict[str, float] = {}
        for key, val in data.items():
            if key in valid and isinstance(val, (int, float)) and not isinstance(val, bool):
                out[key] = max(-1.0, min(1.0, float(val)))
        return out or None


def apply_weights(evidence, weights: dict[str, float]) -> None:
    """Write a judged weight map onto an EvidenceObject's supports/contradicts/weights."""
    evidence.weights = dict(weights)
    evidence.supports = [h for h, w in weights.items() if w > 0]
    evidence.contradicts = [h for h, w in weights.items() if w < 0]
