"""Roll up plan execution and review rounds across project checkouts.

Usage: python3 scripts/sdlc-metrics.py [--records OUT.jsonl] ROOT [ROOT ...]
Each ROOT is a project checkout; its .claude/reviews/ handoffs and docs/plans/,
docs/superpowers/plans/ files are read. Nothing is written except OUT.jsonl.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

_spec = importlib.util.spec_from_file_location(
    "roster_stats", pathlib.Path(__file__).with_name("roster-stats.py"))
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

ISSUE_LIMIT = 400
ROUND_RE = re.compile(r"^##\s*ROUND\s+(\d+)\b", re.IGNORECASE | re.MULTILINE)
TITLE_RE = re.compile(r"^###\s*F\d+\s*[—-]\s*(.+)$", re.MULTILINE)
PATH_TITLE_RE = re.compile(r"^`([^`\s]*[/.][^`\s]*)`$")
DOC_PATH_RE = re.compile(r"docs/[^\s`,;)]+\.md")
SUBJECT_SHA_RE = re.compile(r"-(?:findings|[0-9a-f]{7,40})$")
CLASS_RE = re.compile(r"^([a-z][a-z-]*)\s+—")


def _subject(rel_path):
    stem = pathlib.PurePosixPath(rel_path).stem
    return SUBJECT_SHA_RE.sub("", stem)


REQUIREMENT_RE = re.compile(r"^[-*\s]*\**requirement(?:\s+resolved)?\**\s*:\s*\**\s*(.*)$",
                            re.IGNORECASE | re.MULTILINE)


def _requirements(text):
    first = rs.FINDING_HEADING_RE.search(text)
    m = REQUIREMENT_RE.search(text[:first.start()] if first else text)
    return DOC_PATH_RE.findall(m.group(1)) if m else []


def finding_records(project, rel_path, text):
    requirements = _requirements(text)
    rounds = [(m.start(), int(m.group(1))) for m in ROUND_RE.finditer(text)]
    review = rs._kind(pathlib.Path(rel_path))
    records = []
    for m in rs.FINDING_HEADING_RE.finditer(text):
        nxt = rs.NEXT_HEADING_RE.search(text, m.end())
        block = text[m.end():nxt.start() if nxt else len(text)]
        heading_line = text[m.start():text.find("\n", m.start()) if "\n" in text[m.start():] else len(text)]
        title = TITLE_RE.match(heading_line)
        found_by_value = rs.line_value(block, "found[- ]by")
        consequence = rs.line_value(block, "consequence")
        verdict = rs.line_value(block, "verdict")
        issue = rs.line_value(block, "issue")
        file_value = rs.line_value(block, r"file(?::line)?")
        if file_value is None and title:
            path_only = PATH_TITLE_RE.match(title.group(1).strip())
            file_value = path_only.group(1) if path_only else None
        records.append({
            "kind": "finding",
            "key": f"{project}/{rel_path}#{m.group(1)}",
            "project": project,
            "handoff": rel_path,
            "review": review,
            "subject": _subject(rel_path),
            "round": max([n for pos, n in rounds if pos < m.start()], default=1),
            "id": m.group(1),
            "title": title.group(1).strip() if title else None,
            "file": file_value,
            "severity": rs.line_value(block, "severity") or None,
            "scope": rs.line_value(block, "scope") or None,
            "consequence_class": (CLASS_RE.match(consequence).group(1) if consequence and CLASS_RE.match(consequence) else None),
            "found_by": list(rs.normalise_agents(found_by_value)[0]) if found_by_value else [],
            "verdict": (re.match(r"[a-z-]+", verdict.lower()).group(0) if verdict and re.match(r"[a-z-]+", verdict.lower()) else None),
            "issue": issue[:ISSUE_LIMIT] if issue else None,
            "requirements": requirements,
        })
    return records


TASK_HEADING_RE = re.compile(r"^###\s*Task\s+\d+\b", re.MULTILINE)
LOG_HEADING_RE = re.compile(r"^##\s*Spec Change Log\s*$", re.MULTILINE)
ENTRY_RE = re.compile(r"^-\s+(?:(\d{4}-\d{2}-\d{2})[,:]?\s*)?(.*)$")
LEAD_TASK_RE = re.compile(r"\bTasks?\s+(\d+)\b")
AUTHOR_RE = re.compile(
    r"\b(author|user)\b.*\b(decid|re-decid|resolved)"
    r"|\b(decid|re-decid|resolved)\w*\b.*\b(author|user)\b|^author decision"
    r"|\bauthor\b.*\b(approv|accept|ruling|direct|amend)"
    r"|\b(approv|accept|ruling|amend|decision)\w*\b.*\bauthor\b",
    re.IGNORECASE)


DATED_ITEM_RE = re.compile(r"^-\s+\d{4}-\d{2}-\d{2}\b")
SUBSECTION_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s*[—–-]+\s*(.*)$")


def _entries(text):
    """Log entries in file order as [date, lead-source, text] lists."""
    m = LOG_HEADING_RE.search(text)
    if not m:
        return []
    entries = []
    current = None
    in_sub = False
    for line in text[m.end():].splitlines():
        if re.match(r"^#{1,2}\s", line):
            break
        sub = SUBSECTION_RE.match(line)
        if sub:
            current = [sub.group(1), sub.group(2), sub.group(2)]
            in_sub = True
            entries.append(current)
        elif line.startswith("###"):
            current = None
        elif line.startswith("- ") and (current is None or not in_sub or DATED_ITEM_RE.match(line)):
            in_sub = False
            em = ENTRY_RE.match(line)
            current = [em.group(1), em.group(2), em.group(2)]
            entries.append(current)
        elif current and line.strip() and not line.lstrip().startswith("<!--"):
            current[2] += " " + line.strip()
    return entries


def change_records(project, rel_path, text):
    records = []
    for n, (date, head, body) in enumerate(_entries(text), 1):
        lead = head.split(":", 1)[0]
        task = LEAD_TASK_RE.search(lead)
        if AUTHOR_RE.search(lead):
            origin = "author-decision"
        elif "outside the plan" in lead.lower():
            origin = "outside-plan"
        elif task:
            origin = "task"
        else:
            origin = "other"
        records.append({
            "kind": "plan-change", "key": f"{project}/{rel_path}#{n}", "project": project,
            "plan": rel_path, "date": date, "task": int(task.group(1)) if task else None,
            "origin": origin, "text": body[:ISSUE_LIMIT],
        })
    return records


def plan_summary(project, rel_path, text):
    return {"project": project, "plan": rel_path,
            "tasks": len(TASK_HEADING_RE.findall(text)),
            "changes": change_records(project, rel_path, text)}


HANDOFF_SKIP_RE = re.compile(r"-(?:deferred|archive|fix-prompt)\.md$")
PLAN_DIRS = ("docs/plans", "docs/superpowers/plans")
ROUND_LINE_RE = re.compile(r"^\s*-\s*round\s+(\d+)\s+@", re.MULTILINE)


def project_identity(root):
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True).stdout.strip()
        return pathlib.Path(out).parent.name
    except (OSError, subprocess.CalledProcessError):
        return pathlib.Path(root).resolve().name


def _handoffs(root):
    d = root / ".claude/reviews"
    return sorted(f for f in d.glob("*.md") if not HANDOFF_SKIP_RE.search(f.name)) if d.is_dir() else []


def _plans(root):
    files = []
    for rel in PLAN_DIRS:
        d = root / rel
        if d.is_dir():
            files += [f for f in d.rglob("*.md") if "references" not in f.relative_to(d).parts]
    return sorted(files)


def collect(roots):
    seen, findings, plans, rounds = set(), [], [], {}
    reviews = 0
    for root in roots:
        root = pathlib.Path(root)
        project = project_identity(root)
        for f in _handoffs(root):
            text = f.read_text(errors="replace")
            rel = f.relative_to(root).as_posix()
            digest = (project, rel, hashlib.sha256(text.encode()).hexdigest())
            if digest in seen:
                continue
            seen.add(digest)
            findings += finding_records(project, rel, text)
            reviews += 1
            subject = _subject(rel)
            lines = len(ROUND_LINE_RE.findall(text))
            rounds[subject] = max(lines, 1) if rs._kind(f) == "pr" else rounds.get(subject, 0) + 1
        for f in _plans(root):
            text = f.read_text(errors="replace")
            digest = (project, hashlib.sha256(text.encode()).hexdigest())
            if digest in seen:
                continue
            seen.add(digest)
            plans.append(plan_summary(project, f.relative_to(root).as_posix(), text))
    for plan in plans:
        linked = [r for r in findings if r["project"] == plan["project"] and plan["plan"] in r["requirements"]]
        plan["linked_findings"] = sum(1 for r in linked if r["verdict"] != "dropped" and r["scope"] == "introduced")
        plan["executed"] = bool(linked) or bool(plan["changes"])
        plan["linked"] = bool(linked)
    return {"findings": findings, "plans": plans, "rounds": rounds, "reviews": reviews}


def _plan_row(plan):
    task_entries = [c for c in plan["changes"] if c["origin"] == "task"]
    first_pass = plan["tasks"] - len({c["task"] for c in task_entries if c["task"] is not None})
    return {
        "first_pass": max(first_pass, 0),
        "task": len(task_entries),
        "outside": sum(1 for c in plan["changes"] if c["origin"] == "outside-plan"),
        "author": sum(1 for c in plan["changes"] if c["origin"] == "author-decision"),
        "other": sum(1 for c in plan["changes"] if c["origin"] == "other"),
    }


def _median(values):
    values = sorted(values)
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def _render_plans(plans):
    lines = ["## Plan execution"]
    executed = [p for p in plans if p["executed"] and p["tasks"]]
    idle = [p for p in plans if not p["executed"]]
    if not executed:
        lines += ["leading: no data: no executed plan with tasks",
                  "lagging: no data: no executed plan with a linked review"]
    else:
        rows = [(p, _plan_row(p)) for p in executed]
        done = sum(r["first_pass"] for _, r in rows)
        total = sum(p["tasks"] for p, _ in rows)
        sums = {k: sum(r[k] for _, r in rows) for k in ("task", "outside", "author", "other")}
        lines.append(
            f"leading: first-pass tasks: {done}/{total} across {len(rows)} executed plans "
            f"({round(100 * done / total)}%) · plan-change entries by origin: task {sums['task']}, "
            f"outside-plan {sums['outside']}, author-decision {sums['author']}, other {sums['other']}")
        linked = [p for p in executed if p["linked"]]
        if linked:
            worst = max(linked, key=lambda p: p["linked_findings"])
            lines.append(
                "lagging: introduced findings that reached review per executed plan with a linked review: "
                f"{_median([p['linked_findings'] for p in linked]):g}, max {worst['linked_findings']} ({worst['plan']})")
        else:
            lines.append("lagging: no data: no executed plan has a linked review")
        lines += ["", "| project | plan | tasks | first-pass | task entries | outside-plan | author-decision | linked findings |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for p, r in sorted(rows, key=lambda x: (x[0]["project"], x[0]["plan"])):
            link = p["linked_findings"] if p["linked"] else "no linked review"
            lines.append(f"| {p['project']} | {p['plan']} | {p['tasks']} | {r['first_pass']}/{p['tasks']} | "
                         f"{r['task']} | {r['outside']} | {r['author']} | {link} |")
    lines.append("")
    if idle:
        lines.append(f"no execution evidence: {len(idle)} plans — " + ", ".join(
            f"{p['project']}/{p['plan']}" for p in sorted(idle, key=lambda p: (p["project"], p["plan"]))))
    else:
        lines.append("no execution evidence: 0 plans")
    return lines


def _render_loop(collected):
    findings, rounds = collected["findings"], collected["rounds"]
    lines = ["## Review loop"]
    if not collected["reviews"]:
        lines += ["leading: no data: no handoffs found", "lagging: no data: no handoff has a re-check round"]
        return lines
    sev = {"Critical": 0, "High": 0, "Medium": 0, "other": 0}
    for r in findings:
        sev[r["severity"] if r["severity"] in sev else "other"] += 1
    dropped = sum(1 for r in findings if r["verdict"] == "dropped")
    lines.append(f"leading: findings per review by severity: Critical {sev['Critical']}, High {sev['High']}, "
                 f"Medium {sev['Medium']}, other/none {sev['other']} over {collected['reviews']} reviews · dropped {dropped}")
    again = {s: n for s, n in rounds.items() if n >= 2}
    if again:
        worst = max(again, key=lambda s: (again[s], s))
        lines.append(f"lagging: rounds to clean: {len(again)}/{len(rounds)} · max {again[worst]} ({worst}); "
                     "re-reviewed: " + ", ".join(sorted(again)))
    else:
        lines.append("lagging: no data: no handoff has a re-check round")
    return lines


def _render_signals(findings):
    lines = ["## Recurring signals (coarse, no semantic grouping)"]
    classes = {}
    for r in findings:
        if r["consequence_class"]:
            classes[r["consequence_class"]] = classes.get(r["consequence_class"], 0) + 1
    if classes:
        lines.append("leading: findings by consequence class: " + ", ".join(
            f"{c} {n}" for c, n in sorted(classes.items(), key=lambda x: (-x[1], x[0]))))
    else:
        lines.append("leading: no data: no handoff records a consequence class")
    agents = {}
    for r in findings:
        for a in r["found_by"]:
            entry = agents.setdefault(a, [set(), 0])
            entry[0].add(r["project"])
            entry[1] += 1
    multi = sorted(((a, len(p), n) for a, (p, n) in agents.items() if len(p) >= 2), key=lambda x: (-x[1], -x[2], x[0]))
    if multi:
        lines.append("lagging: reviewer agents finding issues in ≥2 projects: " + ", ".join(
            f"{a} {p}/{n}" for a, p, n in multi))
    else:
        lines.append("lagging: no data: no reviewer agent found issues in ≥2 projects")
    return lines


def render(collected):
    sections = [_render_plans(collected["plans"]), _render_loop(collected), _render_signals(collected["findings"])]
    return "\n\n".join("\n".join(s) for s in sections) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Roll up plan execution and review rounds across checkouts.")
    parser.add_argument("--records", type=pathlib.Path, help="write finding and plan-change records as JSONL")
    parser.add_argument("roots", metavar="ROOT", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)
    collected = collect(args.roots)
    if args.records:
        rows = collected["findings"] + [c for p in collected["plans"] for c in p["changes"]]
        try:
            args.records.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                            for r in sorted(rows, key=lambda r: r["key"])))
        except OSError as e:
            print(f"cannot write records: {e}", file=sys.stderr)
            return 2
    print(render(collected), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
