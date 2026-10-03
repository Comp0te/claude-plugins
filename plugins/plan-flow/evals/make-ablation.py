#!/usr/bin/env python3
"""Generate hook-delivery variants of comment-rules cases, for a with/without ablation.

The tier's own cases carry the rule in `append_system_prompt`, which puts it in both arms and
leaves nothing for an ablation to measure. These variants strip that field, so the rule reaches
the with-arm only — through `hooks/session-start.py`'s fallback, the way it reaches an install
whose import line is missing.

Generated, not committed, because a checked-in copy of a case drifts from the case.

    python3 evals/make-ablation.py [case-name ...]     default: every comment-rules case

Then, from the plugin directory:

    claude plugin eval . --eval-dir evals-ablation --tag ablation --ablation with-without \\
      --scaffold --allow-tools Write Edit --judge-model claude-opus-5-5 --no-publish --json out.json
    python3 evals/check-run.py out.json
"""
import pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / "evals-ablation"
FIELD = "  append_system_prompt: |\n"


def strip_rule(text):
    """The case with its append_system_prompt block removed."""
    head = text.index(FIELD)
    tail = head + len(FIELD)
    for line in text[tail:].splitlines(keepends=True):
        if line.strip() and not line.startswith("    "):
            break
        tail += len(line)
    return text[:head] + text[tail:]


def main(argv):
    names = argv or [p.parent.name for p in sorted(ROOT.glob("*-cmt-*/case.yaml"))]
    if OUT.exists():
        shutil.rmtree(OUT)
    for name in names:
        case = ROOT / name
        if not (case / "case.yaml").exists():
            print("no such case: %s" % name)
            return 2
        out = OUT / name
        out.mkdir(parents=True)
        shutil.copy(case / "scaffold.sh", out / "scaffold.sh")
        text = strip_rule((case / "case.yaml").read_text())
        out.joinpath("case.yaml").write_text(text.replace("tags: [comment-rules]",
                                                          "tags: [ablation]"))
    print("wrote %d case(s) to %s" % (len(names), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
