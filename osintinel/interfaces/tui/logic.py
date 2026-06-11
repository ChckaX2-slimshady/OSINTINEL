"""TUI logic — pure helpers the Textual widgets call. No Textual import here, so it's unit-tested
directly: parsing the input fields, turning the model panel into a gateway (with full per-tier
control), running the investigation, and formatting the result as Rich markup.

The model panel exposes every knob the web picker can't: per-tier models (reason/small/task/embed),
the reasoning-tier and Skeptic decorrelation profiles, and a base-URL/key-env override for any
OpenAI-compatible endpoint. Because the TUI runs one investigation at a time, the overrides are
applied through a scoped ``os.environ`` patch (the same env the gateway already reads) — no global
mutation leaks past a run.
"""

from __future__ import annotations

import json
import os
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass

from ...inference import PROFILES, build_gateway, gateway_status
from ...service import (
    EvidenceInput,
    InvestigationSummary,
    RunStore,
    autoresearch_investigation,
    run_investigation,
)

_STORE = RunStore()

# model-panel attribute -> the env var the gateway already honors
_FORM_ENV = {
    "reason_model": "OSINTINEL_REASON_MODEL",
    "small_model": "OSINTINEL_SMALL_MODEL",
    "task_model": "OSINTINEL_TASK_MODEL",
    "embed_model": "OSINTINEL_EMBED_MODEL",
    "reason_profile": "OSINTINEL_REASON_PROFILE",
    "skeptic_profile": "OSINTINEL_SKEPTIC_PROFILE",
    "base_url": "OSINTINEL_OPENAI_BASE_URL",
    "key_env": "OSINTINEL_OPENAI_KEY_ENV",
}


@dataclass
class InferenceForm:
    """The model panel's state — one profile plus optional per-tier / endpoint overrides."""

    profile: str = "deterministic"
    reason_model: str = ""
    small_model: str = ""
    task_model: str = ""
    embed_model: str = ""
    reason_profile: str = ""
    skeptic_profile: str = ""
    base_url: str = ""
    key_env: str = ""


def profile_names() -> list[str]:
    return list(PROFILES)


def form_from_profile(name: str) -> InferenceForm:
    """Prefill the per-tier model fields from a profile's defaults (what the dropdown does)."""
    p = PROFILES.get(name) or PROFILES["deterministic"]
    return InferenceForm(profile=p.name, reason_model=p.reason_model, small_model=p.small_model,
                         task_model=p.task_model, embed_model=p.embed_model)


@contextmanager
def _applied(form: InferenceForm):
    """Scope the form's overrides into the environment, then restore exactly."""
    saved: dict[str, str | None] = {}
    try:
        for attr, env in _FORM_ENV.items():
            val = (getattr(form, attr) or "").strip()
            if val:
                saved[env] = os.environ.get(env)
                os.environ[env] = val
        yield
    finally:
        for env, prev in saved.items():
            if prev is None:
                os.environ.pop(env, None)
            else:
                os.environ[env] = prev


def build_gateway_from_form(form: InferenceForm):
    with _applied(form):
        return build_gateway(profile=form.profile or None)


def status_from_form(form: InferenceForm) -> dict:
    with _applied(form):
        return gateway_status(form.profile or None)


def status_lines(form: InferenceForm) -> str:
    """Rich-markup readout of what will actually run (for the live status pane)."""
    st = status_from_form(form)
    tier = st["tier_models"]
    key = "—" if not st["key_env"] else ("present" if st["key_present"] else "[red]missing[/red]")
    rows = [
        f"[b]profile[/b]  {st['profile']}  ([i]{'local' if st['local'] else 'cloud'},"
        f" {'free' if st['free'] else 'paid'}[/i])",
        f"[b]reason[/b]  {tier['reason']}" + (f"  →[i]{st['reason_override']}[/i]"
                                              if st["reason_override"] else ""),
        f"[b]small [/b]  {tier['small']}",
        f"[b]task  [/b]  {tier['task']}",
        f"[b]embed [/b]  {st['embed']['model']}",
        f"[b]base  [/b]  {st['base_url'] or '—'}",
        f"[b]key   [/b]  {st['key_env'] or '—'}  ({key})",
    ]
    if st["skeptic_override"]:
        rows.append(f"[b]skeptic[/b] →[i]{st['skeptic_override']}[/i]")
    return "\n".join(rows)


def is_openai_profile(name: str) -> bool:
    p = PROFILES.get(name)
    return bool(p and p.kind == "openai")


def effective_base_url(form: InferenceForm) -> str | None:
    """The chat endpoint that will actually be used (profile base-URL + any override)."""
    return status_from_form(form).get("base_url")


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
            name = (row or {}).get("name") or (row or {}).get("model") if isinstance(row, dict) else None
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
    except Exception:                                            # unreachable/timeout/garbage → none
        return []


def parse_candidates(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_evidence(text: str) -> list[EvidenceInput]:
    """One per line: ``source | text | supports#`` (trailing 1-based index optional)."""
    out: list[EvidenceInput] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        source = parts[0] if len(parts) > 1 else "user"
        body = parts[1] if len(parts) > 1 else parts[0]
        supports = None
        if len(parts) > 2 and parts[2].lstrip("-").isdigit():
            supports = int(parts[2]) - 1
        out.append(EvidenceInput(text=body, source=source, supports=supports))
    return out


def run_summary(question: str, candidates: list[str], evidence: list[EvidenceInput],
                form: InferenceForm) -> InvestigationSummary:
    gateway = build_gateway_from_form(form)
    result = run_investigation(question=question, candidates=candidates, evidence=evidence,
                               gateway=gateway)
    summary = InvestigationSummary.from_result(result)
    _STORE.save(summary, result.investigation.investigation_id, model=form.profile)
    return summary


def _live_web_adapter(backend: str):
    """A web-research adapter wired for live, SSRF-guarded, polite open-web fetches."""
    import tempfile
    from pathlib import Path

    from ...adapters import Cassette, ContentAddressedStore, HttpClient, WebSearchAdapter

    cas = ContentAddressedStore(tempfile.mkdtemp())
    http = HttpClient(Cassette(Path(tempfile.mkdtemp()) / "web.json"), mode="live",
                      block_private_net=True, min_interval=1.0)
    return WebSearchAdapter(http, cas, backend=backend)


def run_autoresearch(question: str, form: InferenceForm, *, candidates: list[str] | None = None,
                     rounds: int = 3, limit: int = 5, backend: str = "wikipedia",
                     web_adapter=None) -> InvestigationSummary:
    """Autonomous investigation: gather evidence from the open web, let the reason model frame
    competing answers, chase the known-unknowns for more (and contrary) evidence, run the Skeptic
    gauntlet, and return the insights that survived. ``web_adapter`` is injectable for tests."""
    from ...adapters.web.search import to_search_query

    gateway = build_gateway_from_form(form)
    adapter = web_adapter if web_adapter is not None else _live_web_adapter(backend)
    result = autoresearch_investigation(
        question=question, candidates=candidates or None, web_adapter=adapter,
        limit=limit, gateway=gateway, rounds=rounds,
        backends=["duckduckgo", "wikipedia"],  # diverse domains + reliable content
        query_transform=to_search_query)       # natural questions → keyword search
    summary = InvestigationSummary.from_result(result)
    _STORE.save(summary, result.investigation.investigation_id, model=form.profile)
    return summary


def _bar(fraction: float, width: int = 16) -> str:
    filled = max(0, min(width, round(fraction * width)))
    return "█" * filled + "░" * (width - filled)


def format_summary(s: InvestigationSummary) -> str:
    """Rich-markup report for the results pane."""
    lines = [
        f"[b]Question[/b]  {s.question}",
        "",
        f"[b green]▸ Leading answer[/b green]  {s.leader}",
        f"   confidence [b]{s.leader_confidence:.0%}[/b]   "
        f"[dim]{_bar(s.leader_confidence)}[/dim]   class [i]{s.leader_class}[/i]",
        "",
        "[b]Ranked hypotheses[/b]",
    ]
    for i, h in enumerate(s.ranked, 1):
        lines.append(f"  [cyan]{i}.[/cyan] {h['statement']}")
        lines.append(f"     [dim]{_bar(h['confidence'])}  {h['confidence']:.0%} · "
                     f"{h['class']}[/dim]")
    if s.known_unknowns:
        lines += ["", "[b yellow]Known unknowns[/b yellow]"]
        lines += [f"  • {k}" for k in s.known_unknowns]
    if s.sources:
        lines += ["", "[b]Tools / sources used[/b]"]
        for src in s.sources:
            times = f" ×{src['count']}" if src["count"] > 1 else ""
            lines.append(f"  [cyan]·[/cyan] {src['source']}  [dim]({src['tool']}{times})[/dim]")
    if s.next_steps:
        lines += ["", "[b]Recommended next steps[/b]"]
        lines += [f"  [green]→[/green] {n}" for n in s.next_steps]
    return "\n".join(lines)


def photo_report(path: str) -> str:
    """Read a JPEG's EXIF and, if it's geotagged + timestamped, compute the sun/shadow geometry —
    a real 'what does this photo reveal' read for the front door."""
    from pathlib import Path

    from ...service.photo import analyze_photo, osm_url

    try:
        data = Path(path).expanduser().read_bytes()
    except OSError as exc:
        return f"[red]Can't read {path}:[/red] {exc}"
    a = analyze_photo(data)
    if not a["ok"]:
        return ("[yellow]No EXIF metadata found.[/yellow] The reader handles JPEG with EXIF — "
                "iPhone HEIC won't parse, so export/convert to JPEG first.")

    lines = [f"[b]Photo analysis[/b]  [dim]{path}[/dim]", ""]
    if a["camera"]:
        lines.append(f"[b]Camera[/b]   {a['camera']}")
    if a["captured"]:
        lines.append(f"[b]Captured[/b] {a['captured']}")
    gps = a["gps"]
    if not gps:
        lines += ["", "[yellow]No GPS tag — this image isn't geotagged.[/yellow]"]
        return "\n".join(lines)

    lat, lon = gps["lat"], gps["lon"]
    alt = f"  ·  alt {gps['altitude_m']} m" if gps.get("altitude_m") is not None else ""
    lines += ["", f"[b green]▸ Geotag[/b green]  {lat}, {lon}{alt}",
              f"   [dim]{osm_url(lat, lon)}[/dim]"]
    sun = a["sun"]
    if sun:
        lines += ["", "[b]Sun at capture (UTC)[/b]",
                  f"   elevation [b]{sun['elevation']}°[/b], azimuth {sun['azimuth']}°  →  "
                  f"shadows point [b]{sun['shadow']}°[/b]",
                  "   [dim]cross-check: do the shadows in the photo match that bearing?[/dim]"]
    return "\n".join(lines)
