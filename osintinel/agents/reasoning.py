"""Reason-tier model reasoning (doc 11 §2, Phase M milestone 2 — the `reason` tier).

The open-ended judgment the deterministic spine can't do: proposing *new* competing explanations
beyond the ones handed in, and authoring genuine adversarial critique (hidden assumptions,
reasoning weaknesses). Both run on the flagship `reason` tier through the gateway and degrade
safely — no gateway, an unreachable model, or unparseable output yields an empty result, so the
deterministic behavior is always the floor (CI stays green; a flaky local model never breaks a
run).

Division of labour (doc 08 §2): the model supplies *judgment and prose*; it never sets the
numbers. Model-authored findings advise — the **structural gates** (source-dependency,
illusory-independence) remain the only things that can *block* a promotion, so a model can't
arbitrarily gate (or un-gate) a conclusion. Accordingly model critique severity is capped below
`blocking`.
"""

from __future__ import annotations

import json
from typing import Any

# Critique categories a model may raise (the judgment ones; the computed gates are off-limits).
_MODEL_CRITIQUE_CATEGORIES = {"contradiction", "hidden_assumption", "reasoning_weakness", "overfit"}
_SEVERITIES = ("low", "medium", "high")  # model advice never blocks; structure owns blocking


def _extract_json(text: str) -> Any:
    """Parse JSON from possibly-prose model output (whole string, or first [...]/{...})."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text[:4].lower() == "json" else text
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("[", "]"), ("{", "}")):
        start = text.find(open_c)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == open_c:
                depth += 1
            elif text[i] == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


class ReasoningModel:
    """Thin reason-tier wrapper over the gateway; every method has an empty-result fallback."""

    def __init__(self, gateway, *, tier: str = "reason") -> None:
        self.gateway = gateway
        self.tier = tier

    def _complete(self, role: str, system: str, prompt: str, max_tokens: int = 400) -> Any:
        try:
            resp = self.gateway.complete(tier=self.tier, role=role,
                                         payload={"system": system, "prompt": prompt,
                                                  "max_tokens": max_tokens, "temperature": 0.0})
        except Exception:
            return None
        if not isinstance(resp, dict):
            return None
        data = resp.get("structured")
        return data if data is not None else _extract_json(resp.get("text", ""))

    # -- competing-explanation generation (Connections) --------------------
    _PROPOSE_SYSTEM = (
        "You are a hypothesis-generation analyst. Given a question and the evidence so far, "
        "propose additional *competing* explanations that are distinct from the ones already "
        "listed and from each other. Respond with ONLY a JSON array of short explanation "
        "strings. No prose.")

    def propose_explanations(self, *, question: str, observations: list[str],
                             existing: list[str], limit: int = 3) -> list[str]:
        obs = "\n".join(f"- {o}" for o in observations[:8]) or "(none yet)"
        have = "\n".join(f"- {e}" for e in existing) or "(none)"
        prompt = (f"Question: {question}\n\nObservations:\n{obs}\n\n"
                  f"Already considered:\n{have}\n\nNew competing explanations (JSON array):")
        data = self._complete("connections", self._PROPOSE_SYSTEM, prompt)
        if not isinstance(data, list):
            return []
        seen = {e.strip().lower() for e in existing}
        out: list[str] = []
        for item in data:
            s = item.strip() if isinstance(item, str) else ""
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
            if len(out) >= limit:
                break
        return out

    # -- adversarial critique (Skeptic) ------------------------------------
    _CRITIQUE_SYSTEM = (
        "You are a rigorous skeptic. Given a leading hypothesis and its evidence, identify the "
        "strongest objections: hidden assumptions, reasoning weaknesses, contradictions, or "
        "overfitting. Respond with ONLY a JSON array of objects "
        '{"category","severity","description"} where category is one of '
        "[contradiction, hidden_assumption, reasoning_weakness, overfit] and severity is one of "
        "[low, medium, high]. No prose.")

    def critique(self, *, statement: str, evidence: list[str], limit: int = 4) -> list[dict]:
        ev = "\n".join(f"- {e}" for e in evidence[:10]) or "(no evidence yet)"
        prompt = (f"Leading hypothesis: {statement}\n\nEvidence:\n{ev}\n\nObjections (JSON array):")
        data = self._complete("skeptic", self._CRITIQUE_SYSTEM, prompt)
        if not isinstance(data, list):
            return []
        out: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "")).strip()
            description = str(item.get("description", "")).strip()
            severity = str(item.get("severity", "medium")).strip().lower()
            if category in _MODEL_CRITIQUE_CATEGORIES and description:
                out.append({"category": category,
                            "severity": severity if severity in _SEVERITIES else "medium",
                            "description": description})
            if len(out) >= limit:
                break
        return out
