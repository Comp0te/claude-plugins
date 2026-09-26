#!/usr/bin/env python3
"""Test double for the `claude` CLI, selected via `run.py --claude`.

Never talks to a model. Picks its canned `claude -p --output-format json` reply from
`FAKE_CLAUDE_MODE` (`ok-caught`, `ok-clean`, `error`, `sleep`, `unparsed`), and — when
`FAKE_CLAUDE_LOG` is set — appends one JSON line recording its argv and cwd, so a test
can confirm what `run.py` actually invoked without inspecting a live process.
"""
import json
import os
import sys
import time

CAUGHT_RESULT = (
    "### Silent failure\n"
    "src/store/notes.ts:12 — scope: introduced — the catch swallows the error silently.\n"
    "Evidence: grounded: read src/store/notes.ts\n"
    "Why it matters: errors are lost with no signal to the user.\n"
)
CLEAN_RESULT = "No silent failures found.\n"
UNPARSED_RESULT = (
    "1. Location: src/a.ts:10\n"
    "Evidence: grounded: read src/a.ts\n"
    "Why it matters: could break silently\n"
)


def log_invocation():
    log_path = os.environ.get("FAKE_CLAUDE_LOG")
    if not log_path:
        return
    record = {"argv": sys.argv[1:], "cwd": os.getcwd()}
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def main():
    log_invocation()
    mode = os.environ.get("FAKE_CLAUDE_MODE", "ok-caught")

    if mode == "sleep":
        time.sleep(5)
        mode = "ok-clean"  # only reached if the caller's --timeout did not fire

    if mode == "ok-caught":
        payload = {
            "type": "result", "subtype": "success", "is_error": False,
            "result": CAUGHT_RESULT, "total_cost_usd": 0.05,
        }
    elif mode == "ok-clean":
        payload = {
            "type": "result", "subtype": "success", "is_error": False,
            "result": CLEAN_RESULT, "total_cost_usd": 0.05,
        }
    elif mode == "unparsed":
        payload = {
            "type": "result", "subtype": "success", "is_error": False,
            "result": UNPARSED_RESULT, "total_cost_usd": 0.05,
        }
    elif mode == "error":
        payload = {
            "type": "result", "subtype": "error", "is_error": True,
            "result": "", "total_cost_usd": 0.0,
        }
    else:
        print(f"unknown FAKE_CLAUDE_MODE: {mode!r}", file=sys.stderr)
        return 2

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
