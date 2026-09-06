#!/usr/bin/env python3
"""Fail if either agent's discipline block differs from the shared source."""
import pathlib, sys

BEGIN = "<!-- discipline:begin"
END = "<!-- discipline:end -->"
ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = [
    ROOT / "plugins/ui-verifier-mobile/agents/ui-verifier-mobile.md",
    ROOT / "plugins/ui-verifier-web/agents/ui-verifier-web.md",
]

def block(text):
    i = text.index(BEGIN); i = text.index("-->", i) + len("-->")
    return text[i:text.index(END)].strip()

def main():
    src = ROOT / "shared/verification-discipline.md"
    if not src.is_file() or not src.read_text().strip():
        print(f"source missing or empty: {src}", file=sys.stderr)
        return 1
    body = src.read_text().strip()
    bad = []
    for t in TARGETS:
        try:
            if block(t.read_text()) != body:
                bad.append(t)
        except (ValueError, OSError):
            bad.append(t)
    for t in bad:
        print(f"out of sync: {t.relative_to(ROOT)}", file=sys.stderr)
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
