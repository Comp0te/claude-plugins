#!/usr/bin/env python3
"""Copy shared/ block sources into every command/agent file that embeds them.

Reads shared/blocks.json (block name -> source file -> target files) and writes
each source between that block's <!-- shared:NAME --> / <!-- /shared:NAME -->
markers in every target. With --check, reports drift on stderr instead of
writing. Validation of every block runs before any write: if any problem is
found, nothing is written.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

ORPHAN_RE = re.compile(r"<!-- shared:([a-z0-9-]+) -->")


def _markers(name):
    return f"<!-- shared:{name} -->", f"<!-- /shared:{name} -->"


def sync(root: pathlib.Path, check: bool) -> list[str]:
    """Return problems; write targets only when check is False and there are none."""
    problems = []
    manifest = json.loads((root / "shared/blocks.json").read_text())

    listed = {
        (target, name)
        for name, spec in manifest.items()
        for target in spec["targets"]
    }
    for md in sorted((root / "plugins").glob("**/*.md")):
        rel = md.relative_to(root).as_posix()
        for m in ORPHAN_RE.finditer(md.read_text()):
            name = m.group(1)
            if (rel, name) not in listed:
                problems.append(f"unlisted block: {rel} [{name}]")

    pending = {}  # target path -> text with all this run's block substitutions applied

    for name, spec in manifest.items():
        source_rel = spec["source"]
        source = root / source_rel
        if not source.is_file() or not source.read_text().strip():
            problems.append(f"source missing or empty: {source_rel}")
            continue
        body = source.read_text().strip()
        begin_marker, end_marker = _markers(name)

        for target_rel in spec["targets"]:
            target = root / target_rel
            if not target.is_file():
                problems.append(f"target missing: {target_rel}")
                continue
            text = pending.get(target, None)
            if text is None:
                text = target.read_text()

            begins = [m.start() for m in re.finditer(re.escape(begin_marker), text)]
            ends = [m.start() for m in re.finditer(re.escape(end_marker), text)]
            if not begins or not ends:
                problems.append(f"markers missing: {target_rel} [{name}]")
                continue
            if len(begins) > 1 or len(ends) > 1:
                problems.append(f"markers duplicated: {target_rel} [{name}]")
                continue
            begin_start, end_start = begins[0], ends[0]
            if end_start < begin_start:
                problems.append(f"markers unbalanced: {target_rel} [{name}]")
                continue

            content_start = begin_start + len(begin_marker)
            if check:
                if text[content_start:end_start].strip() != body:
                    problems.append(f"out of sync: {target_rel} [{name}]")
                continue

            pending[target] = (
                text[:content_start] + "\n\n" + body + "\n\n" + text[end_start:]
            )

    if problems or check:
        return problems

    for target, text in pending.items():
        target.write_text(text)

    return problems


def main():
    check = "--check" in sys.argv[1:]
    problems = sync(ROOT, check)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
