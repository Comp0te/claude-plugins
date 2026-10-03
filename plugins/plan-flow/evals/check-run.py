#!/usr/bin/env python3
"""Reject an eval result whose numbers are harness artifacts rather than measurements.

A run the harness could not finish — a session limit, a timeout, a crashed child — still lands
in the JSON with a score, and an `llm` grader that never executed is recorded as *failed*. The
result is a score table that looks like a finding and reads like one. This says which runs are
real before anyone reads them.

    python3 evals/check-run.py <result.json>     exit 1 if any run is unusable
"""
import json, pathlib, sys

PAID = ("llm", "baseline")


def verdicts(result):
    """(case, arm, index, reason) for every run that cannot be trusted."""
    bad = []
    for case in result.get("cases", []):
        graders = {g["name"]: g.get("type") for g in case.get("graders", [])}
        paid = {name for name, kind in graders.items() if kind in PAID}
        for arm, runs in case.get("arms", {}).items():
            for i, run in enumerate(runs):
                if run.get("error"):
                    bad.append((case["name"], arm, i, run["error"]))
                elif run.get("skippedPaidGraders"):
                    bad.append((case["name"], arm, i, "paid graders skipped (cost ceiling)"))
                elif paid and not run.get("judgeCostUsd"):
                    scored = {g["name"] for g in run.get("graders", [])} & paid
                    if scored:
                        bad.append((case["name"], arm, i,
                                    "judge cost is zero but %s is an llm grader — it did not run"
                                    % sorted(scored)[0]))
    return bad


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    result = json.loads(pathlib.Path(argv[0]).read_text())
    if result.get("partial"):
        print("partial result (%s): some runs never started; re-run before reading the table."
              % result.get("partialReason", "unknown reason"))
        return 1
    bad = verdicts(result)
    total = sum(len(runs) for c in result.get("cases", []) for runs in c.get("arms", {}).values())
    if not total:
        # A result with no runs measured nothing, whatever the exit code said.
        print("no runs in this result — the filter matched no cases, or none started.")
        return 1
    if not bad:
        print("%d run(s) usable; no harness errors, no ungraded paid graders." % total)
        return 0
    print("%d of %d run(s) are not measurements:" % (len(bad), total))
    for case, arm, i, reason in bad:
        print("  %s [%s run %d] %s" % (case, arm, i, reason))
    print("\nA case with any listed run scores an artifact. Re-run it before reading the table.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
