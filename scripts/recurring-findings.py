"""Track recurring review-finding classes and where each one landed.

The model only classifies; every count, threshold and state change is here.
"""
import json
import pathlib

CANDIDATE_SUBJECTS = 2
AGREEMENTS_PROJECTS = 2
AGREEMENTS_SUBJECTS = 3
REOPEN_GROWTH = 2
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
