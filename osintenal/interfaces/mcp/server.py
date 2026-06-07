"""MCP stdio server (zero dependencies).

Implements just enough of MCP — ``initialize``, ``tools/list``, ``tools/call`` over
newline-delimited JSON-RPC 2.0 on stdin/stdout — to expose OSINTENAL as conversational tools.
The dispatch is pure (``handle_request``); ``serve_stdio`` drives it. The model profile is read
from the environment, so a configured local Ollama (or free cloud tier) is used automatically.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from ...inference import build_gateway, gateway_status
from ...service import EvidenceInput, InvestigationSummary, run_investigation

PROTOCOL_VERSION = "2024-11-05"

TOOLS: list[dict] = [
    {
        "name": "investigate",
        "description": (
            "Run a multi-agent OSINTENAL investigation over a question, the competing answers to "
            "weigh, and any evidence you provide. Returns ranked hypotheses with confidence, "
            "preserved alternatives, known unknowns, and recommended next steps. Uses the "
            "configured local/free models to judge evidence relevance, propose additional "
            "explanations, and critique the leader."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The investigative question."},
                "candidates": {"type": "array", "items": {"type": "string"},
                               "description": "Competing answers to weigh (2+)."},
                "evidence": {
                    "type": "array",
                    "description": "Evidence items to weigh.",
                    "items": {"type": "object", "properties": {
                        "text": {"type": "string"},
                        "source": {"type": "string"},
                        "supports": {"type": "integer",
                                     "description": "1-based index of the answer it supports "
                                                    "(optional; omit to let a model judge)."}}}},
            },
            "required": ["question", "candidates"],
        },
    },
    {
        "name": "models_status",
        "description": "Show the active model profile and tier→model routing for OSINTENAL.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _result(rid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _text(rid: Any, text: str, is_error: bool = False) -> dict:
    return _result(rid, {"content": [{"type": "text", "text": text}], "isError": is_error})


def _format_summary(s: InvestigationSummary) -> str:
    lines = [f"Investigation: {s.question}", "",
             f"Leading answer: {s.leader}  ({s.leader_confidence:.0%}, {s.leader_class})", "",
             "Ranked hypotheses (competing alternatives preserved):"]
    for h in s.ranked:
        lines.append(f"  - {h['confidence']:.0%}  [{h['class']}]  {h['statement']}")
    if s.known_unknowns:
        lines += ["", "Known unknowns:"] + [f"  - {q}" for q in s.known_unknowns]
    if s.next_steps:
        lines += ["", "Recommended next steps:"] + [f"  - {x}" for x in s.next_steps]
    return "\n".join(lines)


def _investigate(args: dict) -> str:
    question = args["question"]
    candidates = list(args.get("candidates") or [])
    evidence = [EvidenceInput(text=e.get("text", ""), source=e.get("source", "user"),
                              supports=(e["supports"] - 1) if isinstance(e.get("supports"), int)
                              else None)
                for e in (args.get("evidence") or [])]
    result = run_investigation(question=question, candidates=candidates, evidence=evidence,
                               gateway=build_gateway())
    return _format_summary(InvestigationSummary.from_result(result))


def _models_status(_args: dict) -> str:
    st = gateway_status()
    lines = [f"profile: {st['profile']} ({'local' if st['local'] else 'cloud'}, "
             f"{'free' if st['free'] else 'paid'})"]
    for tier, model in st["tier_models"].items():
        lines.append(f"  {tier}: {model}")
    lines.append(f"  embed: {st['embed']['model']}")
    return "\n".join(lines)


_DISPATCH = {"investigate": _investigate, "models_status": _models_status}


def handle_request(req: dict) -> dict | None:
    """Pure JSON-RPC dispatch. Returns a response dict, or None for notifications."""
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return _result(rid, {"protocolVersion": PROTOCOL_VERSION,
                             "capabilities": {"tools": {}},
                             "serverInfo": {"name": "osintenal", "version": "0.1.0"}})
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _result(rid, {"tools": TOOLS})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        handler = _DISPATCH.get(name)
        if handler is None:
            return _text(rid, f"unknown tool: {name}", is_error=True)
        try:
            return _text(rid, handler(params.get("arguments") or {}))
        except Exception as exc:  # tool errors are returned as data, not crashes
            return _text(rid, f"tool error: {exc}", is_error=True)
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def serve_stdio() -> None:
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_request(req)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
