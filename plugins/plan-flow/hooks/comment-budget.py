#!/usr/bin/env python3
"""PostToolUse hook: warn when a comment block just written busts the working-agreements
budget. Set PLAN_FLOW_COMMENT_BUDGET=off to silence it without disabling the plugin's hooks."""
import json, os, re, sys

INLINE, DOC = 2, 4
HASH = {".py", ".rb", ".sh", ".bash", ".zsh", ".pl", ".r", ".tf"}
DASH = {".sql", ".lua", ".hs", ".elm"}
SLASH = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".kts",
         ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".scala", ".dart",
         ".m", ".mm", ".css", ".scss", ".less"}
# Machine-read directives: a run of them is not a paragraph.
PRAGMA = re.compile(r"(eslint|prettier|biome|oxlint|deno-lint|@ts-|ts-ignore|noqa|pylint|mypy|"
                    r"type:|istanbul|c8 |v8 |region|coding[:=]|@flow|@jsx|codegen|!|shellcheck)")


def marker(ext):
    return "#" if ext in HASH else "--" if ext in DASH else "//" if ext in SLASH else None


def written(tool, inp):
    """Only what this call added — a pre-existing block is not this edit's to answer for."""
    if tool == "Write":
        return inp.get("content", "")
    if tool == "Edit":
        return inp.get("new_string", "")
    if tool == "MultiEdit":
        return "\n".join(e.get("new_string", "") for e in inp.get("edits", []))
    return ""


def prose(line, mark):
    body = line.strip()[len(mark):].strip()
    return bool(body) and not PRAGMA.match(body)


def block_prose(line, opening=False, closing=False):
    body = line.strip()
    if closing and "*/" in body:
        body = body[:body.rindex("*/")]
    if opening:
        body = body.lstrip("/")
    return bool(body.lstrip("*").strip())


def runs(text, ext):
    """(budget, prose lines, opening line) for every own-line comment run in `text`."""
    mark, lines, i, out = marker(ext), text.splitlines(), 0, []
    while i < len(lines):
        stripped = lines[i].strip()
        if ext in SLASH and stripped.startswith("/*"):
            budget, first, n = (DOC if stripped.startswith("/**") else INLINE), stripped, 0
            closed = "*/" in stripped[2:]
            n += 1 if block_prose(stripped, opening=True, closing=closed) else 0
            if not closed:
                i += 1
                while i < len(lines) and "*/" not in lines[i]:
                    n += 1 if block_prose(lines[i]) else 0
                    i += 1
                if i < len(lines):
                    n += 1 if block_prose(lines[i], closing=True) else 0
            out.append((budget, n, first))
        elif mark and stripped.startswith(mark):
            first, n = stripped, 0
            while i < len(lines) and lines[i].strip().startswith(mark):
                n += 1 if prose(lines[i], mark) else 0
                i += 1
            out.append((INLINE, n, first))
            continue
        i += 1
    return out


def main():
    if os.environ.get("PLAN_FLOW_COMMENT_BUDGET", "").lower() in ("0", "off", "false", "no"):
        return 0
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    inp = event.get("tool_input") or {}
    path = inp.get("file_path") or ""
    ext = os.path.splitext(path)[1].lower()
    if marker(ext) is None:
        return 0
    text = written(event.get("tool_name", ""), inp)
    over = [(b, n, first) for b, n, first in runs(text, ext) if n > b]
    if not over:
        return 0
    report = ["Comment budget exceeded in %s (working agreements: %d lines inline, %d in a "
              "docstring — a ceiling, and it outranks the style of the file you are editing):"
              % (os.path.basename(path), INLINE, DOC)]
    for budget, n, first in over:
        report.append('- %d prose lines against a budget of %d, starting "%s"'
                      % (n, budget, first[:72]))
    report.append("Cut to the constraint or move the context to the ticket. Never split one "
                  "block into two. If this one is a listed exception, say so and move on.")
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": "\n".join(report)}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
