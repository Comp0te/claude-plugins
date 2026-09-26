"""Parse review-flow handoff files into per-reviewer, per-finding counts.

Handoffs in the wild spell `found-by:` several ways (commas, semicolons, "and",
prose asides) and `files changed:` in several shapes (plain count, committed +
uncommitted). The functions here turn one handoff's text into structured rows;
a later stage aggregates them into the roster-size numbers `pr-review.md` and
`branch-review.md` rest on.
"""
import re
from dataclasses import dataclass

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VERIFIERS = {"finding-gate-verifier", "fix-verifier", "anchor-resolver"}

FINDING_HEADING_RE = re.compile(r"^###\s*(F\d+)\b", re.IGNORECASE | re.MULTILINE)
NEXT_HEADING_RE = re.compile(r"^#{2,3}\s", re.MULTILINE)
CHECKS_SECTION_HEADING_RE = re.compile(r"^#{1,6}\s*checks that ran\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class FindingRow:
    id: str                          # "F3"
    found_by: tuple[str, ...]        # normalised agent names, first-seen order, deduplicated
    unnormalised: tuple[str, ...]    # items that did not normalise to an agent name
    dropped: bool


@dataclass(frozen=True)
class Handoff:
    files_changed: int | None
    dispatched: tuple[str, ...] | None
    dispatched_unnormalised: tuple[str, ...]
    findings: tuple[FindingRow, ...]


def _strip_parens(s):
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\([^()]*\)", "", s)
    return s


def normalise_agents(value):
    agents, other = [], []
    for item in re.split(r"[;,]|\band\b", _strip_parens(value)):
        item = item.strip().strip("`*").strip()
        if not item:
            continue
        name = item.split(":", 1)[1] if item.startswith("review-flow:") else item
        if NAME_RE.match(name):
            if name not in agents:
                agents.append(name)
        else:
            other.append(item)
    return tuple(agents), tuple(other)


def parse_files_changed(value):
    parts = re.findall(r"(\d+)\s+(?:un)?committed", value)
    if parts:
        return sum(int(p) for p in parts)
    m = re.match(r"\s*(\d+)", value)
    return int(m.group(1)) if m else None


def bucket(files_changed):
    if files_changed is None:
        return "unknown"
    if files_changed <= 10:
        return "≤10"
    if files_changed <= 30:
        return "11-30"
    return ">30"


def _line_value(text, key_pattern):
    """First `key: value` line matching `key_pattern` (a regex fragment, not a
    literal), tolerating a leading list bullet and bold markers around the key."""
    pattern = re.compile(rf"^[-*\s]*\**{key_pattern}\**\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _checks_section_paragraph(text):
    m = CHECKS_SECTION_HEADING_RE.search(text)
    if not m:
        return None
    lines = []
    for line in text[m.end():].splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("#"):
            break
        lines.append(stripped)
    return " ".join(lines) if lines else None


def _dispatched(text):
    value = _line_value(text, re.escape("checks that ran"))
    if value is None:
        value = _checks_section_paragraph(text)
    if value is None:
        return None, ()
    agents, other = normalise_agents(value)
    return tuple(a for a in agents if a not in VERIFIERS), other


def _findings(text):
    rows = []
    for m in FINDING_HEADING_RE.finditer(text):
        next_heading = NEXT_HEADING_RE.search(text, m.end())
        block = text[m.end():next_heading.start() if next_heading else len(text)]

        found_by_value = _line_value(block, "found[- ]by")
        found_by, unnormalised = normalise_agents(found_by_value) if found_by_value is not None else ((), ())

        verdict_value = _line_value(block, "verdict")
        dropped = verdict_value is not None and verdict_value.strip().lower().startswith("dropped")

        rows.append(FindingRow(id=m.group(1), found_by=found_by, unnormalised=unnormalised, dropped=dropped))
    return tuple(rows)


def parse_handoff(text):
    files_changed_value = _line_value(text, re.escape("files changed"))
    files_changed = parse_files_changed(files_changed_value) if files_changed_value is not None else None
    dispatched, dispatched_unnormalised = _dispatched(text)
    return Handoff(
        files_changed=files_changed,
        dispatched=dispatched,
        dispatched_unnormalised=dispatched_unnormalised,
        findings=_findings(text),
    )
