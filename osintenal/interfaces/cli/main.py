"""OSINTENAL CLI (doc 06 Phase 1).

Commands:
  osintenal run [--json] [--max-iterations N]   run the bundled demo investigation
  osintenal report                              run the demo and print the InsightReport
  osintenal verify                              run the demo and verify ledger integrity

Phase 1 runs the deterministic bundled scenario so the full recursive loop is demonstrable
offline. Custom investigations (file/image inputs) arrive with the adapter framework in
Phase 3.
"""

from __future__ import annotations

import argparse
import json
import sys

from ...core.runtime import InvestigationController
from ...scenarios import build_demo_investigation


def _run_demo(max_iterations: int | None):
    investigation, registry = build_demo_investigation()
    if max_iterations is not None:
        investigation.config.max_iterations = max_iterations
    controller = InvestigationController(registry)
    return controller.run(investigation)


def _print_human(result) -> None:
    r = result.report
    print(f"\n=== OSINTENAL Insight Report ===")
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
    sub.add_parser("verify", help="run the demo and verify ledger integrity")

    args = parser.parse_args(argv)

    if args.command in ("run", "report"):
        result = _run_demo(getattr(args, "max_iterations", None))
        if getattr(args, "json", False):
            print(result.report.model_dump_json(indent=2))
        else:
            _print_human(result)
        return 0

    if args.command == "verify":
        result = _run_demo(None)
        ok = result.ledger.verify()
        print(f"ledger chain verified: {ok} ({len(result.ledger)} events)")
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
