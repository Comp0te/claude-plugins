#!/usr/bin/env python3
"""Fail if review-flow's hunk-map.awk disagrees with its fixtures under any awk on this machine.

Every awk found is run, so CI can cover macOS's one-true-awk (`original-awk` on Debian)
alongside gawk and mawk.
"""
import pathlib, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/review-flow/scripts/hunk-map.awk"
FIXTURES = ROOT / "tests/review-flow/hunk-map"
AWKS = ["/usr/bin/awk", "original-awk", "nawk", "gawk", "mawk"]


def main():
    found = {}
    for name in AWKS:
        path = shutil.which(name)
        if path and pathlib.Path(path).resolve() not in found.values():
            found[name] = pathlib.Path(path).resolve()
    if not found:
        print("no awk found", file=sys.stderr)
        return 1

    cases = sorted(FIXTURES.glob("*.diff"))
    if not cases:
        print(f"no fixtures in {FIXTURES.relative_to(ROOT)}", file=sys.stderr)
        return 1

    problems = []
    for name, path in found.items():
        for diff in cases:
            expected = diff.with_suffix(".expected").read_text()
            run = subprocess.run(
                [str(path), "-f", str(SCRIPT)],
                stdin=diff.open(), capture_output=True, text=True,
            )
            if run.returncode != 0:
                problems.append(f"{name}: {diff.name}: exit {run.returncode}: {run.stderr.strip()}")
            elif run.stdout != expected:
                problems.append(
                    f"{name}: {diff.name}: map differs\n--- expected\n{expected}--- got\n{run.stdout}"
                )

    for p in problems:
        print(p, file=sys.stderr)
    print(f"{len(cases)} fixtures x {len(found)} awks ({', '.join(found)}): "
          f"{'FAIL' if problems else 'ok'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
