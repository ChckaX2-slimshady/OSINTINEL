"""Model & inference gateway (doc 11): routing, cost, record/replay, embeddings, no leaks."""

from __future__ import annotations

import json

from osintinel.adapters.transport import Cassette, HttpClient, request_key
from osintinel.agents.llm import LLMClient
from osintinel.core.budget import BudgetGovernor
from osintinel.core.schemas import Budgets
from osintinel.inference import build_gateway, gateway_status
from osintinel.inference.providers.anthropic import API_URL, AnthropicProvider
from osintinel.inference.providers.huggingface import FEATURE_URL, HuggingFaceEmbedder
from osintinel.inference.types import ChatMessage, ChatRequest
from osintinel.ledger import Ledger


# -- deterministic default ---------------------------------------------------
def test_deterministic_gateway_is_reproducible_and_llmclient_compatible():
    gw = build_gateway()
    assert isinstance(gw, LLMClient)  # drops into AgentContext.llm unchanged
    a = gw.complete(tier="reason", role="connections", payload={"prompt": "x", "system": "s"})
    b = gw.complete(tier="reason", role="connections", payload={"prompt": "x", "system": "s"})
    assert a["text"] == b["text"] and a["model"] == "deterministic-1"


def test_default_profile_is_deterministic():
    st = gateway_status()
    assert st["profile"] == "deterministic" and st["local"] is True
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


def test_ollama_profile_builds_local_openai_provider_without_a_key(tmp_path):
    # the recommended free path: local Ollama, no API key, OpenAI-compatible
    gw = build_gateway(profile="ollama", cassette_dir=tmp_path, record=False)
    reason = gw.providers["reason"]
    assert reason.__class__.__name__ == "OpenAICompatibleProvider"
    assert reason.base_url == "http://localhost:11434/v1" and reason.key_env is None
    assert gw.models["reason"] == "qwen2.5:14b-instruct"


def test_per_tier_model_override_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINTINEL_REASON_MODEL", "llama3.1:70b")
    gw = build_gateway(profile="ollama", cassette_dir=tmp_path, record=False)
    assert gw.models["reason"] == "llama3.1:70b"


def test_base_url_override_retargets_openai_endpoint(tmp_path, monkeypatch):
    # point the OpenAI-compatible tiers at a custom endpoint (e.g. a Hermes harness) via env
    monkeypatch.setenv("OSINTINEL_OPENAI_BASE_URL", "http://localhost:8080/v1")
    monkeypatch.setenv("OSINTINEL_OPENAI_KEY_ENV", "HERMES_TOKEN")
    gw = build_gateway(profile="ollama", cassette_dir=tmp_path, record=False)
    reason = gw.providers["reason"]
    assert reason.base_url == "http://localhost:8080/v1"
    assert reason.key_env == "HERMES_TOKEN"
    assert gateway_status("ollama")["base_url"] == "http://localhost:8080/v1"


def test_base_url_override_ignored_for_non_openai_backend(monkeypatch):
    # deterministic/anthropic/huggingface ignore base_url; the override must not switch backends
    monkeypatch.setenv("OSINTINEL_OPENAI_BASE_URL", "http://localhost:8080/v1")
    assert gateway_status("deterministic")["base_url"] is None


def test_hybrid_reason_override_routes_only_reasoning_tier(tmp_path, monkeypatch):
    # local stack for embed/task, free-cloud profile for the reasoning tier (doc 11 §2)
    monkeypatch.setenv("OSINTINEL_REASON_PROFILE", "groq")
    gw = build_gateway(profile="ollama", cassette_dir=tmp_path, record=False)
    assert gw.models["reason"] == "llama-3.3-70b-versatile"   # from groq
    assert gw.models["task"] == "qwen2.5:3b-instruct"          # still local ollama


def test_openai_compatible_provider_replays_recorded_response(tmp_path):
    from osintinel.inference.providers.openai_compat import OpenAICompatibleProvider

    base = "http://localhost:11434/v1"
    cass = Cassette(tmp_path / "ollama.json")
    req = ChatRequest(tier="reason", role="synthesis", model="qwen2.5:14b-instruct",
                      system="Be precise.", messages=[ChatMessage(role="user", content="Go.")])
    body = json.dumps({"model": "qwen2.5:14b-instruct",
                       "messages": [{"role": "system", "content": "Be precise."},
                                    {"role": "user", "content": "Go."}],
                       "max_tokens": 1024, "temperature": 0.0, "stream": False}, sort_keys=True)
    api = {"model": "qwen2.5:14b-instruct",
           "choices": [{"message": {"role": "assistant", "content": "A mast."},
                        "finish_reason": "stop"}],
           "usage": {"prompt_tokens": 12, "completion_tokens": 3}}
    cass.put(request_key("POST", f"{base}/chat/completions", None, body),
             {"url": base, "text": json.dumps(api)})

    prov = OpenAICompatibleProvider(HttpClient(cass, record=False), "qwen2.5:14b-instruct", base)
    resp = prov.chat(req)
    assert resp.text == "A mast." and resp.usage.input_tokens == 12


def test_openai_compatible_embedder_replays_recorded_vectors(tmp_path):
    from osintinel.inference.providers.openai_compat import OpenAICompatibleEmbedder

    base = "http://localhost:11434/v1"
    cass = Cassette(tmp_path / "emb.json")
    body = json.dumps({"model": "nomic-embed-text", "input": ["hi"]})
    cass.put(request_key("POST", f"{base}/embeddings", None, body),
             {"url": base, "text": json.dumps({"data": [{"embedding": [0.1, 0.2]}]})})
    emb = OpenAICompatibleEmbedder(HttpClient(cass, record=False), "nomic-embed-text", base)
    result = emb.embed(["hi"])
    assert result.vectors == [[0.1, 0.2]] and result.dims == 2


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
