#!/usr/bin/env python3
"""Run the plan-flow and reviewer evals a change affects, gate them, and exit with the release decision.

    python3 scripts/run-evals.py [--plugin NAME] [--since REF] [--all | --smoke]
        [--dry-run] [--yes] [--claude PATH]

Exit 0 ok, 1 regression, 2 harness failure or bad input, 3 needs confirmation (estimate above
CONFIRM_ABOVE_USD with no TTY and no --yes). Runs use the `claude` CLI as already authenticated
on this machine; no credential is read or passed.
"""
import argparse, importlib.util, json, pathlib, re, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PF_DIR = ROOT / "plugins/plan-flow"
PF_RESULTS = PF_DIR / "evals/results"
RV_DIR = ROOT / "tests/review-flow/reviewer-evals"
RV_RESULTS = RV_DIR / "results"

# USD, API-list equivalent per run; estimates to refresh from results.
COST_PER_RUN = {
    "plan-writing": 0.45, "plan-execution": 0.60, "plan-command": 0.13,
    "comment-rules": 0.08, "debugging": 0.45, "intent": 0.50, "reviewer": 0.10,
}
CONFIRM_ABOVE_USD = 10.0
REVIEWER_RUNS = 3
MIN_CASE_CEILING_USD = 2.0
CEILING_FACTOR = 1.5


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


es = _load("eval_select", "eval-select.py")
gate = _load("eval_gate", "eval-gate.py")


def compute_selection(args):
    if args.all:
        return {"ref": None, **es.all_selection(ROOT)}
    if args.smoke:
        return {"ref": None, **es.SMOKE}
    ref = es.resolve_ref(args.plugin, args.since, ROOT)
    return {"ref": ref, **es.select(es.changed_files(ref, ROOT), ROOT)}


def _case_runs(case):
    m = re.search(r"^runs:\s*(\d+)", (PF_DIR / "evals" / case / "case.yaml").read_text(), re.M)
    return int(m.group(1)) if m else 3


def pf_runs(entry):
    """(cases, runs) a plan-flow entry executes."""
    if entry.get("case"):
        return 1, _case_runs(entry["case"])
    cases = [p.name for p in sorted((PF_DIR / "evals").glob("[0-9]*"))
             if es._case_tier(ROOT, p.name) == entry["tier"]]
    return len(cases), sum(_case_runs(c) for c in cases)


def pf_estimate(entry):
    return pf_runs(entry)[1] * COST_PER_RUN[entry["tier"]]


def rv_rows(name):
    try:
        return len(json.loads((RV_DIR / "cases" / name / "case.json").read_text())["variants"])
    except (OSError, ValueError, KeyError):
        return 1


def rv_estimate(names):
    return sum(rv_rows(n) for n in names) * REVIEWER_RUNS * COST_PER_RUN["reviewer"]


def describe(sel):
    lines, total = [], 0.0
    for e in sel["plan_flow"]:
        cases, runs = pf_runs(e)
        est = runs * COST_PER_RUN[e["tier"]]
        total += est
        label = f'{e["tier"]}' + (f' / {e["case"]}' if e.get("case") else "")
        lines.append(f"  plan-flow {label}: {cases} case(s), {runs} run(s), ~${est:.2f}")
    if sel["reviewer"]:
        est = rv_estimate(sel["reviewer"])
        total += est
        rows = sum(rv_rows(n) for n in sel["reviewer"])
        lines.append(f'  reviewer: {len(sel["reviewer"])} case(s) {", ".join(sel["reviewer"])}: '
                     f"{rows} row(s), {rows * REVIEWER_RUNS} run(s), ~${est:.2f}")
    return lines, total


def run_plan_flow(sel, claude, run_dir):
    outputs = []
    for n, entry in enumerate(sel["plan_flow"], 1):
        out = run_dir / f"pf-{n}.json"
        ceiling = max(MIN_CASE_CEILING_USD, CEILING_FACTOR * pf_estimate(entry))
        argv = [claude, "plugin", "eval", ".", *es.pf_argv(entry),
                "--json", str(out), "--max-cost-usd", f"{ceiling:.2f}"]
        print(f"+ (cd {PF_DIR}) {' '.join(argv)}", flush=True)
        subprocess.run(argv, cwd=PF_DIR)
        outputs.append(out)
    return outputs


def run_reviewer(names, claude, rv_dir):
    for name in names:
        argv = [sys.executable, str(RV_DIR / "run.py"), "--case", name, "--runs", str(REVIEWER_RUNS),
                "-j", "2", "--out", str(rv_dir), "--claude", claude]
        print("+ " + " ".join(argv), flush=True)
        subprocess.run(argv)
    argv = [sys.executable, str(RV_DIR / "run.py"), "--regrade", str(rv_dir)]
    print("+ " + " ".join(argv), flush=True)
    subprocess.run(argv)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plugin")
    ap.add_argument("--since")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--claude", default="claude")
    args = ap.parse_args(argv)

    try:
        sel = compute_selection(args)
    except ValueError as e:
        print(f"run-evals: {e}", file=sys.stderr)
        return 2

    if not sel["plan_flow"] and not sel["reviewer"]:
        print(f'nothing to measure since {sel["ref"]}')
        return 0

    lines, total = describe(sel)
    print("selection" + (f' since {sel["ref"]}' if sel["ref"] else "") + ":")
    print("\n".join(lines))
    print(f"estimate: ~${total:.2f} (API-list equivalent)")
    if args.dry_run:
        return 0

    if total > CONFIRM_ABOVE_USD and not args.yes:
        if not sys.stdin.isatty():
            print(f"estimate ${total:.2f} above ${CONFIRM_ABOVE_USD:.0f}; pass --yes", file=sys.stderr)
            return 3
        print("Proceed? [y/N] ", end="", flush=True)
        if sys.stdin.readline().strip().lower() != "y":
            print("cancelled")
            return 0

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = PF_RESULTS / f"run-{stamp}"
    rv_dir = RV_RESULTS / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    pf_outputs = run_plan_flow(sel, args.claude, run_dir)
    if sel["reviewer"]:
        rv_dir.mkdir(parents=True, exist_ok=True)
        run_reviewer(sel["reviewer"], args.claude, rv_dir)

    pf_files = [p for p in pf_outputs if p.exists()]
    rv_summary = rv_dir / "summary.json"
    gate_argv = ["--summary", str(run_dir / "gate.md")]
    if pf_files:
        gate_argv += ["--plan-flow", *map(str, pf_files)]
    if rv_summary.exists():
        gate_argv += ["--reviewer", str(rv_summary)]
    print()
    rc = gate.main(gate_argv)

    missing = [p.name for p in pf_outputs if not p.exists()]
    if sel["reviewer"] and not rv_summary.exists():
        missing.append("reviewer summary.json")
    if missing and rc == 0:
        print(f'harness failure: no result written for {", ".join(missing)}', file=sys.stderr)
        rc = 2

    if pf_outputs:
        print(f"plan-flow results: {run_dir}")
    if sel["reviewer"]:
        print(f"reviewer results: {rv_dir}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
