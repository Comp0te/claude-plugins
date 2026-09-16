#!/usr/bin/env python3
"""Keep the Code Comments rule embedded in the comment-rules cases identical to its source.

An eval run loads neither the operator's memory files nor a workspace `CLAUDE.md`, so a case
that measures the rule has to carry it in `append_system_prompt`. That copy is the drift risk
this script exists to remove.

    --check   exit 1 and name every case whose copy has drifted (used by the unit tests)
    --write   rewrite each case's block from the source
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT.parent / "references" / "working-agreements.md"
SECTION = "## Code Comments"
PREAMBLE = "The project's working agreements include the section below. Follow it.\n\n"
FIELD = "  append_system_prompt: |\n"
INDENT = "    "


def section():
    """The `## Code Comments` section of the working agreements, verbatim."""
    body = SOURCE.read_text()
    start = body.index(SECTION)
    rest = re.search(r"^## ", body[start + len(SECTION):], re.M)
    return body[start:start + len(SECTION) + rest.start()].rstrip() + "\n"


def cases():
    return sorted(p for p in ROOT.glob("*-cmt-*/case.yaml"))


def expected():
    return "".join(INDENT + line if line.strip() else "\n"
                   for line in (PREAMBLE + section()).splitlines(keepends=True))


def split(text):
    """(before, current block, after) around the case's append_system_prompt block."""
    head = text.index(FIELD) + len(FIELD)
    tail = head
    for line in text[head:].splitlines(keepends=True):
        if line.strip() and not line.startswith(INDENT):
            break
        tail += len(line)
    return text[:head], text[head:tail], text[tail:]


def main(argv):
    if len(argv) != 1 or argv[0] not in ("--check", "--write"):
        print(__doc__)
        return 2
    want, drifted = expected(), []
    for case in cases():
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
