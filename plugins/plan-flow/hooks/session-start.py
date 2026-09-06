#!/usr/bin/env python3
"""SessionStart hook: inject the main-conversation rules and check that the memory-file
import that delivers everything else is present, resolving, and current."""
import json, os, re, subprocess, sys

RULES = ("hooks", "operating-rules.md")
SHIPPED = ("references", "working-agreements.md")
MEMORY = os.path.expanduser("~/.claude/CLAUDE.md")

def imported_path():
    """The path of the @-import that pulls in this plugin's rules, or None."""
    try:
        for line in open(MEMORY, encoding="utf-8"):
            m = re.match(r"\s*@(\S*%s)\s*$" % re.escape(SHIPPED[1]), line)
            if m:
                return os.path.expanduser(m.group(1))
    except OSError:
        pass
    return None

def integrity(root):
    line = "@<path to this plugin>/%s/%s" % SHIPPED
    path = imported_path()
    if path is None:
        return ("The rules this plugin ships are not reaching dispatched workers: "
                "~/.claude/CLAUDE.md has no import line for them. Add: %s" % line)
    if not os.path.exists(path):
        return "The rules import in ~/.claude/CLAUDE.md points at a missing file: %s" % path
    shipped = os.path.join(root, *SHIPPED)
    try:
        if open(path, encoding="utf-8").read() != open(shipped, encoding="utf-8").read():
            return ("The rules imported by ~/.claude/CLAUDE.md differ from the installed "
                    "copy (%s). One of them is stale." % shipped)
    except OSError:
        return None  # cannot compare; say nothing rather than guess
    return None

def main():
    sys.stdin.read()  # drain the event payload; nothing in it is needed
    try:
        subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       check=True, capture_output=True, timeout=5)
    except Exception:
        return 0  # not a repository: say nothing
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(__file__))
    try:
        text = open(os.path.join(root, *RULES), encoding="utf-8").read()
    except OSError:
        return 0  # a missing rules file is a silent no-op, never a broken payload
    warning = integrity(root)
    if warning:
        text += "\n\n**Setup warning.** " + warning + "\n"
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": text}}, sys.stdout)
    return 0

if __name__ == "__main__":
    sys.exit(main())
