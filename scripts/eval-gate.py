#!/usr/bin/env python3
"""Compare eval results with committed baselines and exit non-zero on regression.

    python3 scripts/eval-gate.py [--plan-flow RESULT.json ...] [--reviewer SUMMARY.json ...]
        [--pf-baseline PATH] [--rv-baseline PATH] [--summary OUT.md]

Exit 0 ok, 1 regression, 2 harness failure or unreadable input. A grader failing every run is
a regression and one miss in three is variance; an invalid run is a harness failure, never a score.
"""
import argparse, importlib.util, json, pathlib, sys
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent
PF_SCORE_DROP = 0.20
RV_RATE_DROP = 0.34
RV_FP_RISE = 1.0
PF_MIN_RUNS_FOR_CONSISTENT = 2

DEFAULT_PF_BASELINE = ROOT / "plugins/plan-flow/evals/baseline.json"
DEFAULT_RV_BASELINE = ROOT / "tests/review-flow/reviewer-evals/baselines/baseline.json"
ORDER = {"regressed": 0, "harness": 1, "unbaselined": 2, "ok": 3}


@dataclass
class Verdict:
    harness: str
    key: str
    status: str
    reasons: list = field(default_factory=list)


class InputError(Exception):
    pass


def _load_check_run():
    path = ROOT / "plugins/plan-flow/evals/check-run.py"
    spec = importlib.util.spec_from_file_location("check_run", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_json(path, missing_ok=False):
    p = pathlib.Path(path)
    if missing_ok and not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        raise InputError(f"eval-gate: cannot read {path}")


def pf_metrics(result):
    """Per-case run count, score and per-grader pass counts from a plan-flow result."""
    out = {}
    for case in result.get("cases", []):
        runs = case.get("arms", {}).get("with", [])
        graders = {}
        for run in runs:
            for g in run.get("graders", []):
                if g.get("withOnly") or not g.get("scored", True):
                    continue
                graders[g["name"]] = graders.get(g["name"], 0) + (1 if g.get("passed") else 0)
        out[case["name"]] = {"runs": len(runs),
                             "score": case.get("aggregates", {}).get("score", 0.0),
                             "graders": graders}
    return out


def pf_harness(result):
    """case -> reasons; every case of a partial result, and any run check-run.py rejects."""
    bad = {}
    if result.get("partial"):
        reason = "partial result (%s)" % result.get("partialReason", "unknown reason")
        for case in result.get("cases", []):
            bad.setdefault(case["name"], []).append(reason)
        return bad
    for name, arm, i, reason in _load_check_run().verdicts(result):
        bad.setdefault(name, []).append(f"{arm} run {i}: {reason}")
    for case in result.get("cases", []):
        if not any(case.get("arms", {}).values()):
            bad.setdefault(case["name"], []).append("no runs")
    return bad


def compare_pf(base, cur):
    """`base` is the baseline document, `cur` is `pf_metrics` output."""
    base_cases = (base or {}).get("cases", {})
    out = []
    for name in sorted(cur):
        c = cur[name]
        b = base_cases.get(name)
        if b is None:
            out.append(Verdict("plan-flow", name, "unbaselined"))
            continue
        reasons = []
        if c["runs"] >= PF_MIN_RUNS_FOR_CONSISTENT:
            for g, passed in sorted(c["graders"].items()):
                if passed == 0 and b.get("graders", {}).get(g, 0) >= 1:
                    reasons.append(f"grader {g} failed every run (baseline "
                                   f"{b['graders'][g]}/{b.get('runs', '?')})")
        if c["score"] < b.get("score", 0.0) - PF_SCORE_DROP:
            reasons.append(f"score {c['score']:.2f} < baseline {b['score']:.2f} − {PF_SCORE_DROP:.2f}")
        out.append(Verdict("plan-flow", name, "regressed" if reasons else "ok", reasons))
    return out


def _rate_drop(field_, cur_n, cur_d, base_n, base_d):
    if not cur_d or not base_d:
        return None
    if cur_n / cur_d < base_n / base_d - RV_RATE_DROP:
        return f"{field_} {cur_n}/{cur_d} (baseline {base_n}/{base_d})"
    return None


def compare_rv(base, cur):
    """`base` is the baseline document, `cur` a reviewer `summary.json`.

    caught is rated over parsed runs (unparsed is a parser limit, not a miss); scope_ok and
    claim_ok are rated over caught runs.
    """
    base_rows = (base or {}).get("rows", {})
    out = []
    for key in sorted(cur.get("rows", {})):
        c = cur["rows"][key]
        b = base_rows.get(key)
        if c.get("invalid", 0) > 0:
            out.append(Verdict("reviewer", key, "harness",
                               [f"invalid {c['invalid']}/{c.get('total', '?')} runs"]))
            continue
        if b is None:
            out.append(Verdict("reviewer", key, "unbaselined"))
            continue
        reasons = []
        if c.get("caught") is not None and b.get("caught") is not None:
            r = _rate_drop("caught", c["caught"], c.get("parsed", 0), b["caught"], b.get("runs", 0))
            if r:
                reasons.append(r)
            if c.get("scope_ok") is not None and b.get("scope_ok") is not None:
                r = _rate_drop("scope_ok", c["scope_ok"], c["caught"], b["scope_ok"], b["caught"])
                if r:
                    reasons.append(r)
            if c.get("claim_ok") is not None and b.get("claim_ok") is not None:
                r = _rate_drop("claim_ok", c["claim_ok"], c["caught"], b["claim_ok"], b["caught"])
                if r:
                    reasons.append(r)
        if c.get("fp_mean", 0.0) > b.get("fp_mean", 0.0) + RV_FP_RISE:
            reasons.append(f"fp_mean {c['fp_mean']:.2f} > baseline {b['fp_mean']:.2f} + {RV_FP_RISE:.1f}")
        status = "regressed" if reasons else "ok"
        if not reasons and c.get("unparsed", 0) > 0:
            reasons.append(f"unparsed {c['unparsed']}/{c.get('valid', c.get('total', '?'))}")
        out.append(Verdict("reviewer", key, status, reasons))
    return out


def render(verdicts, headers):
    lines = list(headers)
    if lines:
        lines.append("")
    lines += ["| harness | case | status | reasons |", "| --- | --- | --- | --- |"]
    for v in sorted(verdicts, key=lambda v: ORDER[v.status]):
        lines.append(f"| {v.harness} | {v.key} | {v.status} | {'; '.join(v.reasons)} |")
    return "\n".join(lines) + "\n"


def _apply_harness(verdicts, bad):
    out = []
    for v in verdicts:
        if v.key in bad:
            out.append(Verdict(v.harness, v.key, "harness", bad[v.key]))
        else:
            out.append(v)
    seen = {v.key for v in verdicts}
    for key in bad:
        if key not in seen:
            out.append(Verdict("plan-flow", key, "harness", bad[key]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan-flow", nargs="*", default=[], metavar="RESULT.json")
    ap.add_argument("--reviewer", nargs="*", default=[], metavar="SUMMARY.json")
    ap.add_argument("--pf-baseline", default=str(DEFAULT_PF_BASELINE))
    ap.add_argument("--rv-baseline", default=str(DEFAULT_RV_BASELINE))
    ap.add_argument("--summary")
    args = ap.parse_args(argv)

    verdicts, headers = [], []
    try:
        pf_base = _read_json(args.pf_baseline, missing_ok=True)
        rv_base = _read_json(args.rv_baseline, missing_ok=True)
        for path in args.plan_flow:
            result = _read_json(path)
            vs = _apply_harness(compare_pf(pf_base, pf_metrics(result)), pf_harness(result))
            verdicts += vs
            headers.append(f"**plan-flow** `{path}`: claudeVersion {result.get('claudeVersion', 'unknown')}, "
                           f"cost ${result.get('costUsd', 0.0):.2f}")
        for path in args.reviewer:
            summary = _read_json(path)
            verdicts += compare_rv(rv_base, summary)
            cost = sum(r.get("cost", 0.0) for r in summary.get("rows", {}).values())
            headers.append(f"**reviewer** `{path}`: cost ${cost:.2f}")
    except InputError as e:
        print(e, file=sys.stderr)
        return 2

    text = render(verdicts, headers)
    print(text, end="")
    if args.summary:
        pathlib.Path(args.summary).write_text(text)
    if any(v.status == "regressed" for v in verdicts):
        return 1
    if any(v.status == "harness" for v in verdicts):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
