#!/usr/bin/env python3
"""Copy shared/verification-discipline.md into each agent's marked block."""
import pathlib, sys

BEGIN = "<!-- discipline:begin"
END = "<!-- discipline:end -->"
ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = [
    ROOT / "plugins/ui-verifier-mobile/agents/ui-verifier.md",
    ROOT / "plugins/ui-verifier-web/agents/ui-verifier.md",
]

def main():
    src = ROOT / "shared/verification-discipline.md"
    if not src.is_file() or not src.read_text().strip():
        print(f"source missing or empty: {src}", file=sys.stderr)
        return 1
    body = src.read_text().rstrip("\n")
    for target in TARGETS:
        if not target.is_file():
            print(f"target missing: {target}", file=sys.stderr)
            return 1
        text = target.read_text()
        try:
            i = text.index(BEGIN)
            i = text.index("-->", i) + len("-->")
            j = text.index(END)
        except ValueError:
            print(f"markers missing or unbalanced: {target}", file=sys.stderr)
            return 1
        target.write_text(text[:i] + "\n\n" + body + "\n\n" + text[j:])
        print(f"synced {target.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
