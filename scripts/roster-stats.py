"""Parse review-flow handoff files into per-reviewer, per-finding counts.

Handoffs in the wild spell `found-by:` several ways (commas, semicolons, "and",
prose asides) and `files changed:` in several shapes (plain count, committed +
uncommitted). The functions here turn one handoff's text into structured rows;
a later stage aggregates them into the roster-size numbers `pr-review.md` and
`branch-review.md` rest on.
"""
import argparse
import pathlib
import re
import sys
from dataclasses import dataclass

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VERIFIERS = {"finding-gate-verifier", "fix-verifier", "anchor-resolver"}
BUCKET_ORDER = ("≤10", "11-30", ">30", "unknown")

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


def _kind(path):
    """Handoff kind from filename: `branch-*`/`pr-*` are the known shapes; anything
    else is reported as `other` rather than guessed."""
    stem = path.name[:-3] if path.name.endswith(".md") else path.name
    for kind in ("branch", "pr"):
        if stem == kind or stem.startswith(kind + "-") or stem.startswith(kind + "_"):
            return kind
    return "other"


def _collect_files(paths):
    """Expand CLI PATH arguments into handoff files. A directory yields its `*.md`
    files except deferred companions (`x-deferred.md` alongside `x.md`)."""
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(f for f in path.glob("*.md") if not f.name.endswith("-deferred.md")))
        else:
            files.append(path)
    return files


def render(handoffs):
    groups = {}
    for path, handoff in handoffs:
        groups.setdefault((_kind(path), bucket(handoff.files_changed)), []).append(handoff)

    lines = []
    for kind, buck in sorted(groups, key=lambda k: (k[0], BUCKET_ORDER.index(k[1]))):
        # name -> [dispatched, findings, sole finder, dispatch count unknown]
        agents = {}
        for handoff in groups[(kind, buck)]:
            if handoff.dispatched is not None:
                for agent in handoff.dispatched:
                    agents.setdefault(agent, [0, 0, 0, False])[0] += 1
            for finding in handoff.findings:
                if finding.dropped:
                    continue
                sole = len(finding.found_by) == 1
                for agent in finding.found_by:
                    row = agents.setdefault(agent, [0, 0, 0, False])
                    row[1] += 1
                    if sole:
                        row[2] += 1
                    if handoff.dispatched is None:
                        row[3] = True

        lines.append(f"### {kind} · {buck}")
        lines.append("")
        lines.append("| agent | dispatched | findings | sole finder | sole / dispatch |")
        lines.append("| --- | --- | --- | --- | --- |")
        for name, (dispatched, findings, sole, unknown) in sorted(
            agents.items(), key=lambda kv: (-kv[1][2], kv[0])
        ):
            dispatched_cell = "?" if unknown else str(dispatched)
            ratio_cell = "-" if unknown or dispatched == 0 else f"{sole / dispatched:.2f}"
            lines.append(f"| {name} | {dispatched_cell} | {findings} | {sole} | {ratio_cell} |")
        if any(row[3] for row in agents.values()):
            lines.append("")
            lines.append("_dispatched shown as `?` where `checks that ran` could not be parsed._")
        lines.append("")

    findings_total = dropped_total = 0
    unnormalised_lines = []
    for path, handoff in handoffs:
        for finding in handoff.findings:
            if finding.dropped:
                dropped_total += 1
            else:
                findings_total += 1
            for item in finding.unnormalised:
                unnormalised_lines.append(f"- {path}: {finding.id}: {item}")

    if unnormalised_lines:
        lines.append("## Unnormalised values")
        lines.append("")
        lines.extend(unnormalised_lines)
        lines.append("")

    lines.append("---")
    lines.append(f"handoffs: {len(handoffs)}")
    lines.append(f"findings: {findings_total}")
    lines.append(f"dropped: {dropped_total}")
    lines.append("files read:")
    for path, _ in handoffs:
        lines.append(f"- {path}")

    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aggregate review-flow handoffs into per-reviewer finding counts."
    )
    parser.add_argument("paths", metavar="PATH", nargs="+", type=pathlib.Path)
    args = parser.parse_args(argv)

    files = _collect_files(args.paths)
    if not files:
        print("no handoff files found under the given paths", file=sys.stderr)
        return 1

    handoffs = [(f, parse_handoff(f.read_text())) for f in files]
    print(render(handoffs), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
