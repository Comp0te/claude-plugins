"""Turn a reviewer agent's prose answer into countable findings, and grade a run.

Pure logic, no subprocess or network call: `run.py` does the I/O and calls in here to
grade what it collected. A finding is one `scope: introduced|pre-existing` record with the
citations and text that belong to it; a run is graded against a case's `expected` /
`allowed` points, or found invalid before grading is even attempted.
"""
import json
import re
from dataclasses import dataclass

SCOPE_RE = re.compile(r"scope\W{0,6}:\W{0,3}(introduced|pre-existing)", re.I)
UNPARSED_HINT_RE = re.compile(r"(\bevidence\W{0,6}:|why it matters)", re.I)
CITE_RE = re.compile(
    r"(?P<path>[\w./-]+\.(?:ts|tsx|js|jsx))(?::|#L)(?P<a>\d+)(?:\s*[-–]\s*L?(?P<b>\d+))?"
)
HEADING_RE = re.compile(r"^#{1,6}\s")
RULE_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
BOLD_LABEL_RE = re.compile(r"^\*\*([^*\n]+)\*\*:?\s*$")
NUM_ITEM_RE = re.compile(r"^1\.\s")
BULLET_RE = re.compile(r"^[-*]\s")

# A standalone bold line boundaries a section unless its label is a finding's own
# field (e.g. "**Issue Description**:"); a real section label ("**Cleared**") still ends the record.
KNOWN_FIELD_LABELS = {
    "location", "scope", "issue description", "hidden errors",
    "why it matters", "evidence", "recommendation", "example",
}


@dataclass(frozen=True)
class Citation:
    file: str      # relative to the fixture root, e.g. "src/store/notes.ts"
    start: int
    end: int       # == start for a single line


@dataclass(frozen=True)
class Finding:
    scope: str                     # "introduced" | "pre-existing"
    citations: tuple[Citation, ...]
    text: str                      # the finding's record text, used for keyword matching


@dataclass(frozen=True)
class RunGrade:
    caught: bool | None            # None on a variant with no expectation ("clean")
    scope_ok: bool | None          # None unless caught
    false_positives: int
    unparsed: bool
    findings: int


def _resolve_path(path, known_files):
    if path in known_files:
        return path
    for known in known_files:
        if path.endswith("/" + known):
            return known
    return None


def _extract_citations(text, known_files):
    citations = []
    seen = set()
    for m in CITE_RE.finditer(text):
        resolved = _resolve_path(m.group("path"), known_files)
        if resolved is None:
            continue
        start = int(m.group("a"))
        end = int(m.group("b")) if m.group("b") else start
        key = (resolved, start, end)
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(file=resolved, start=start, end=end))
    return tuple(citations)


def _is_block_boundary(line):
    if HEADING_RE.match(line) or RULE_RE.match(line):
        return True
    m = BOLD_LABEL_RE.match(line)
    if not m:
        return False
    return m.group(1).strip("` ").lower() not in KNOWN_FIELD_LABELS


def _split_blocks(lines):
    blocks = []
    current = []
    for line in lines:
        if _is_block_boundary(line) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _bullet_cites_known_file(line, known_files):
    if not BULLET_RE.match(line):
        return False
    return any(_resolve_path(m.group("path"), known_files) for m in CITE_RE.finditer(line))


def _segment_block(lines, known_files):
    scope_idxs = []
    scopes = []
    for i, line in enumerate(lines):
        m = SCOPE_RE.search(line)
        if m:
            scope_idxs.append(i)
            scopes.append(m.group(1).lower())
    if not scope_idxs:
        return []

    starts = [0]
    for k in range(1, len(scope_idxs)):
        prev = scope_idxs[k - 1]
        start = None
        for li in range(prev + 1, len(lines)):
            line = lines[li]
            if NUM_ITEM_RE.match(line) or _bullet_cites_known_file(line, known_files):
                start = li
                break
        starts.append(prev + 1 if start is None else start)
    starts.append(len(lines))

    findings = []
    for k in range(len(scope_idxs)):
        record_lines = lines[starts[k]:starts[k + 1]]
        record_text = "\n".join(record_lines)
        findings.append(Finding(
            scope=scopes[k],
            citations=_extract_citations(record_text, known_files),
            text=record_text,
        ))
    return findings


def parse_findings(text: str, known_files: list[str]) -> tuple[list[Finding], bool]:
    """Split an agent answer into findings; the bool is True when the answer is unparsed."""
    lines = text.splitlines()
    findings = []
    for block in _split_blocks(lines):
        findings.extend(_segment_block(block, known_files))

    if not SCOPE_RE.search(text):
        # No scope anywhere, but a hint phrase or a fixture citation means it wrote
        # finding records the parser can't score, not that it found nothing.
        if UNPARSED_HINT_RE.search(text) or _extract_citations(text, known_files):
            return [], True
        return [], False
    return findings, False


def invalid_reason(stdout: str, timed_out: bool) -> str | None:
    """Why a raw `claude -p --output-format json` result cannot be graded, or None."""
    if timed_out:
        return "timed out"
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return "stdout not JSON"
    if data.get("subtype") != "success":
        return f"subtype != success ({data.get('subtype')!r})"
    if data.get("is_error"):
        return "is_error"
    if not data.get("result"):
        return "empty result"
    if not data.get("total_cost_usd"):
        return "total_cost_usd == 0"
    return None


def _matches_point(finding, point, keywords):
    lo, hi = point["lines"][0], point["lines"][1]
    cited = any(
        c.file == point["file"] and c.start <= hi and lo <= c.end
        for c in finding.citations
    )
    if not cited:
        return False
    text_lower = finding.text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def grade_run(text: str, known_files: list[str], case: dict, variant: str) -> RunGrade:
    """Grade one valid run's answer text against case.json for "defect" or "clean"."""
    findings, unparsed = parse_findings(text, known_files)
    if unparsed:
        return RunGrade(caught=None, scope_ok=None, false_positives=0, unparsed=True, findings=0)

    expected = case["expected"]
    allowed = case.get("allowed", [])

    def hits_allowed(finding):
        return any(_matches_point(finding, a, a["keywords"]) for a in allowed)

    if variant == "defect":
        caught_findings = []
        false_positives = 0
        for f in findings:
            if any(_matches_point(f, p, expected["keywords"]) for p in expected["any_of"]):
                caught_findings.append(f)
            elif not hits_allowed(f):
                false_positives += 1
        caught = bool(caught_findings)
        scope_ok = any(f.scope == expected["scope"] for f in caught_findings) if caught else None
        return RunGrade(
            caught=caught, scope_ok=scope_ok, false_positives=false_positives,
            unparsed=False, findings=len(findings),
        )

    # clean: no expectation to catch, only false positives to count.
    false_positives = sum(1 for f in findings if not hits_allowed(f))
    return RunGrade(
        caught=None, scope_ok=None, false_positives=false_positives,
        unparsed=False, findings=len(findings),
    )
