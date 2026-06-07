"""Inference profiles (doc 11 §4) — tier→endpoint presets, all free or local.

A profile maps the three tiers to concrete models on a concrete endpoint. The default is
``deterministic`` (no network, CI). The operator selects a real profile with
``OSINTINEL_INFERENCE_PROFILE``; models are overridable per tier via env so you can match your
hardware without code changes. ``ollama`` (fully local, free, private) is the recommended base;
the cloud profiles are all **free tiers**. The hybrid sweet spot — local embeddings/tasks with a
free-cloud reasoning tier — is one extra knob, ``OSINTINEL_REASON_PROFILE``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace

OLLAMA_BASE = "http://localhost:11434/v1"


@dataclass(frozen=True)
class Profile:
    name: str
    kind: str                 # chat backend: "openai" | "anthropic" | "huggingface" | "deterministic"
    base_url: str | None
    key_env: str | None
    reason_model: str
    small_model: str
    task_model: str
    embed_kind: str           # "openai" | "huggingface" | "deterministic"
    embed_base_url: str | None
    embed_key_env: str | None
    embed_model: str
    local: bool = False
    free: bool = True
    note: str = ""


# Local embeddings via Ollama — the default embed backend for cloud chat profiles that don't
# serve embeddings (Groq, OpenRouter), keeping evidence vectors on the operator's machine.
_LOCAL_EMBED = dict(embed_kind="openai", embed_base_url=OLLAMA_BASE, embed_key_env=None,
                    embed_model="nomic-embed-text")

PROFILES: dict[str, Profile] = {
    "deterministic": Profile(
        name="deterministic", kind="deterministic", base_url=None, key_env=None,
        reason_model="deterministic-1", small_model="deterministic-1", task_model="deterministic-1",
        embed_kind="deterministic", embed_base_url=None, embed_key_env=None,
        embed_model="det-embed-64", local=True, free=True,
        note="no network; reproducible; CI / offline default"),

    "ollama": Profile(
        name="ollama", kind="openai", base_url=OLLAMA_BASE, key_env=None,
        reason_model="qwen2.5:14b-instruct", small_model="qwen2.5:7b-instruct",
        task_model="qwen2.5:3b-instruct",
        embed_kind="openai", embed_base_url=OLLAMA_BASE, embed_key_env=None,
        embed_model="nomic-embed-text", local=True, free=True,
        note="fully local & private via Ollama; pick reason model to fit your VRAM"),

    "gemini": Profile(
        name="gemini", kind="openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai", key_env="GEMINI_API_KEY",
        reason_model="gemini-2.0-flash", small_model="gemini-2.0-flash",
        task_model="gemini-2.0-flash-lite",
        embed_kind="openai", embed_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        embed_key_env="GEMINI_API_KEY", embed_model="text-embedding-004", free=True,
        note="Google AI Studio free tier (key, no card); good free reasoning"),

    "groq": Profile(
        name="groq", kind="openai", base_url="https://api.groq.com/openai/v1", key_env="GROQ_API_KEY",
        reason_model="llama-3.3-70b-versatile", small_model="llama-3.1-8b-instant",
        task_model="llama-3.1-8b-instant", **_LOCAL_EMBED, free=True,
        note="Groq free tier (fast 70B); embeddings fall back to local Ollama"),

    "openrouter": Profile(
        name="openrouter", kind="openai", base_url="https://openrouter.ai/api/v1",
        key_env="OPENROUTER_API_KEY",
        reason_model="deepseek/deepseek-r1:free", small_model="meta-llama/llama-3.3-70b-instruct:free",
        task_model="meta-llama/llama-3.2-3b-instruct:free", **_LOCAL_EMBED, free=True,
        note="OpenRouter ':free' models; embeddings fall back to local Ollama"),

    "anthropic": Profile(
        name="anthropic", kind="anthropic", base_url=None,
        key_env="ANTHROPIC_API_KEY", reason_model="claude-opus-4-8",
        small_model="claude-sonnet-4-6", task_model="claude-haiku-4-5-20251001",
        **_LOCAL_EMBED, free=False, note="paid; flagship quality"),

    "huggingface": Profile(
        name="huggingface", kind="huggingface", base_url=None, key_env="HF_TOKEN",
        reason_model="HuggingFaceH4/zephyr-7b-beta", small_model="HuggingFaceH4/zephyr-7b-beta",
        task_model="HuggingFaceH4/zephyr-7b-beta",
        embed_kind="huggingface", embed_base_url=None, embed_key_env="HF_TOKEN",
        embed_model="sentence-transformers/all-MiniLM-L6-v2", free=True,
        note="HF Inference API free tier (rate-limited)"),
}

DEFAULT_PROFILE = "deterministic"


def resolve_profile(name: str | None = None) -> Profile:
    """Return the named profile (default from ``OSINTINEL_INFERENCE_PROFILE``) with per-tier
    model overrides from ``OSINTINEL_{REASON,SMALL,TASK,EMBED}_MODEL`` applied."""
    name = name or os.environ.get("OSINTINEL_INFERENCE_PROFILE", DEFAULT_PROFILE)
    if name not in PROFILES:
        raise ValueError(f"unknown inference profile {name!r}; choose from {sorted(PROFILES)}")
    p = PROFILES[name]
    return replace(
        p,
        reason_model=os.environ.get("OSINTINEL_REASON_MODEL", p.reason_model),
        small_model=os.environ.get("OSINTINEL_SMALL_MODEL", p.small_model),
        task_model=os.environ.get("OSINTINEL_TASK_MODEL", p.task_model),
        embed_model=os.environ.get("OSINTINEL_EMBED_MODEL", p.embed_model),
    )
