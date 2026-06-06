"""OSINTENAL CLI (doc 06 Phase 1–2).

Commands:
  osintenal run [--json] [--max-iterations N]   run the bundled demo investigation
  osintenal report                              run the demo and print the InsightReport
  osintenal verify [--ledger PATH]              run, persist the ledger, reload & replay it,
                                                and prove a byte-identical graph + hash chain
  osintenal audit                               print the full evidence chain for the leading
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
    print("\n=== OSINTENAL Insight Report ===")
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
    parser = argparse.ArgumentParser(prog="osintenal", description="Open Source Intelligence Sentinel")
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

    return 1


def _geo() -> int:
    """Run the geospatial golden suite: narrow each case across ≥3 independent constraints."""
    from ...scenarios.geospatial_demo import (
        CONFLICT_CASE,
        GOLDEN_CASES,
        narrowing_curve,
        run_geospatial_demo,
        solve_case,
    )

    print("\n=== OSINTENAL Phase 6 — Geospatial constraint narrowing ===")
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
    print("\n=== OSINTENAL Phase 5 — Image Investigation (geolocation) ===")
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
    print("\n=== OSINTENAL Phase 4 — Investigation Memory (learning benchmark) ===")
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

    print("\n=== OSINTENAL Evidence Chain (audit) ===")
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
          f"OSINTENAL_ATTEST_AUTHORIZED=1)")
    return 0


def _slice() -> int:
    """Run the Phase 3 vertical slice and show selection-by-capability + the storage split."""
    from ...scenarios.archive_slice import run_archive_slice

    result = run_archive_slice()
    mast = result.state.hypotheses[result.mast_hypothesis_id]
    raws = [e for e in result.ledger.events() if e.type == "raw_response"]

    print("\n=== OSINTENAL Phase 3 — adapter vertical slice (offline, from cassettes) ===")
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
