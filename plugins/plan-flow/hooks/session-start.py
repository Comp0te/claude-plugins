#!/usr/bin/env python3
"""SessionStart hook: inject the main-conversation rules and check that the memory-file
import that delivers everything else is present, resolving, and current. When it is not, the
agreements it would have delivered are injected verbatim as a fallback."""
import json, os, re, subprocess, sys

RULES = ("hooks", "operating-rules.md")
SHIPPED = ("references", "working-agreements.md")
MEMORY = os.path.expanduser("~/.claude/CLAUDE.md")

def imported_path():
    """The path of the @-import that pulls in this plugin's rules, or None."""
    try:
        with open(MEMORY, encoding="utf-8") as memory:
            for line in memory:
                m = re.match(r"\s*@(\S*%s)\s*$" % re.escape(SHIPPED[1]), line)
                if m:
                    return os.path.expanduser(m.group(1))
    except OSError:
        pass
    return None

def integrity(root):
    """(warning, whether the import is putting the rules in front of the agent).

    A stale import still delivers them, so it warrants the warning and not the fallback —
    injecting a second, differing copy next to the one already loaded is worse than old text.
    """
    line = "@" + os.path.join(root, *SHIPPED)
    path = imported_path()
    if path is None:
        return ("The rules this plugin ships are not reaching dispatched workers: "
                "~/.claude/CLAUDE.md has no import line for them. Add: %s" % line, False)
    if not os.path.exists(path):
        return ("The rules import in ~/.claude/CLAUDE.md points at a missing file: %s" % path,
                False)
    shipped = os.path.join(root, *SHIPPED)
    try:
        with open(path, encoding="utf-8") as a, open(shipped, encoding="utf-8") as b:
            same = a.read() == b.read()
        if not same:
            return ("The rules imported by ~/.claude/CLAUDE.md differ from the installed "
                    "copy (%s). One of them is stale." % shipped, True)
    except OSError:
        return (None, True)  # cannot compare; say nothing rather than guess
    return (None, True)

def fallback(root):
    """The agreements verbatim, for a session the import is not reaching.

    Verbatim because the one attempt to paraphrase these sections into a hook's budget lost
    seven rules; this conversation is also all it covers, since a dispatched worker still
    reads them only through the import.
    """
    try:
        with open(os.path.join(root, *SHIPPED), encoding="utf-8") as shipped:
            agreements = shipped.read()
    except OSError:
        return ""
    return ("\nUntil that import is in place, they follow here, and cover this conversation "
            "only:\n\n" + agreements)


def main():
    sys.stdin.read()  # drain the event payload; nothing in it is needed
    try:
        subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       check=True, capture_output=True, timeout=5)
    except Exception:
        return 0  # not a repository: say nothing
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(__file__))
    try:
        with open(os.path.join(root, *RULES), encoding="utf-8") as rules:
            text = rules.read()
    except OSError:
        return 0  # a missing rules file is a silent no-op, never a broken payload
    warning, delivering = integrity(root)
    if warning:
        text += "\n\n**Setup warning.** " + warning + "\n"
        if not delivering:
            text += fallback(root)
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": text}}, sys.stdout)
    return 0

if __name__ == "__main__":
    sys.exit(main())
