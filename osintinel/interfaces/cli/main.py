"""OSINTINEL CLI (doc 06 Phase 1–2).

Commands:
  osintinel run [--json] [--max-iterations N]   run the bundled demo investigation
  osintinel report                              run the demo and print the InsightReport
  osintinel verify [--ledger PATH]              run, persist the ledger, reload & replay it,
                                                and prove a byte-identical graph + hash chain
  osintinel audit                               print the full evidence chain for the leading
                                                insight (terminating in sourced INFORMATION)

The deterministic bundled scenario makes the full recursive loop demonstrable offline. Custom
investigations (file/image inputs) arrive with the adapter framework in Phase 3.
"""

from __future__ import annotations

import argparse
import sys

from ...core.runtime import InvestigationController
from ...graph import build_graph, chain_terminates_in_information, evidence_chain
from ...ledger import Ledger, replay_state
from ...scenarios import build_demo_investigation


def _run_demo(max_iterations: int | None, ledger_path=None):
    investigation, registry = build_demo_investigation()
    if max_iterations is not None:
        investigation.config.max_iterations = max_iterations
    controller = InvestigationController(registry, ledger_path=ledger_path)
    return controller.run(investigation)


def _print_human(result) -> None:
    r = result.report
    print("\n=== OSINTINEL Insight Report ===")
    print(f"Investigation : {result.investigation.title}")
    print(f"Iterations    : {result.loop.iterations}  "
          f"(terminated: {result.loop.termination.reason})")
    print(f"Ledger events : {len(result.ledger)}  (chain verified: "
          f"{result.ledger.verify()})")
    print(f"\n-- Executive Summary --\n{r.executive_summary}")
    print(f"\n-- Information Summary --\n{r.information_summary}")
    print("\n-- Connective Probability Scores (competing hypotheses preserved) --")
    for cps in r.connective_probability_scores:
        print(f"  Q: {cps.question}")
        for rh in cps.ranked_hypotheses:
            backing = rh.explanation_type.value.lower() if rh.explanation_type else "-"
            print(f"     [{rh.epistemic_class.value:10}] {rh.confidence:5.2f}  {rh.statement}"
                  f"  (explanation: {backing})")
        print(f"     residual 'none of the above' mass: {cps.residual_mass:.2f}")
    print("\n-- Known Unknowns --")
    for ku in r.known_unknowns or []:
        print(f"  - {ku.question}" + (" [BLOCKING]" if ku.blocking else ""))
    if not r.known_unknowns:
        print("  (none above threshold)")
    print("\n-- Unknown-Unknown Indicators --")
    for uu in r.unknown_unknown_indicators or []:
        print(f"  - [{uu.severity}] {uu.signal}: {uu.detail}")
    if not r.unknown_unknown_indicators:
        print("  (none detected)")
    if r.speculations:
        print(f"\n-- Speculation (quarantined) : {len(r.speculations)} item(s) --")
    print("\n-- Reasoning Chain --")
    for step in r.reasoning_chain:
        print(f"  {step.step}. [{step.epistemic_class.value}] ({step.agent}) {step.claim}")
    print("\n-- Recommended Next Investigations --")
    for s in r.recommended_next_investigations:
        print(f"  - {s}")
    print("\n-- Source Appendix --")
    for src in r.source_appendix:
        print(f"  - {src['source']} (group={src['independence_group']}, "
              f"method={src['acquisition_method']}, license={src.get('license_note')})")
    print(f"\n{r.confidence_calibration_note}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="osintinel", description="Open Source Intelligence Sentinel")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the bundled demo investigation")
    p_run.add_argument("--json", action="store_true", help="emit the report as JSON")
    p_run.add_argument("--max-iterations", type=int, default=None)

    sub.add_parser("report", help="run the demo and print the insight report")
    p_verify = sub.add_parser("verify", help="persist, reload & replay the ledger; verify integrity")
    p_verify.add_argument("--ledger", default=None,
                          help="path to write the durable JSONL ledger (default: temp file)")
    sub.add_parser("audit", help="print the evidence chain for the leading insight")
    sub.add_parser("adapters", help="list registered reference + license-gated adapters")
    sub.add_parser("slice", help="run the Phase 3 adapter vertical slice (offline, from cassettes)")
    p_mem = sub.add_parser("memory", help="run the Phase 4 learning benchmark (cost falls as Memory learns)")
    p_mem.add_argument("--rounds", type=int, default=5)
    sub.add_parser("image", help="run the Phase 5 image-geolocation pipeline on a sample image")
    sub.add_parser("geo", help="run the Phase 6 geospatial constraint-narrowing golden suite")
    p_dash = sub.add_parser("dashboard", help="render the Phase 7 self-contained HTML console")
    p_dash.add_argument("--out", default="osintinel-dashboard.html",
                        help="output HTML path (default: ./osintinel-dashboard.html)")
    sub.add_parser("models", help="show the model-tier config and exercise the inference gateway")
    sub.add_parser("independence", help="embed-tier demo: detect illusory (syndicated) source independence")
    sub.add_parser("reason", help="reason-tier demo: model-generated explanations + adversarial critique")
    sub.add_parser("improve", help="Phase 8: self-improvement — calibration + planner tuning across versions")
    p_serve = sub.add_parser("serve", help="launch the local web app (browser UI for investigations)")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--host", default="127.0.0.1")
    sub.add_parser("tui", help="launch the terminal UI (Textual) — full model control + mascot")
    sub.add_parser("mcp", help="run the MCP server (stdio) so Claude can drive OSINTINEL")
    sub.add_parser("doctor", help="preflight: check Python, deps, model endpoint, and persistence")
    p_hist = sub.add_parser("history", help="list saved investigation runs (~/.osintinel/runs)")
    p_hist.add_argument("--limit", type=int, default=20)
    sub.add_parser("research", help="autonomous web-research demo (gathers its own evidence, offline)")
    sub.add_parser("intel", help="free infra/threat adapters (Shodan InternetDB, URLScan, OTX) demo")
    sub.add_parser("records", help="free public-records adapters (OpenCorporates, SEC EDGAR, GLEIF) demo")

    args = parser.parse_args(argv)

    if args.command in ("run", "report"):
        result = _run_demo(getattr(args, "max_iterations", None))
        if getattr(args, "json", False):
            print(result.report.model_dump_json(indent=2))
        else:
            _print_human(result)
        return 0

    if args.command == "verify":
        return _verify(args.ledger)

    if args.command == "audit":
        return _audit()

    if args.command == "adapters":
        return _adapters()

    if args.command == "slice":
        return _slice()

    if args.command == "memory":
        return _memory(args.rounds)

    if args.command == "image":
        return _image()

    if args.command == "geo":
        return _geo()

    if args.command == "dashboard":
        return _dashboard(args.out)

    if args.command == "models":
        return _models()

    if args.command == "independence":
        return _independence()

    if args.command == "reason":
        return _reason()

    if args.command == "improve":
        return _improve()

    if args.command == "serve":
        from ...interfaces.web import serve
        serve(port=args.port, host=args.host)
        return 0

    if args.command == "tui":
        try:
            from ...interfaces.tui import run_tui
        except ModuleNotFoundError:
            print("The TUI needs Textual. Install it with:  pip install -e \".[tui]\"")
            return 1
        run_tui()
        return 0

    if args.command == "mcp":
        from ...interfaces.mcp import serve_stdio
        serve_stdio()
        return 0

    if args.command == "doctor":
        return _doctor()

    if args.command == "history":
        return _history(args.limit)

    if args.command == "research":
        return _research()

    if args.command == "intel":
        return _intel()

    if args.command == "records":
        return _records()

    return 1


def _records() -> int:
    """Demo the free public-records / corporate adapters (offline cassette)."""
    from pathlib import Path

    from ...adapters import (
        Cassette,
        GLEIFAdapter,
        HttpClient,
        OpenCorporatesAdapter,
        SECEdgarAdapter,
    )
    from ...core.schemas import AcquisitionMethod, AgentName, Provenance

    cdir = Path(__file__).resolve().parent.parent.parent / "adapters" / "_cassettes"
    company = "WindReach Telecom"

    def client():
        return HttpClient(Cassette(cdir / "records.json"))

    def prov():
        return Provenance(source="records", acquisition_method=AcquisitionMethod.API,
                          agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                          investigation_id="records-demo")

    print("\n=== OSINTINEL — free public-records adapters (offline demo) ===")
    print(f"Entity: {company}\n")
    runs = [
        ("OpenCorporates", OpenCorporatesAdapter(client()).acquire(
            "record.public", {"query": company}, prov())),
        ("SEC EDGAR", SECEdgarAdapter(client()).acquire(
            "record.public", {"query": company}, prov())),
        ("GLEIF", GLEIFAdapter(client()).acquire(
            "record.public", {"query": company}, prov())),
    ]
    for name, evs in runs:
        ev = evs[0]
        print(f"  [{name}] {ev.summary}")
        print(f"      source group: {ev.structured['independence_group']} · tool: "
              f"{ev.provenance.tool_used}")
    print("\nAll free/lawful. Live: OSINTINEL_NET=live (OpenCorporates optional free token via "
          "OPENCORPORATES_API_TOKEN; SEC EDGAR & GLEIF need no key).")
    return 0


def _intel() -> int:
    """Demo the free infra/threat-intel adapters (offline cassette)."""
    from pathlib import Path

    from ...adapters import (
        Cassette,
        HttpClient,
        OTXAdapter,
        ShodanInternetDBAdapter,
        UrlscanAdapter,
    )
    from ...core.schemas import AcquisitionMethod, AgentName, Provenance

    cdir = Path(__file__).resolve().parent.parent.parent / "adapters" / "_cassettes"
    domain, ip = "windreach-telecom.example", "203.0.113.10"

    def client():
        return HttpClient(Cassette(cdir / "intel.json"))

    def prov():
        return Provenance(source="intel", acquisition_method=AcquisitionMethod.API,
                          agent_responsible=AgentName.ACQUISITION, confidence=0.7,
                          investigation_id="intel-demo")

    print("\n=== OSINTINEL — free infra/threat-intel adapters (offline demo) ===")
    print(f"Target: {domain} / {ip}\n")
    runs = [
        ("Shodan InternetDB", ShodanInternetDBAdapter(client()).acquire(
            "infra.exposure", {"ip": ip}, prov())),
        ("URLScan.io", UrlscanAdapter(client()).acquire(
            "infra.urlscan", {"domain": domain}, prov())),
        ("AlienVault OTX", OTXAdapter(client()).acquire(
            "threat.intel", {"indicator": domain}, prov())),
    ]
    for name, evs in runs:
        ev = evs[0]
        print(f"  [{name}] {ev.summary}")
        print(f"      source group: {ev.structured['independence_group']} · "
              f"tool: {ev.provenance.tool_used} · license: {ev.provenance.license_note}")
    print("\nAll free / lawful (Shodan InternetDB & URLScan search need no key; OTX uses a free "
          "key). Live: OSINTINEL_NET=live, keys via URLSCAN_API_KEY / OTX_API_KEY.")
    return 0


def _doctor() -> int:
    """Preflight the environment so first-run problems surface as clear guidance, not tracebacks."""
    from ...service import diagnostics_ok, run_diagnostics

    glyph = {"ok": "✓", "warn": "!", "fail": "✗"}
    checks = run_diagnostics()
    print("\n=== OSINTINEL — doctor (environment preflight) ===")
    for c in checks:
        print(f"  [{glyph.get(c.status, '?')}] {c.name:18} {c.detail}")
    ok = diagnostics_ok(checks)
    warns = sum(1 for c in checks if c.status == "warn")
    if ok and not warns:
        print("\nAll green. Try:  osintinel serve   (→ http://127.0.0.1:8765)")
    elif ok:
        print(f"\nReady to run ({warns} optional warning(s) above — the deterministic floor still "
              "works). Try:  osintinel serve")
    else:
        print("\nSomething essential is missing (see ✗ above). Fix it, then re-run: osintinel doctor")
    return 0 if ok else 1


def _history(limit: int) -> int:
    """List persisted investigation runs (newest first)."""
    import datetime as _dt

    from ...service import RunStore

    runs = RunStore().list(limit)
    if not runs:
        print("No saved runs yet. Run an investigation (osintinel tui / serve) — history persists "
              "to ~/.osintinel/runs (set OSINTINEL_NO_PERSIST=1 to disable).")
        return 0
    print(f"{'when':19}  {'confidence':>10}  question → leading answer")
    for r in runs:
        when = _dt.datetime.fromtimestamp(r.get("saved_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
        conf = r.get("leader_confidence", 0.0)
        q = (r.get("question") or "")[:48]
        leader = (r.get("leader") or "")[:48]
        print(f"{when}  {conf:>9.0%}  {q} → {leader}")
    return 0


def _research() -> int:
    """Autonomous web-research demo: the system gathers its own evidence, then reasons over it."""
    import tempfile
    from pathlib import Path

    from ...adapters import Cassette, ContentAddressedStore, HttpClient, WebSearchAdapter
    from ...service import InvestigationSummary, autoresearch_investigation

    cdir = Path(__file__).resolve().parent.parent.parent / "adapters" / "_cassettes"
    cas = ContentAddressedStore(tempfile.mkdtemp())
    # untrusted open-web path: SSRF guard + polite throttle on (no-ops in offline replay)
    web_http = HttpClient(Cassette(cdir / "web.json"), block_private_net=True, min_interval=1.0)
    web = WebSearchAdapter(web_http, cas, backend="duckduckgo")
    question = "Bullington ridge communications mast"
    result = autoresearch_investigation(
        question=question, candidates=["communications mast", "wind turbine"],
        web_adapter=web, limit=3, rounds=2)  # iterative: chase known-unknowns if any surface
    s = InvestigationSummary.from_result(result)
    leader = result.report.connective_probability_scores[0].ranked_hypotheses[0]
    groups = sorted(result.state.independent_source_groups(leader.hypothesis_id))

    print("\n=== OSINTINEL — Autonomous web research (offline demo cassette) ===")
    print(f"Question: {question}\n")
    print(f"Gathered {len(result.state.evidence)} pages from {len(groups)} independent "
          f"domains: {', '.join(groups)}\n")
    print("Ranked answers:")
    for h in s.ranked:
        print(f"  {h['confidence']:.0%}  [{h['class']}]  {h['statement']}")
    print("\nThe leader reached "
          f"{leader.epistemic_class.value} on {len(groups)} independent sources; page bytes are "
          "in the content-addressed store, only refs in the ledger.")
    print("\n(Lawful default backend is Wikipedia; this demo uses a recorded DuckDuckGo result "
          "set to show multi-domain corroboration. Live: OSINTINEL_NET=live.)")
    return 0 if leader.epistemic_class.value == "INSIGHT" else 1


def _improve() -> int:
    """Phase 8: self-improvement — calibration + planner efficiency improve across versions,
    with a firewall audit proving no evidentiary history is touched."""
    from ...improvement import (
        assert_strategy_artifacts_only,
        audit_no_evidence_mutation,
        run_self_improvement,
    )
    from ...scenarios import build_demo_investigation

    report = run_self_improvement()
    b, a = report.before, report.after
    print("\n=== OSINTINEL Phase 8 — Self-Improvement ===")
    print(f"{'metric':22} {'v1 (' + b.version + ')':>18} {'v2 (' + a.version + ')':>18}   change")
    print(f"{'confidence ECE':22} {b.calibration_ece:>18.4f} {a.calibration_ece:>18.4f}   "
          f"{'-' if a.calibration_ece < b.calibration_ece else '+'}"
          f"{abs(b.calibration_ece - a.calibration_ece):.4f}")
    print(f"{'Brier score':22} {b.calibration_brier:>18.4f} {a.calibration_brier:>18.4f}")
    print(f"{'softmax temperature':22} {b.temperature:>18} {a.temperature:>18}")
    print(f"{'accuracy (preserved)':22} {b.accuracy:>18} {a.accuracy:>18}")
    print(f"{'planner tokens/case':22} {b.planner_tokens:>18} {a.planner_tokens:>18}   "
          f"{(1 - a.planner_tokens / b.planner_tokens) * 100:.0f}% cheaper")

    print("\nFirewall audit (self-improvement touches strategy only):")
    assert_strategy_artifacts_only(report)
    print("  report carries no evidence content: PASS")
    _, registry = build_demo_investigation()
    result = InvestigationController(registry).run(build_demo_investigation()[0])
    audit_no_evidence_mutation(result, run_self_improvement)
    print("  ledger hash chain + confidence history unchanged by tuning: PASS")

    print(f"\nVerdict: calibration {'improved' if report.calibration_improved else 'flat'}, "
          f"planner {'improved' if report.planner_improved else 'flat'}, "
          f"accuracy {'preserved' if report.accuracy_preserved else 'changed'}.")
    return 0 if report.improved else 1


def _reason() -> int:
    """Reason-tier demo: model-generated competing explanations + adversarial critique."""
    from ...scenarios.reason_demo import run_reason_demo

    r = run_reason_demo()
    print("\n=== OSINTINEL Phase M (reason tier) — open-ended model reasoning ===")
    print("Question: What is the circular structure on the ridge?\n")
    print(f"Competing explanations: {r.given} given → {r.after_connections} after the reason "
          f"tier proposed new ones:")
    for s in r.proposed:
        print(f"    + {s}")
    print("\nSkeptic — model-authored objections (advisory; structural gates still own blocking):")
    for category, severity, desc in r.model_findings:
        print(f"  [{severity:6}] {category}: {desc}")
    print(f"\nreason-tier model calls recorded in the ledger: {r.model_calls}")
    ok = r.after_connections > r.given and len(r.model_findings) >= 1
    print(f"reason tier working: {'YES' if ok else 'NO'}  "
          f"(model widened the hypothesis space and challenged the leader)")
    return 0 if ok else 1


def _independence() -> int:
    """Embed-tier demo: collapse near-duplicate 'independent' sources (doc 11 §6)."""
    from ...scenarios.independence_demo import run_independence_demo

    r = run_independence_demo()
    print("\n=== OSINTINEL Phase M (embed tier) — illusory source independence ===")
    print("A leader corroborated by OpenStreetMap + Regional Newswire (both carrying the same")
    print("syndicated text), then by a genuinely distinct Wikidata entity.\n")
    merged = "; ".join("≈".join(c) for c in r.merged_clusters) or "(none)"
    print(f"Before distinct source:  declared independent groups = {r.declared_before}, "
          f"effective (after dedup) = {r.effective_before}  [collapsed: {merged}]")
    print(f"  → Skeptic raised BLOCKING illusory-independence finding: {r.finding_raised}")
    print(f"After distinct source:   declared = {r.declared_after}, effective = {r.effective_after}")
    print(f"  → finding resolved (genuine corroboration): {r.finding_resolved}")
    ok = (r.effective_before < r.declared_before and r.finding_raised
          and r.effective_after >= 2 and r.finding_resolved)
    print(f"\nembed-tier guard working: {'YES' if ok else 'NO'}  "
          f"(syndicated corroboration no longer fools the Confidence gate)")
    return 0 if ok else 1


def _models() -> int:
    """Show the active inference profile, tier routing, and exercise the gateway."""
    from ...core.budget import BudgetGovernor
    from ...core.schemas import Budgets
    from ...inference import PROFILES, build_gateway, gateway_status
    from ...ledger import Ledger

    st = gateway_status()
    print("\n=== OSINTINEL — Model & Inference layer (doc 11) ===")
    print(f"Active profile: {st['profile']}  ({'local' if st['local'] else 'cloud'}, "
          f"{'free' if st['free'] else 'paid'}) — {st['note']}")
    if st["base_url"]:
        print(f"  endpoint: {st['base_url']}")
    print("Tier → model:")
    for tier, model in st["tier_models"].items():
        print(f"  {tier:7} → {model}")
    print(f"  embed   → {st['embed']['model']} ({st['embed']['kind']})")
    if st["key_env"]:
        print(f"  key: {st['key_env']} {'present' if st['key_present'] else 'NOT set'}")
    if st["reason_override"]:
        print(f"  reasoning tier overridden to profile: {st['reason_override']}")
    if st["skeptic_override"]:
        print(f"  Skeptic decorrelated onto profile: {st['skeptic_override']}")
    print(f"  network mode: {st['net_mode']}  (replay=offline/CI · record=build corpus · live=online)")
    print(f"\nAvailable profiles: {', '.join(sorted(PROFILES))}")
    print("Recommended (free): OSINTINEL_INFERENCE_PROFILE=ollama   (fully local & private)")
    print("  hybrid: keep ollama, add OSINTINEL_REASON_PROFILE=gemini|groq|openrouter for "
          "heavier free-cloud reasoning")

    gov = BudgetGovernor(Budgets())
    ledger = Ledger()
    # Exercise deterministically so 'models' always works (a live profile needs its endpoint);
    # the status above reflects whatever profile is actually configured.
    gw = build_gateway(profile="deterministic", governor=gov, ledger=ledger,
                       investigation_id="models-demo")
    gw.complete(tier="reason", role="connections",
                payload={"system": "Frame competing explanations.", "prompt": "ridge structure"})
    gw.complete(tier="task", role="tool_selection", payload={"prompt": "pick an adapter"})
    vecs = gw.embed(["a telecom mast", "a telecom mast", "a wind turbine"])

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))
    print(f"\nGateway exercise (profile '{st['profile']}'):")
    print(f"  embedding similarity — duplicate {cos(vecs[0], vecs[1]):.2f} vs "
          f"different {cos(vecs[0], vecs[2]):.2f}")
    print(f"  cost summary: {gw.cost_summary()}")
    print(f"  model_call ledger events: {sum(1 for e in ledger.events() if e.type == 'model_call')}"
          f" (lean: hashes + token counts only — no prompt/response bytes)")
    return 0


def _dashboard(out: str) -> int:
    """Run the demo investigation and render the self-contained HTML console."""
    from ...interfaces.api import build_dashboard_data
    from ...interfaces.dashboard import render_dashboard

    result = _run_demo(None)
    data = build_dashboard_data(result)
    html = render_dashboard(data)
    from pathlib import Path
    path = Path(out)
    path.write_text(html, encoding="utf-8")

    print("\n=== OSINTINEL Phase 7 — Investigation Console ===")
    print(f"Rendered self-contained dashboard → {path}  ({len(html) // 1024} KB)")
    print(f"  graph: {len(data.nodes)} nodes / {len(data.edges)} edges")
    print(f"  timeline: {len(data.timeline)} iterations, {len(data.events)} ledger events")
    print(f"  confidence tracks: {len(data.hypothesis_tracks)}  "
          f"| sources: {len(data.sources)}  | agents: {len(data.agent_activity)}")
    print("  offline & self-contained: no external scripts, styles, fonts, or network calls.")
    return 0


def _geo() -> int:
    """Run the geospatial golden suite: narrow each case across ≥3 independent constraints."""
    from ...scenarios.geospatial_demo import (
        CONFLICT_CASE,
        GOLDEN_CASES,
        narrowing_curve,
        run_geospatial_demo,
        solve_case,
    )

    print("\n=== OSINTINEL Phase 6 — Geospatial constraint narrowing ===")
    print(f"{'golden case':24} {'groups':>6} {'radius':>9} {'conf':>6} {'error':>8}  truth-in-radius")
    results = run_geospatial_demo()
    covered = 0
    for r in results:
        e = r.estimate
        covered += int(r.within_radius)
        print(f"{r.case.name:24} {e.n_independent:>6} {e.radius_km:>7.1f}km {e.confidence:>6.2f} "
              f"{r.error_km:>6.1f}km  {'yes' if r.within_radius else 'NO'}")
    print(f"\nCoverage (truth within stated radius): {covered}/{len(results)} golden cases.")

    curve = narrowing_curve(GOLDEN_CASES[1])
    print("\nLocation narrows as independent constraints intersect (Valais alps):")
    for groups, radius in curve:
        bar = "#" * max(1, int(40 * radius / curve[0][1]))
        print(f"  {groups} independent constraint group(s): {radius:8.1f} km  {bar}")

    conflict = solve_case(CONFLICT_CASE)
    print(f"\nCalibration check — conflicting constraints: confidence "
          f"{conflict.estimate.confidence:.2f} (low, as it should be), radius "
          f"{conflict.estimate.radius_km:.0f} km.")
    ok = covered == len(results) and conflict.estimate.confidence < 0.3
    return 0 if ok else 1


def _image() -> int:
    """Run the image-investigation pipeline and print ranked geolocation hypotheses."""
    from ...scenarios.image_demo import run_image_demo

    r = run_image_demo()
    print("\n=== OSINTINEL Phase 5 — Image Investigation (geolocation) ===")
    print("Question: Where was this image taken?\n")
    print("Ranked location hypotheses:")
    for i, f in enumerate(r.ranked):
        print(f"  {i + 1}. {f.name:32} {f.confidence:5.2f}  [{f.epistemic_class}]  "
              f"(+{len(f.supporting)} supporting / -{len(f.contradicting)} contradicting)")
    leader = r.leader
    print(f"\nLeading location: {leader.name}  [{leader.epistemic_class}]")
    print("  Supporting evidence:")
    for s in leader.supporting:
        print(f"    + {s}")
    print("  Contradicting evidence (surfaced, not hidden):")
    for s in leader.contradicting:
        print(f"    - {s}")
    print(f"\nSkeptic gate: challenged single-source leader = "
          f"{r.leader_challenged_single_source}; held at "
          f"{r.leader_class_when_single_source} until independent corroboration "
          f"(now {leader.epistemic_class}).")
    print("\nRecommended next investigations:")
    for s in r.next_steps():
        print(f"  - {s}")
    ok = (leader.epistemic_class == "INSIGHT" and bool(leader.contradicting)
          and r.leader_challenged_single_source)
    return 0 if ok else 1


def _memory(rounds: int) -> int:
    """Run the learning benchmark and show cost falling as Investigation Memory learns."""
    from ...memory import MemoryPriors, verify_read_only
    from ...scenarios.learning_benchmark import run_learning_benchmark

    memory, results = run_learning_benchmark(rounds)
    print("\n=== OSINTINEL Phase 4 — Investigation Memory (learning benchmark) ===")
    print(f"{'round':>5}  {'adapter chosen':14}  {'iters':>5}  {'tokens':>7}")
    for i, r in enumerate(results):
        flag = "  <- misleading seed" if i == 0 else (
            "  <- learned" if r.selected_adapter == "geo.reliable" else "")
        print(f"{i:>5}  {r.selected_adapter:14}  {r.iterations:>5}  {r.tokens:>7}{flag}")
    first, last = results[0].tokens, results[-1].tokens
    saved = (1 - last / first) * 100 if first else 0
    print(f"\nLearned effectiveness:  geo.reliable={memory.adapter_effectiveness('geo.reliable'):.2f}"
          f"   geo.noisy={memory.adapter_effectiveness('geo.noisy'):.2f}")
    print(f"Cost to solve the same case: {first} -> {last} tokens ({saved:.0f}% cheaper).")
    # The priors handed to agents are firewall-safe: no evidence handle, no mutator.
    verify_read_only(MemoryPriors(memory))
    print("Firewall: priors expose strategy only — no path to read or rewrite evidence.")
    return 0 if last <= first else 1


def _verify(ledger_path: str | None) -> int:
    """Run, persist the ledger to disk, reload it, replay → graph, and check every guarantee."""
    import os
    import tempfile

    tmp = ledger_path or os.path.join(tempfile.mkdtemp(), "ledger.jsonl")
    result = _run_demo(None, ledger_path=tmp)

    chain_ok = result.ledger.verify()
    reloaded = Ledger.load(tmp)                      # re-verifies the hash chain on load
    replayed = replay_state(reloaded)                # rebuild state from the event log alone
    identical = result.state.snapshot() == replayed.snapshot()
    graph_ok = build_graph(replayed).summary() == build_graph(result.state).summary()

    print(f"ledger written      : {tmp} ({len(result.ledger)} events)")
    print(f"hash chain verified : {chain_ok and reloaded.verify()}")
    print(f"replay byte-identical: {identical}")
    print(f"graph reconstructed : {graph_ok}")
    ok = chain_ok and identical and graph_ok
    print(f"\nPhase 2 guarantees: {'ALL PASS' if ok else 'FAILED'}")
    return 0 if ok else 1


def _audit() -> int:
    """Materialize the graph and walk the evidence chain beneath the leading insight."""
    result = _run_demo(None)
    store = build_graph(result.state)
    cps = result.report.connective_probability_scores[0]
    leader = cps.ranked_hypotheses[0]

    print("\n=== OSINTINEL Evidence Chain (audit) ===")
    print(f"Insight: {leader.statement!r}  "
          f"[{leader.epistemic_class.value} / {leader.explanation_type.value.lower()}]  "
          f"confidence {leader.confidence:.2f}\n")
    for n in evidence_chain(store, leader.hypothesis_id):
        cls = f" ({n.epistemic_class.value})" if n.epistemic_class else ""
        print(f"  - {n.node_type}{cls}: {n.label}")
    ok = chain_terminates_in_information(store, leader.hypothesis_id)
    print(f"\nChain terminates in sourced INFORMATION: {ok}  "
          f"(auditability guarantee, doc 03 §16.3)")
    return 0 if ok else 1


def _adapters() -> int:
    """List the registered lawful adapters and the license-gated supplemental catalogue."""
    from ...adapters import ContentAddressedStore
    from ...adapters.commercial import MaltegoAdapter
    from ...scenarios.archive_slice import build_registry

    import tempfile
    registry = build_registry(ContentAddressedStore(tempfile.mkdtemp()))
    print("\n=== Reference adapters (lawful, public-source; enabled) ===")
    for a in sorted(registry.all(), key=lambda x: x.id):
        print(f"  {a.id:20} eff={registry.effectiveness(a.id):.2f}  "
              f"caps: {', '.join(a.capabilities)}")
    print("\n=== Supplemental adapters (license-gated; OFF by default) ===")
    m = MaltegoAdapter.__new__(MaltegoAdapter)
    print(f"  {m.id:20} vendor={m.vendor}  caps: {', '.join(m.capabilities)}")
    print(f"  (enable with credentials in {MaltegoAdapter.auth_env} + "
          f"OSINTINEL_ATTEST_AUTHORIZED=1)")
    return 0


def _slice() -> int:
    """Run the Phase 3 vertical slice and show selection-by-capability + the storage split."""
    from ...scenarios.archive_slice import run_archive_slice

    result = run_archive_slice()
    mast = result.state.hypotheses[result.mast_hypothesis_id]
    raws = [e for e in result.ledger.events() if e.type == "raw_response"]

    print("\n=== OSINTINEL Phase 3 — adapter vertical slice (offline, from cassettes) ===")
    print(f"Tool Selection chose by capability: {', '.join(result.selected_adapters)}")
    print(f"\nLeading hypothesis: {mast.statement!r}")
    print(f"  confidence {mast.confidence:.2f}  ->  {mast.epistemic_class.value}  "
          f"(independent groups: "
          f"{sorted(result.state.independent_source_groups(result.mast_hypothesis_id))})")
    print("\nStorage split (the integral decision):")
    for e in raws:
        ch = e.payload["content_hash"]
        in_cas = result.cas.has(ch)
        size = len(result.cas.get(ch)) if in_cas else 0
        print(f"  {e.payload['adapter']:18} bytes={e.payload['bytes'] or 0:>5}  "
              f"cas={'yes' if in_cas else 'inline':5} ({size} B)  hash={ch[:12]}…")
    largest = max(len(e.model_dump_json()) for e in result.ledger.events())
    print(f"\nLedger stays lean: largest event {largest} B; raw bytes never enter the ledger.")
    from ...ledger import replay_state
    identical = replay_state(result.ledger).snapshot() == result.state.snapshot()
    print(f"Replayable offline: byte-identical state from the ledger = {identical}")
    return 0 if identical else 1


if __name__ == "__main__":
    sys.exit(main())
