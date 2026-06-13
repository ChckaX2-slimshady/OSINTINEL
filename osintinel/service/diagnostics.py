"""First-run diagnostics — ``osintinel doctor``.

A fast, dependency-free preflight that answers "is my machine set up to run OSINTINEL, and which
model (if any) will it use?" Pure: ``run_diagnostics`` returns a list of ``Check`` records so it's
unit-testable without a terminal, and the CLI just renders them. Every check degrades gracefully —
a stopped Ollama or a missing key is reported as a clear ``warn``, never an exception. The
deterministic floor always passes, so ``doctor`` is green out of the box with no model and no key.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass(frozen=True)
class Check:
    name: str
    status: str           # "ok" | "warn" | "fail"
    detail: str


def run_diagnostics(*, profile: str | None = None, model_lister=None) -> list[Check]:
    """Probe the environment and return one ``Check`` per concern. ``model_lister`` is injectable
    (defaults to the real endpoint probe) so tests stay offline."""
    from ..inference import gateway_status, list_installed_models, resolve_profile
    from .runstore import default_home, persistence_enabled

    lister = model_lister or list_installed_models
    checks: list[Check] = []

    # 1) Python — the engine targets 3.11+. Reaching here means imports already worked.
    v = sys.version_info
    py = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 11):
        checks.append(Check("Python", FAIL, f"{py} — OSINTINEL needs 3.11 or newer"))
    else:
        checks.append(Check("Python", OK, f"{py}"))

    # 2) Core dependency — pydantic v2.
    try:
        import pydantic
        major = int(pydantic.VERSION.split(".")[0])
        checks.append(Check("pydantic", OK if major >= 2 else FAIL,
                            f"{pydantic.VERSION}" + ("" if major >= 2 else " — v2 required")))
    except Exception as exc:  # pragma: no cover - import guard
        checks.append(Check("pydantic", FAIL, f"not importable ({exc}); run: pip install -e ."))

    # 3) Inference profile + tier routing.
    st = gateway_status(profile)
    where = "local" if st["local"] else "cloud"
    money = "free" if st["free"] else "paid"
    checks.append(Check("Inference profile", OK,
                        f"{st['profile']} ({where}, {money}) — reason→{st['tier_models']['reason']}"))

    # 4) Credentials — only profiles that need a key.
    if st.get("key_env"):
        if st.get("key_present"):
            checks.append(Check("API key", OK, f"{st['key_env']} is set"))
        else:
            checks.append(Check("API key", WARN,
                                f"{st['key_env']} not set — this profile needs it, or it will "
                                f"degrade to deterministic"))

    # 5) Model endpoint reachability (local Ollama / any OpenAI-compatible base).
    try:
        base = resolve_profile(profile).base_url
    except ValueError:
        base = None
    if st["kind"] == "deterministic":
        checks.append(Check("Models", OK, "deterministic floor — no model needed (free, offline)"))
    elif base:
        models = lister(base)
        if models:
            checks.append(Check("Model endpoint", OK,
                                f"{len(models)} model(s) installed at {base}"))
        else:
            checks.append(Check("Model endpoint", WARN,
                                f"no models reachable at {base} — is the server running? "
                                f"(e.g. `ollama serve`)"))
    else:
        checks.append(Check("Model endpoint", OK, f"{st['profile']} (no local endpoint to probe)"))

    # 6) Network mode (cassette transport).
    checks.append(Check("Network mode", OK,
                        f"{st['net_mode']}  (replay=offline · record=build corpus · live=online)"))

    # 7) Persistence / run history.
    if not persistence_enabled():
        checks.append(Check("Run history", OK, "OSINTINEL_NO_PERSIST=1 — fully ephemeral session"))
    else:
        home = default_home()
        try:
            home.mkdir(parents=True, exist_ok=True)
            probe = home / ".doctor_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            checks.append(Check("Run history", OK, f"writable at {home}"))
        except OSError as exc:
            checks.append(Check("Run history", WARN,
                                f"{home} not writable ({exc}) — set OSINTINEL_HOME or "
                                f"OSINTINEL_NO_PERSIST=1"))

    # 8) Optional TUI dependency.
    try:
        import textual  # noqa: F401
        checks.append(Check("TUI (optional)", OK, "textual installed — `osintinel tui` available"))
    except ModuleNotFoundError:
        checks.append(Check("TUI (optional)", WARN,
                            "textual not installed — `pip install -e \".[tui]\"` for the terminal UI"))

    return checks


def diagnostics_ok(checks: list[Check]) -> bool:
    """True when nothing hard-failed (warnings are fine — the deterministic floor still runs)."""
    return not any(c.status == FAIL for c in checks)
