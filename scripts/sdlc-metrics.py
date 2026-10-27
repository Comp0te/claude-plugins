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
            "file": rs.line_value(block, r"file(?::line)?"),
            "severity": rs.line_value(block, "severity") or None,
            "scope": rs.line_value(block, "scope") or None,
            "consequence_class": (CLASS_RE.match(consequence).group(1) if consequence and CLASS_RE.match(consequence) else None),
            "found_by": list(rs.normalise_agents(found_by_value)[0]) if found_by_value else [],
            "verdict": (re.match(r"[a-z-]+", verdict.lower()).group(0) if verdict and re.match(r"[a-z-]+", verdict.lower()) else None),
            "issue": issue[:ISSUE_LIMIT] if issue else None,
            "requirements": requirements,
        })
    return records
