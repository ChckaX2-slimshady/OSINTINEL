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

    return 1


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


if __name__ == "__main__":
    sys.exit(main())
