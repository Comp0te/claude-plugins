#!/usr/bin/env python3
"""Keep the working-agreements sections embedded in eval cases identical to their source.

An eval run loads neither the operator's memory files nor a workspace `CLAUDE.md`, so a case
that measures the rule has to carry it in `append_system_prompt`. That copy is the drift risk
this script exists to remove. Comment-rules cases carry Code Comments; debugging cases carry
Before Writing Code in both arms, so a with-without delta measures the skill and not that rule.

    --check   exit 1 and name every case whose copy has drifted (used by the unit tests)
    --write   rewrite each case's block from the source

    --tier rcv|tst --arm with|without  (with --check or --write) instead sync the cases of a
    working-agreements candidate to the whole agreements, with or without the candidate section.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT.parent / "references" / "working-agreements.md"
SECTION = "## Code Comments"
CASES = [("*-cmt-*", SECTION), ("*-dbg-*", "## Before Writing Code")]
PREAMBLE = "The project's working agreements include the section below. Follow it.\n\n"
FIELD = "  append_system_prompt: |\n"
INDENT = "    "
TIER_PREAMBLE = "The project's working agreements are below. Follow them.\n\n"
TIERS = {
    "rcv": {"glob": "*-rcv-*/case.yaml", "candidate": "candidates/receiving-review.md",
            "heading": "## Receiving Review", "before": "## Verifying Work"},
    "tst": {"glob": "*-tst-*/case.yaml", "candidate": "candidates/writing-tests.md",
            "heading": "## Writing Tests", "after": "## Verifying Work"},
}


def section(heading=SECTION):
    """One `## ` section of the working agreements, verbatim."""
    body = SOURCE.read_text()
    start = body.index(heading)
    rest = re.search(r"^## ", body[start + len(heading):], re.M)
    return body[start:start + len(heading) + rest.start()].rstrip() + "\n"


def _bounds(body, heading):
    """(start, end) of the `## ` section, or None when absent."""
    found = re.search(r"^" + re.escape(heading) + r"[ \t]*$", body, re.M)
    if not found:
        return None
    rest = re.search(r"^## ", body[found.end():], re.M)
    return found.start(), (found.end() + rest.start() if rest else len(body))


def strip_section(body, heading):
    bounds = _bounds(body, heading)
    return body if bounds is None else body[:bounds[0]] + body[bounds[1]:]


def insert_section(body, candidate, tier):
    """Insert the candidate before/after the anchor section; no-op when already present."""
    if _bounds(body, tier["heading"]):
        return body
    candidate = candidate.strip("\n") + "\n\n"
    if "before" in tier:
        at = _bounds(body, tier["before"])[0]
        return body[:at] + candidate + body[at:]
    at = _bounds(body, tier["after"])[1]
    head = body[:at].rstrip("\n") + "\n\n"
    return head + candidate + body[at:] if body[at:] else head + candidate.rstrip("\n") + "\n"


def agreements(tier, arm):
    body = SOURCE.read_text()
    if arm == "without":
        return strip_section(body, tier["heading"])
    return insert_section(body, (ROOT / tier["candidate"]).read_text(), tier)


def cases():
    """(case.yaml, heading) for every case that embeds a section."""
    return sorted((p, heading) for glob, heading in CASES
                  for p in ROOT.glob(glob + "/case.yaml"))


def expected(heading):
    return "".join(INDENT + line if line.strip() else "\n"
                   for line in (PREAMBLE + section(heading)).splitlines(keepends=True))


def split(text):
    """(before, current block, after) around the case's append_system_prompt block."""
    head = text.index(FIELD) + len(FIELD)
    tail = head
    for line in text[head:].splitlines(keepends=True):
        if line.strip() and not line.startswith(INDENT):
            break
        tail += len(line)
    return text[:head], text[head:tail], text[tail:]


def indented(text):
    return "".join(INDENT + line if line.strip() else "\n"
                   for line in text.splitlines(keepends=True))


def main(argv):
    tier, arm = None, None
    flags = dict(zip(argv[1:], argv[2:])) if len(argv) == 5 else {}
    if len(argv) == 5 and argv[0] in ("--check", "--write"):
        if flags.get("--tier") in TIERS and flags.get("--arm") in ("with", "without"):
            tier, arm = TIERS[flags["--tier"]], flags["--arm"]
            argv = argv[:1]
    if len(argv) != 1 or argv[0] not in ("--check", "--write"):
        print(__doc__)
        return 2
    if tier:
        text = indented(TIER_PREAMBLE + agreements(tier, arm).rstrip("\n") + "\n")
        targets = [(p, text) for p in sorted(ROOT.glob(tier["glob"]))]
    else:
        targets = [(p, expected(h)) for p, h in cases()]
    drifted = []
    for case, want in targets:
        before, have, after = split(case.read_text())
        if have == want:
            continue
        drifted.append(case)
        if argv[0] == "--write":
            case.write_text(before + want + after)
    if not drifted:
        return 0
    verb = "rewrote" if argv[0] == "--write" else "drifted from %s:" % SOURCE.name
    print("%s %d case(s): %s" % (verb, len(drifted), ", ".join(c.parent.name for c in drifted)))
    return 0 if argv[0] == "--write" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
