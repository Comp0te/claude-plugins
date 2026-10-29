#!/usr/bin/env python3
"""Map files changed since a ref to the plan-flow tiers and reviewer cases that measure them."""
import argparse, fnmatch, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PF_EVALS = "plugins/plan-flow/evals"
REVIEWER_EVALS = "tests/review-flow/reviewer-evals"

# Each tier's grant is load-bearing (plugins/plan-flow/evals/README.md, "Running it").
TIER_FLAGS = {
    "plan-writing":   ["--allow-tools", "Write", "Edit"],
    "plan-execution": ["--allow-tools", "Write", "Edit", "Bash"],
    "plan-command":   ["--allow-tools", "Write", "Edit", "Bash"],
    "comment-rules":  ["--allow-tools", "Write", "Edit"],
    "debugging":      ["--allow-tools", "Write", "Edit", "Bash"],
    "intent":         ["--allow-tools", "Write", "Edit"],
    "review-reception": ["--allow-tools", "Write", "Edit", "Bash"],
}
COMMON_FLAGS = ["--ablation", "none", "--scaffold", "--judge-model", "claude-opus-5-5",
                "--threshold", "0", "--no-publish", "--trust-plugin", "-j", "2"]

SMOKE = {
    "plan_flow": [{"tier": "comment-rules", "case": "26-cmt-neg-keep-the-why"}],
    "reviewer": ["01-swallowed-catch"],
}

ALL_REVIEWER = "*all*"
# (glob, action) pairs; every matching rule contributes and the results are unioned.
RULES = [
    ("plugins/plan-flow/skills/writing-implementation-plans/*", [("tier", "plan-writing")]),
    ("plugins/plan-flow/skills/intent/*", [("tier", "intent")]),
    ("plugins/plan-flow/skills/debugging/*", [("tier", "debugging")]),
    ("plugins/plan-flow/agents/plan-executor.md", [("tier", "plan-execution")]),
    ("plugins/plan-flow/agents/intent-reader.md", [("tier", "intent")]),
    ("plugins/plan-flow/commands/*", [("tier", "plan-command")]),
    ("plugins/plan-flow/references/working-agreements.md",
     [("tier", "comment-rules"), ("tier", "plan-command"), ("tier", "review-reception")]),
    ("plugins/plan-flow/hooks/session-start.py",
     [("tier", "comment-rules"), ("tier", "plan-command")]),
    ("plugins/plan-flow/hooks/operating-rules.md",
     [("tier", "comment-rules"), ("tier", "plan-command")]),
    ("plugins/plan-flow/hooks/comment-budget.py",
     [("tier", "comment-rules"), ("case", "plan-execution", "12-exec-comment-budget")]),
    (REVIEWER_EVALS + "/brief.md", [("reviewer", ALL_REVIEWER)]),
    (REVIEWER_EVALS + "/grade.py", [("reviewer", ALL_REVIEWER)]),
    (REVIEWER_EVALS + "/run.py", [("reviewer", ALL_REVIEWER)]),
]


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def resolve_ref(plugin, since, root):
    if since:
        if _git(root, "rev-parse", "--verify", "--quiet", since + "^{commit}").returncode != 0:
            raise ValueError(f"unknown ref {since}")
        return since
    if plugin:
        out = _git(root, "tag", "--list", f"{plugin}--v*", "--sort=-v:refname").stdout.split()
        if out:
            return out[0]
    return "HEAD~1"


def changed_files(ref, root):
    committed = _git(root, "diff", "--name-only", f"{ref}...HEAD")
    if committed.returncode != 0:
        raise ValueError(f"unknown ref {ref}")
    dirty = _git(root, "diff", "--name-only", "HEAD").stdout.split()
    return sorted(set(committed.stdout.split()) | set(dirty))


def _case_tier(root, case):
    try:
        text = (root / PF_EVALS / case / "case.yaml").read_text()
    except OSError:
        return None
    m = re.search(r"^tags:\s*\[([^\]]*)\]", text, re.M)
    if not m:
        return None
    tags = [t.strip().strip("'\"") for t in m.group(1).split(",")]
    return next((t for t in tags if t in TIER_FLAGS), None)


def _reviewer_cases(root):
    cases = {}
    for f in sorted((root / REVIEWER_EVALS / "cases").glob("*/case.json")):
        try:
            cases[f.parent.name] = json.loads(f.read_text())
        except ValueError:
            cases[f.parent.name] = {}
    return cases


def all_selection(root):
    return {
        "plan_flow": [{"tier": t, "case": None} for t in TIER_FLAGS],
        "reviewer": list(_reviewer_cases(root)),
    }


def select(changed, root):
    root = pathlib.Path(root)
    tiers, pf_cases, reviewer = set(), set(), set()
    reviewer_cases = _reviewer_cases(root)

    def add_reviewer_case(name):
        if name not in reviewer_cases:
            return
        reviewer.add(name)
        reviewer.update(n for n, c in reviewer_cases.items() if c.get("fixture_from") == name)

    for path in changed:
        for glob, actions in RULES:
            if not fnmatch.fnmatchcase(path, glob):
                continue
            for act in actions:
                if act[0] == "tier":
                    tiers.add(act[1])
                elif act[0] == "case":
                    pf_cases.add((act[1], act[2]))
                elif act[1] == ALL_REVIEWER:
                    reviewer.update(reviewer_cases)
        if fnmatch.fnmatchcase(path, "plugins/review-flow/agents/*.md"):
            agent = "review-flow:" + pathlib.PurePosixPath(path).stem
            reviewer.update(n for n, c in reviewer_cases.items() if c.get("agent") == agent)
        parts = pathlib.PurePosixPath(path).parts
        pf = pathlib.PurePosixPath(PF_EVALS).parts
        if len(parts) > len(pf) + 1 and parts[:len(pf)] == pf:
            case = parts[len(pf)]
            if re.match(r"\d", case):
                tier = _case_tier(root, case)
                if tier:
                    pf_cases.add((tier, case))
        rv = pathlib.PurePosixPath(REVIEWER_EVALS, "cases").parts
        if len(parts) > len(rv) + 1 and parts[:len(rv)] == rv:
            add_reviewer_case(parts[len(rv)])

    plan_flow = [{"tier": t, "case": None} for t in TIER_FLAGS if t in tiers]
    plan_flow += [{"tier": t, "case": c} for t, c in sorted(pf_cases) if t not in tiers]
    return {"plan_flow": plan_flow, "reviewer": sorted(reviewer)}


def pf_argv(entry):
    argv = ["--tag", entry["tier"]]
    if entry.get("case"):
        argv += ["--case", entry["case"]]
    return argv + TIER_FLAGS[entry["tier"]] + COMMON_FLAGS


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plugin")
    ap.add_argument("--since")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if args.all:
        out = {"ref": None, **all_selection(root)}
    elif args.smoke:
        out = {"ref": None, **SMOKE}
    else:
        try:
            ref = resolve_ref(args.plugin, args.since, root)
            out = {"ref": ref, **select(changed_files(ref, root), root)}
        except ValueError as e:
            print(f"eval-select: {e}", file=sys.stderr)
            return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
