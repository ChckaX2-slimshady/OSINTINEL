"""Model & inference gateway (doc 11): routing, cost, record/replay, embeddings, no leaks."""

from __future__ import annotations

import json

from osintenal.adapters.transport import Cassette, HttpClient, request_key
from osintenal.agents.llm import LLMClient
from osintenal.core.budget import BudgetGovernor
from osintenal.core.schemas import Budgets
from osintenal.inference import build_gateway, gateway_status
from osintenal.inference.providers.anthropic import API_URL, AnthropicProvider
from osintenal.inference.providers.huggingface import FEATURE_URL, HuggingFaceEmbedder
from osintenal.inference.types import ChatMessage, ChatRequest
from osintenal.ledger import Ledger


# -- deterministic default ---------------------------------------------------
def test_deterministic_gateway_is_reproducible_and_llmclient_compatible():
    gw = build_gateway()
    assert isinstance(gw, LLMClient)  # drops into AgentContext.llm unchanged
    a = gw.complete(tier="reason", role="connections", payload={"prompt": "x", "system": "s"})
    b = gw.complete(tier="reason", role="connections", payload={"prompt": "x", "system": "s"})
    assert a["text"] == b["text"] and a["model"] == "deterministic-1"


def test_no_keys_means_deterministic_mode():
    st = gateway_status()
    assert st["anthropic_key"] is False and st["huggingface_token"] is False
    assert build_gateway().providers["reason"].__class__.__name__ == "DeterministicProvider"


# -- routing -----------------------------------------------------------------
def test_tier_routing_and_fallback():
    gw = build_gateway()
    # every documented tier resolves to a provider (with ladder fallback)
    for tier in ("reason", "large", "small", "task", "nano"):
        assert gw.complete(tier=tier, role="r", payload={"prompt": "p"})["tier"] == tier


# -- cost + recording --------------------------------------------------------
def test_cost_is_charged_to_governor_and_recorded_leanly():
    gov = BudgetGovernor(Budgets())
    ledger = Ledger()
    gw = build_gateway(governor=gov, ledger=ledger, investigation_id="t")
    gw.complete(tier="reason", role="synthesis", payload={"prompt": "synthesize secret-prompt"})

    assert gov.snapshot().tokens_used > 0
    model_calls = [e for e in ledger.events() if e.type == "model_call"]
    assert len(model_calls) == 1
    payload = model_calls[0].payload
    # lean: hashes + counts only — never the prompt/response text
    assert set(payload) >= {"tier", "role", "model", "prompt_hash", "response_hash",
                            "input_tokens", "output_tokens"}
    assert "secret-prompt" not in json.dumps(payload)
    assert "text" not in payload


def test_cost_summary_aggregates():
    gw = build_gateway()
    for _ in range(3):
        gw.complete(tier="task", role="extract", payload={"prompt": "p"})
    summary = gw.cost_summary()
    assert summary["calls"] == 3 and summary["input_tokens"] > 0


# -- embeddings --------------------------------------------------------------
def test_embeddings_are_deterministic_and_similarity_meaningful():
    gw = build_gateway()
    v = gw.embed(["a telecom mast", "a telecom mast", "a wind turbine"])
    assert v == gw.embed(["a telecom mast", "a telecom mast", "a wind turbine"])  # reproducible

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))
    assert cos(v[0], v[1]) > cos(v[0], v[2])  # duplicates more similar than different content


# -- live provider parsing via cassette replay (offline) ---------------------
def test_anthropic_provider_replays_recorded_response(tmp_path):
    cass = Cassette(tmp_path / "anthropic.json")
    req = ChatRequest(tier="reason", role="synthesis", model="claude-opus-4-8",
                      system="You are precise.",
                      messages=[ChatMessage(role="user", content="Synthesize.")])
    body = json.dumps({"model": "claude-opus-4-8", "max_tokens": 1024, "temperature": 0.0,
                       "messages": [{"role": "user", "content": "Synthesize."}],
                       "system": "You are precise."}, sort_keys=True)
    api = {"model": "claude-opus-4-8", "stop_reason": "end_turn",
           "content": [{"type": "text", "text": "Most likely a mast."}],
           "usage": {"input_tokens": 42, "output_tokens": 5}}
    cass.put(request_key("POST", API_URL, None, body), {"url": API_URL, "text": json.dumps(api)})

    prov = AnthropicProvider(HttpClient(cass, record=False), "claude-opus-4-8")
    resp = prov.chat(req)
    assert resp.text == "Most likely a mast."
    assert resp.usage.input_tokens == 42 and resp.usage.output_tokens == 5


def test_huggingface_embedder_replays_recorded_vectors(tmp_path):
    cass = Cassette(tmp_path / "hf.json")
    url = FEATURE_URL.format(model="sentence-transformers/all-MiniLM-L6-v2")
    body = json.dumps({"inputs": ["hello"]})
    cass.put(request_key("POST", url, None, body), {"url": url, "text": json.dumps([[0.1, 0.2, 0.3]])})

    emb = HuggingFaceEmbedder(HttpClient(cass, record=False))
    result = emb.embed(["hello"])
    assert result.vectors == [[0.1, 0.2, 0.3]] and result.dims == 3


def test_credentials_never_enter_the_cassette(tmp_path, monkeypatch):
    # request keys hash method+url+body only; the auth header is not part of the recording
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-key")
    cass_path = tmp_path / "anthropic.json"
    cass = Cassette(cass_path)
    req = ChatRequest(tier="reason", role="r", model="claude-opus-4-8",
                      messages=[ChatMessage(role="user", content="hi")])
    body = json.dumps({"model": "claude-opus-4-8", "max_tokens": 1024, "temperature": 0.0,
                       "messages": [{"role": "user", "content": "hi"}]}, sort_keys=True)
    cass.put(request_key("POST", API_URL, None, body),
             {"url": API_URL, "text": json.dumps(
                 {"model": "claude-opus-4-8", "content": [{"type": "text", "text": "ok"}],
                  "usage": {"input_tokens": 1, "output_tokens": 1}})})
    AnthropicProvider(HttpClient(cass, record=False), "claude-opus-4-8").chat(req)
    assert "sk-secret-key" not in cass_path.read_text()
