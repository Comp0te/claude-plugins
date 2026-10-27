"""Track recurring review-finding classes and where each one landed.

The model only classifies; every count, threshold and state change is here.

Usage: recurring-findings.py {unclassified,assign,digest,decide} --records R.jsonl --ledger L.json ...
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys
import tempfile

CANDIDATE_SUBJECTS = 2
AGREEMENTS_PROJECTS = 2
AGREEMENTS_SUBJECTS = 3
REOPEN_GROWTH = 2
RUNGS = ("lint", "hook", "reviewer", "skill", "project", "agreements", "none")
CLASS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DEFAULT_AGREEMENTS = pathlib.Path(__file__).resolve().parents[1] / "plugins/plan-flow/references/working-agreements.md"
FINDING_FIELDS = ("key", "project", "subject", "severity", "title", "issue", "found_by", "file")
STATUSES = {"observing", "proposed", "accepted", "rejected", "deferred", "landed"}
SEVERITY_ORDER = ("Critical", "High", "Medium", "Low")


class LedgerError(Exception):
    pass


def load_ledger(path):
    path = pathlib.Path(path)
    if not path.exists():
        return {"version": 1, "classes": {}, "assignments": {}}
    data = json.loads(path.read_text())
    if data.get("version") != 1:
        raise LedgerError(f"unsupported ledger version: {data.get('version')!r}")
    for key, a in data.get("assignments", {}).items():
        if a.get("class") not in data.get("classes", {}):
            raise LedgerError(f"assignment {key} names undefined class {a.get('class')!r}")
    for cid, c in data.get("classes", {}).items():
        if c.get("status") not in STATUSES:
            raise LedgerError(f"class {cid} has unknown status {c.get('status')!r}")
    return data


def budget(agreements_path, limit):
    p = pathlib.Path(agreements_path)
    if not p.exists():
        return {"lines": None, "limit": limit, "over": False}
    lines = p.read_text().count("\n")
    return {"lines": lines, "limit": limit, "over": lines > limit}


def class_stats(records, ledger):
    by_key = {r["key"]: r for r in records if r.get("kind") == "finding"}
    stats = {}
    for key, a in ledger["assignments"].items():
        r = by_key.get(key)
        if r is None or r.get("verdict") == "dropped":
            continue
        s = stats.setdefault(a["class"], {"findings": 0, "subjects": set(), "projects": set(), "keys": [], "max_severity": None})
        s["findings"] += 1
        s["subjects"].add((r["project"], r["subject"]))
        s["projects"].add(r["project"])
        s["keys"].append(key)
        sev = r.get("severity")
        if sev in SEVERITY_ORDER and (s["max_severity"] is None or SEVERITY_ORDER.index(sev) < SEVERITY_ORDER.index(s["max_severity"])):
            s["max_severity"] = sev
    return {cid: {**s, "subjects": len(s["subjects"]), "projects": sorted(s["projects"]), "keys": sorted(s["keys"])}
            for cid, s in stats.items()}


def candidates(stats, ledger):
    out = []
    for cid, s in sorted(stats.items(), key=lambda kv: (-kv[1]["subjects"], kv[0])):
        c = ledger["classes"][cid]
        if s["subjects"] < CANDIDATE_SUBJECTS or c["status"] in ("accepted", "landed"):
            continue
        reopened = False
        if c["status"] == "rejected":
            if s["subjects"] < (c.get("decided_subjects") or 0) + REOPEN_GROWTH:
                continue
            reopened = True
        out.append({"class": cid, "subjects": s["subjects"], "findings": s["findings"], "projects": s["projects"],
                    "agreements_eligible": len(s["projects"]) >= AGREEMENTS_PROJECTS and s["subjects"] >= AGREEMENTS_SUBJECTS,
                    "reopened": reopened})
    return out


def demotions(records, ledger, quiet_after):
    by_key = {r["key"]: r for r in records if r.get("kind") == "finding"}
    out = []
    for cid, c in sorted(ledger["classes"].items()):
        landed = [h for h in c.get("homes", []) if h.get("landed_on")]
        if not landed:
            continue
        first = min(h["landed_on"] for h in landed)
        after = [k for k, a in ledger["assignments"].items() if a["classified_on"] > first]
        mine = [k for k in after if ledger["assignments"][k]["class"] == cid
                and by_key.get(k, {}).get("verdict") != "dropped"]
        if len(mine) >= 2:
            out.append({"class": cid, "kind": "ineffective", "home": landed[-1]})
        text_homes = [h for h in landed if h["rung"] in ("agreements", "project")]
        enforced = [h for h in landed if h["rung"] in ("lint", "hook")]
        for h in text_homes:
            if any(e["landed_on"] >= h["landed_on"] for e in enforced):
                out.append({"class": cid, "kind": "superseded", "home": h})
        subjects_after = {(by_key[k]["project"], by_key[k]["subject"]) for k in after if k in by_key}
        if not mine and len(subjects_after) >= quiet_after:
            for h in landed:
                if h["rung"] in ("agreements", "project"):
                    out.append({"class": cid, "kind": "quiet", "home": h})
    return out


def _records(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]


def _write_ledger(path, ledger):
    path = pathlib.Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True)
        raise


def _fail(message):
    print(message, file=sys.stderr)
    return 2


def cmd_unclassified(args, records, ledger):
    pending = [{k: r.get(k) for k in FINDING_FIELDS} for r in records
               if r.get("kind") == "finding" and r.get("verdict") != "dropped" and r["key"] not in ledger["assignments"]]
    classes = [{"id": cid, "name": c["name"], "description": c["description"]}
               for cid, c in sorted(ledger["classes"].items())]
    print(json.dumps({"classes": classes, "findings": pending}, indent=2, ensure_ascii=False))
    return 0


def cmd_assign(args, records, ledger):
    data = json.loads(pathlib.Path(args.input).read_text())
    keys = {r["key"] for r in records}
    new_classes = data.get("classes", {})
    assignments = data.get("assignments", {})
    for cid in new_classes:
        if not CLASS_ID_RE.match(cid):
            return _fail(f"bad class id: {cid!r}")
    for key, cid in assignments.items():
        if key not in keys:
            return _fail(f"unknown record key: {key}")
        if cid not in ledger["classes"] and cid not in new_classes:
            return _fail(f"undefined class: {cid}")
        if key in ledger["assignments"] and not args.reassign:
            return _fail(f"already assigned: {key} (use --reassign)")
    for cid, c in new_classes.items():
        ledger["classes"].setdefault(cid, {"name": c["name"], "description": c["description"], "status": "observing",
                                           "decided_on": None, "decided_subjects": None, "homes": []})
    for key, cid in assignments.items():
        prior = ledger["assignments"].get(key)
        ledger["assignments"][key] = {"class": cid, "classified_on": prior["classified_on"] if prior else args.today}
    _write_ledger(args.ledger, ledger)
    return 0


def cmd_digest(args, records, ledger):
    stats = class_stats(records, ledger)
    out = ["## Candidates", ""]
    cands = candidates(stats, ledger)
    for c in cands:
        name = ledger["classes"][c["class"]]["name"]
        eligible = "yes" if c["agreements_eligible"] else "no"
        tail = ", reopened" if c["reopened"] else ""
        out.append(f"- {c['class']} — {name}: subjects {c['subjects']}, findings {c['findings']}, "
                   f"projects {', '.join(c['projects'])}, agreements-eligible: {eligible}{tail}")
        out.extend(f"  - {k}" for k in stats[c["class"]]["keys"])
    if not cands:
        out.append("none")
    out += ["", "## Demotions", ""]
    dems = demotions(records, ledger, args.quiet_after)
    for d in dems:
        h = d["home"]
        out.append(f"- {d['class']}: {d['kind']} — {h['rung']} at {h['target']} (landed {h['landed_on']})")
    if not dems:
        out.append("none")
    b = budget(args.agreements, args.budget)
    out += ["", "## Agreements budget", ""]
    if b["lines"] is None:
        out.append(f"none (agreements file not found; limit {b['limit']})")
    else:
        out.append(f"{b['lines']} of {b['limit']} lines, {'over' if b['over'] else 'within'} budget")
    print("\n".join(out))
    return 0


def cmd_decide(args, records, ledger):
    if args.status not in STATUSES:
        return _fail(f"unknown status: {args.status}")
    if args.cls not in ledger["classes"]:
        return _fail(f"unknown class: {args.cls}")
    if args.status == "landed":
        if not (args.rung and args.target and args.text):
            return _fail("landed requires --rung, --target and --text")
        if args.rung not in RUNGS:
            return _fail(f"unknown rung: {args.rung}")
    c = ledger["classes"][args.cls]
    c["status"] = args.status
    c["decided_on"] = args.today
    c["decided_subjects"] = class_stats(records, ledger).get(args.cls, {}).get("subjects", 0)
    if args.status == "landed":
        c.setdefault("homes", []).append(
            {"rung": args.rung, "target": args.target, "text": args.text, "landed_on": args.today})
    _write_ledger(args.ledger, ledger)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, fn):
        p = sub.add_parser(name)
        p.add_argument("--records", required=True)
        p.add_argument("--ledger", required=True)
        p.set_defaults(fn=fn)
        return p

    def add_today(p):
        p.add_argument("--today", default=datetime.date.today().isoformat())

    add("unclassified", cmd_unclassified)
    p = add("assign", cmd_assign)
    p.add_argument("--input", required=True)
    p.add_argument("--reassign", action="store_true")
    add_today(p)
    p = add("digest", cmd_digest)
    p.add_argument("--agreements", default=str(DEFAULT_AGREEMENTS))
    p.add_argument("--budget", type=int, default=60)
    p.add_argument("--quiet-after", type=int, default=10)
    p = add("decide", cmd_decide)
    p.add_argument("--class", dest="cls", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--rung")
    p.add_argument("--target")
    p.add_argument("--text")
    add_today(p)

    args = parser.parse_args(argv)
    try:
        return args.fn(args, _records(args.records), load_ledger(args.ledger))
    except (LedgerError, json.JSONDecodeError, OSError, KeyError) as e:
        return _fail(f"invalid input: {e}")


if __name__ == "__main__":
    sys.exit(main())
