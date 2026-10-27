#!/usr/bin/env python3
"""Test-lock hook: once a test file written this session has been seen failing, an edit that
changes its existing lines asks the user first. Set PLAN_FLOW_TEST_LOCK=off to disable it."""
import difflib, fcntl, json, os, re, sys, tempfile

DEFAULT_FILES = (r"(^|/)(__tests__|tests?)/|\.(test|spec)\.[^/]+$"
                 r"|(^|/)test_[^/]+\.py$|_test\.(py|go)$")
DEFAULT_RUNNERS = (r"\b(jest|vitest|mocha|ava|pytest|unittest|rspec|phpunit"
                   r"|(go|cargo|swift|dotnet) test|xcodebuild\b.*\btest"
                   r"|(npm|pnpm|yarn|bun)( run)? test(:\S+)?)\b")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
EXIT = re.compile(r"Exit code (\d+)")


def pattern(env, default):
    try:
        return re.compile(os.environ.get(env) or default)
    except re.error:
        return re.compile(default)


def is_test_file(path):
    return bool(pattern("PLAN_FLOW_TEST_LOCK_FILES", DEFAULT_FILES).search(path))


def is_red_test_run(command, error, is_interrupt):
    """Quoted text is stripped first, so a commit message naming a runner is not a run."""
    m = EXIT.match((error or "").split("\n", 1)[0])
    if is_interrupt or not m or m.group(1) == "0":
        return False
    return bool(pattern("PLAN_FLOW_TEST_LOCK_RUNNERS", DEFAULT_RUNNERS)
                .search(QUOTED.sub("", command or "")))


def only_inserts(old, new):
    if not old:
        return False
    ops = difflib.SequenceMatcher(None, old.split("\n"), new.split("\n"), autojunk=False)
    return all(tag in ("equal", "insert") for tag, *_ in ops.get_opcodes())
