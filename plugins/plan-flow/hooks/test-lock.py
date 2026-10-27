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


def state_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)
    folder = os.path.join(tempfile.gettempdir(), "plan-flow-test-lock")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, safe + ".json")


def update(session_id, change):
    """Apply `change(state)` under an exclusive lock; corrupt or missing state starts empty."""
    path = state_path(session_id)
    with open(path + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                raise ValueError
        except (OSError, ValueError):
            state = {}
        state.setdefault("written", []); state.setdefault("locked", []); state.setdefault("pending", {})
        result = change(state)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
        return result


REASON = ("plan-flow test lock: %s was written this session and a test run failed after "
          "that. This edit changes existing lines in it, which can make a fix pass without "
          "fixing anything. Approve only if the test itself is wrong; adding new lines is "
          "never blocked.")


def absolute(path, cwd):
    return os.path.normpath(os.path.join(cwd or os.getcwd(), path))


def inserts_only(tool, inp, path):
    if tool == "Edit":
        return not inp.get("replace_all") and only_inserts(inp.get("old_string", ""),
                                                           inp.get("new_string", ""))
    if tool == "MultiEdit":
        edits = inp.get("edits") or []
        return bool(edits) and all(not e.get("replace_all")
                                   and only_inserts(e.get("old_string", ""), e.get("new_string", ""))
                                   for e in edits)
    if tool == "Write":
        try:
            with open(path, encoding="utf-8") as f:
                return only_inserts(f.read(), inp.get("content", ""))
        except OSError:
            return False
    return False


def main():
    if os.environ.get("PLAN_FLOW_TEST_LOCK", "").lower() in ("0", "off", "false", "no"):
        return 0
    try:
        event = json.loads(sys.stdin.read() or "{}")
        sid, name = event.get("session_id"), event.get("hook_event_name")
        tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
        if not sid:
            return 0
        if name == "PostToolUseFailure" and tool == "Bash":
            if is_red_test_run(inp.get("command", ""), event.get("error", ""),
                               bool(event.get("is_interrupt"))):
                update(sid, lambda s: s.update(
                    locked=sorted(set(s["locked"]) | set(s["written"]))))
            return 0
        if not inp.get("file_path"):
            return 0
        path = absolute(inp["file_path"], event.get("cwd"))
        tid = event.get("tool_use_id")
        if name == "PostToolUse":
            def record(s):
                if s["pending"].pop(tid, None) == path and path in s["locked"]:
                    s["locked"].remove(path)
                if is_test_file(path) and path not in s["written"]:
                    s["written"].append(path)
            update(sid, record)
        elif name == "PreToolUse" and is_test_file(path):
            def check(s):
                if path not in s["locked"] or inserts_only(tool, inp, path):
                    return False
                if tid:
                    s["pending"][tid] = path
                return True
            if update(sid, check):
                json.dump({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "ask",
                    "permissionDecisionReason": REASON % os.path.basename(path)}}, sys.stdout)
        return 0
    except Exception:
        return 0  # the hook must never get in the way because of its own fault


if __name__ == "__main__":
    sys.exit(main())
