"""Unit tests for the test-lock hook.

Run: python3 -m unittest discover -s plugins/plan-flow/hooks -p 'test_*.py'
"""
import contextlib, importlib.util, io, json, os, pathlib, tempfile, unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "test_lock", pathlib.Path(__file__).parent / "test-lock.py")
tl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tl)


class IsTestFile(unittest.TestCase):
    def test_test_files(self):
        for p in ("/r/src/a.test.ts", "/r/src/a.spec.jsx", "/r/src/__tests__/a.ts",
                  "/r/hooks/test_x.py", "/r/pkg/x_test.py", "/r/pkg/x_test.go",
                  "/r/tests/fixtures/data.json"):
            self.assertTrue(tl.is_test_file(p), p)

    def test_source_files(self):
        for p in ("/r/src/latest.ts", "/r/src/contest.py", "/r/src/testing-utils.ts"):
            self.assertFalse(tl.is_test_file(p), p)

    def test_env_override_replaces_default(self):
        with mock.patch.dict(os.environ, {"PLAN_FLOW_TEST_LOCK_FILES": r"\.check\.ts$"}):
            self.assertTrue(tl.is_test_file("/r/a.check.ts"))
            self.assertFalse(tl.is_test_file("/r/a.test.ts"))

    def test_invalid_override_falls_back(self):
        with mock.patch.dict(os.environ, {"PLAN_FLOW_TEST_LOCK_FILES": "("}):
            self.assertTrue(tl.is_test_file("/r/a.test.ts"))


class IsRedTestRun(unittest.TestCase):
    def red(self, cmd, err="Exit code 1\nFAIL", interrupt=False):
        return tl.is_red_test_run(cmd, err, interrupt)

    def test_runners_that_failed(self):
        for cmd in ("npx jest src/a.test.ts", "npm test", "pnpm run test:unit", "yarn test",
                    "python3 -m pytest -x", "python3 -m unittest discover -s hooks",
                    "cd app && npx vitest run"):
            self.assertTrue(self.red(cmd), cmd)

    def test_non_test_failures(self):
        for cmd in ("npx tsc --noEmit", "npm run lint", 'git commit -m "fix jest config"'):
            self.assertFalse(self.red(cmd, "Exit code 2"), cmd)

    def test_no_exit_code_line(self):
        self.assertFalse(self.red("npx jest", "Command timed out"))

    def test_exit_code_zero(self):
        self.assertFalse(self.red("npx jest", "Exit code 0"))

    def test_interrupted(self):
        self.assertFalse(self.red("npx jest", "Exit code 130", interrupt=True))

    def test_env_override_replaces_default(self):
        with mock.patch.dict(os.environ, {"PLAN_FLOW_TEST_LOCK_RUNNERS": r"\bmake check\b"}):
            self.assertTrue(self.red("make check"))
            self.assertFalse(self.red("npx jest"))

    def test_invalid_override_falls_back(self):
        with mock.patch.dict(os.environ, {"PLAN_FLOW_TEST_LOCK_RUNNERS": "("}):
            self.assertTrue(self.red("npx jest"))


class OnlyInserts(unittest.TestCase):
    def test_insertions(self):
        self.assertTrue(tl.only_inserts("a\nb", "a\nX\nb"))
        self.assertTrue(tl.only_inserts("it('a')", "it('a')\nit('b')"))
        self.assertTrue(tl.only_inserts("it('b')", "it('a')\nit('b')"))
        self.assertTrue(tl.only_inserts("same", "same"))

    def test_changes(self):
        self.assertFalse(tl.only_inserts("expect(x).toBe(1)", "expect(x).toBe(2)"))
        self.assertFalse(tl.only_inserts("toBe(1)", "toBe(1) || true"))
        self.assertFalse(tl.only_inserts("a\nb", "a"))
        self.assertFalse(tl.only_inserts("", "x"))


class Events(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "r")
        os.makedirs(os.path.join(self.repo, "src"))
        self.env = mock.patch.dict(os.environ, {"TMPDIR": self.tmp.name}, clear=False)
        self.env.start()
        tempfile.tempdir = None  # gettempdir() caches; make it re-read TMPDIR

    def tearDown(self):
        self.env.stop()
        tempfile.tempdir = None
        self.tmp.cleanup()

    def fire(self, event, sid="S1", **kw):
        """Run main() over one event; return the parsed stdout, or None if silent."""
        kw.setdefault("cwd", self.repo)
        payload = dict(kw, hook_event_name=event, session_id=sid)
        if sid is None:
            del payload["session_id"]
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             contextlib.redirect_stdout(out):
            self.assertEqual(0, tl.main())
        return json.loads(out.getvalue()) if out.getvalue() else None

    def write(self, rel, content, tid="w1", sid="S1"):
        path = os.path.join(self.repo, rel)
        out = self.fire("PreToolUse", sid, tool_name="Write", tool_use_id=tid,
                        tool_input={"file_path": path, "content": content})
        if out is None:
            with open(path, "w") as f:
                f.write(content)
            self.fire("PostToolUse", sid, tool_name="Write", tool_use_id=tid,
                      tool_input={"file_path": path, "content": content})
        return out

    def red(self, cmd="npx jest", sid="S1", code=1):
        self.fire("PostToolUseFailure", sid, tool_name="Bash",
                  tool_input={"command": cmd}, error="Exit code %d\nFAIL" % code)

    def edit(self, rel, old, new, tid="e1", sid="S1", **extra):
        path = rel if os.path.isabs(rel) else os.path.join(self.repo, rel)
        return self.fire("PreToolUse", sid, tool_name="Edit", tool_use_id=tid,
                         tool_input=dict({"file_path": path, "old_string": old,
                                          "new_string": new}, **extra))

    def multi(self, rel, edits, tid="m1", sid="S1"):
        path = os.path.join(self.repo, rel)
        return self.fire("PreToolUse", sid, tool_name="MultiEdit", tool_use_id=tid,
                         tool_input={"file_path": path, "edits": edits})

    def locked(self, rel="src/a.test.ts", content="expect(x).toBe(1)\n"):
        self.write(rel, content)
        self.red()

    def decision(self, out):
        return out["hookSpecificOutput"]["permissionDecision"] if out else None

    def state_files(self):
        return [os.path.join(d, f) for d, _, fs in os.walk(self.tmp.name) for f in fs
                if d != self.repo and not d.startswith(self.repo + os.sep)]

    def test_happy_path_asks(self):
        self.write("src/a.test.ts", "expect(x).toBe(1)\n")
        self.red()
        out = self.edit("src/a.test.ts", "toBe(1)", "toBe(2)")
        spec = out["hookSpecificOutput"]
        self.assertEqual("PreToolUse", spec["hookEventName"])
        self.assertEqual("ask", spec["permissionDecision"])
        self.assertEqual(
            "plan-flow test lock: a.test.ts was written this session and a test run failed "
            "after that. This edit changes existing lines in it, which can make a fix pass "
            "without fixing anything. Approve only if the test itself is wrong; adding new "
            "lines is never blocked.", spec["permissionDecisionReason"])

    def test_runner_passes(self):
        self.write("src/a.test.ts", "expect(x).toBe(1)\n")
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)"))

    def test_unknown_runner(self):
        self.write("src/a.test.ts", "expect(x).toBe(1)\n")
        self.red("make check", code=2)
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)"))

    def test_written_after_red_run(self):
        self.write("src/a.test.ts", "a\n")
        self.red()
        self.write("src/b.test.ts", "expect(x).toBe(1)\n", tid="w2")
        self.assertIsNone(self.edit("src/b.test.ts", "toBe(1)", "toBe(2)"))
        self.red()
        self.assertEqual("ask", self.decision(self.edit("src/b.test.ts", "toBe(1)", "toBe(2)")))

    def test_insertion_into_locked_file(self):
        self.locked(content="it('a')\n")
        self.assertIsNone(self.edit("src/a.test.ts", "it('a')", "it('a')\nit('b')"))

    def test_replace_all_asks(self):
        self.locked(content="it('a')\n")
        out = self.edit("src/a.test.ts", "it('a')", "it('a')\nit('b')", replace_all=True)
        self.assertEqual("ask", self.decision(out))

    def test_multiedit_mixed_asks(self):
        self.locked(content="it('a')\nx(1)\n")
        out = self.multi("src/a.test.ts", [
            {"old_string": "it('a')", "new_string": "it('a')\nit('b')"},
            {"old_string": "x(1)", "new_string": "x(2)"}])
        self.assertEqual("ask", self.decision(out))

    def test_multiedit_all_insertions_silent(self):
        self.locked(content="it('a')\nx(1)\n")
        out = self.multi("src/a.test.ts", [
            {"old_string": "it('a')", "new_string": "it('a')\nit('b')"},
            {"old_string": "x(1)", "new_string": "x(1)\nx(2)"}])
        self.assertIsNone(out)

    def test_write_over_locked_inserts_only(self):
        self.locked(content="a\nb\n")
        self.assertIsNone(self.write("src/a.test.ts", "a\nb\nc\n", tid="w2"))

    def test_write_over_locked_changes(self):
        self.locked(content="a\nb\n")
        self.assertEqual("ask", self.decision(self.write("src/a.test.ts", "a\nB\n", tid="w2")))
        self.assertEqual("ask", self.decision(self.write("src/a.test.ts", "a\n", tid="w3")))

    def test_write_to_deleted_locked_path(self):
        self.locked()
        os.remove(os.path.join(self.repo, "src/a.test.ts"))
        self.assertEqual("ask", self.decision(self.write("src/a.test.ts", "new\n", tid="w2")))

    def test_new_file_creation_recorded(self):
        self.assertIsNone(self.write("src/c.test.ts", "x\n"))
        self.red()
        self.assertEqual("ask", self.decision(self.edit("src/c.test.ts", "x", "y")))

    def test_non_test_file(self):
        self.locked()
        self.assertIsNone(self.edit("src/a.ts", "x", "y"))

    def test_relative_path(self):
        self.fire("PostToolUse", tool_name="Write", tool_use_id="w1",
                  tool_input={"file_path": "src/a.test.ts", "content": "x"})
        self.red()
        out = self.edit(os.path.join(self.repo, "src/a.test.ts"), "x", "y")
        self.assertEqual("ask", self.decision(out))

    def test_approved_ask_unlocks(self):
        self.locked()
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)", tid="T")))
        self.fire("PostToolUse", tool_name="Edit", tool_use_id="T", tool_input={
            "file_path": os.path.join(self.repo, "src/a.test.ts"),
            "old_string": "toBe(1)", "new_string": "toBe(2)"})
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(2)", "toBe(3)", tid="U"))

    def test_rejected_ask_stays_locked(self):
        self.locked()
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)", tid="T")))
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)", tid="U")))

    def test_relock_after_unlock(self):
        self.locked()
        path = os.path.join(self.repo, "src/a.test.ts")
        self.edit("src/a.test.ts", "toBe(1)", "toBe(2)", tid="T")
        self.fire("PostToolUse", tool_name="Edit", tool_use_id="T", tool_input={"file_path": path})
        self.red()
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(2)", "toBe(3)", tid="U")))

    def test_allowed_insertion_does_not_unlock(self):
        self.locked(content="it('a')\n")
        path = os.path.join(self.repo, "src/a.test.ts")
        self.assertIsNone(self.edit("src/a.test.ts", "it('a')", "it('a')\nit('b')", tid="T"))
        self.fire("PostToolUse", tool_name="Edit", tool_use_id="T", tool_input={"file_path": path})
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "it('a')", "it('z')", tid="U")))

    def test_concurrent_sessions(self):
        self.locked()
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)", sid="S2"))

    def test_missing_state_file(self):
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)"))

    def test_corrupt_state_file(self):
        self.write("src/a.test.ts", "expect(x).toBe(1)\n")
        (state,) = [f for f in self.state_files() if f.endswith("S1.json")]
        with open(state, "w") as f:
            f.write("not json")
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)"))
        self.fire("PostToolUse", tool_name="Write", tool_use_id="w9", tool_input={
            "file_path": os.path.join(self.repo, "src/a.test.ts"), "content": "x"})
        with open(state) as f:
            self.assertIsInstance(json.load(f), dict)
        self.red()
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)")))

    def test_missing_session_id(self):
        path = os.path.join(self.repo, "src/a.test.ts")
        for ev, kw in (("PostToolUse", {"tool_name": "Write", "tool_use_id": "w",
                                         "tool_input": {"file_path": path}}),
                       ("PreToolUse", {"tool_name": "Edit", "tool_use_id": "e",
                                        "tool_input": {"file_path": path, "old_string": "a",
                                                       "new_string": "b"}}),
                       ("PostToolUseFailure", {"tool_name": "Bash",
                                                "tool_input": {"command": "npx jest"},
                                                "error": "Exit code 1"})):
            self.assertIsNone(self.fire(ev, None, **kw))
        self.assertEqual([], self.state_files())

    def test_off_switch(self):
        with mock.patch.dict(os.environ, {"PLAN_FLOW_TEST_LOCK": "OFF"}):
            self.locked()
            self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)"))
        self.assertEqual([], self.state_files())

    def test_non_git_directory(self):
        plain = tempfile.mkdtemp(dir=self.tmp.name)
        path = os.path.join(plain, "a.test.ts")
        self.fire("PostToolUse", cwd=plain, tool_name="Write", tool_use_id="w",
                  tool_input={"file_path": path, "content": "x"})
        self.fire("PostToolUseFailure", cwd=plain, tool_name="Bash",
                  tool_input={"command": "npx jest"}, error="Exit code 1")
        out = self.fire("PreToolUse", cwd=plain, tool_name="Edit", tool_use_id="e",
                        tool_input={"file_path": path, "old_string": "x", "new_string": "y"})
        self.assertEqual("ask", self.decision(out))

    def test_hostile_session_id(self):
        self.write("src/a.test.ts", "x\n", sid="../../x")
        folder = os.path.realpath(os.path.join(self.tmp.name, "plan-flow-test-lock"))
        files = self.state_files()
        self.assertTrue(files)
        for f in files:
            self.assertEqual(folder, os.path.dirname(os.path.realpath(f)))

    def test_partial_line_edit_asks(self):
        self.locked()
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(1", "toBe(1\n+1")))

    def test_multiedit_partial_line_asks(self):
        self.locked(content="it('a')\nx(1)\n")
        out = self.multi("src/a.test.ts", [
            {"old_string": "it('a')", "new_string": "it('a')\nit('b')"},
            {"old_string": "x(", "new_string": "x(\n0 +"}])
        self.assertEqual("ask", self.decision(out))

    def test_symlinked_path_is_same_file(self):
        self.locked()
        os.symlink(os.path.join(self.repo, "src"), os.path.join(self.repo, "link"))
        self.assertEqual("ask", self.decision(self.edit("link/a.test.ts", "toBe(1)", "toBe(2)")))

    def test_state_is_private(self):
        self.write("src/a.test.ts", "x\n")
        folder = os.path.join(self.tmp.name, "plan-flow-test-lock")
        self.assertEqual(0o700, os.stat(folder).st_mode & 0o777)
        self.assertEqual(0o600, os.stat(os.path.join(folder, "S1.json")).st_mode & 0o777)

    def test_loose_state_folder_is_tightened(self):
        folder = os.path.join(self.tmp.name, "plan-flow-test-lock")
        os.makedirs(folder)
        os.chmod(folder, 0o755)
        self.locked()
        self.assertEqual(0o700, os.stat(folder).st_mode & 0o777)
        self.assertEqual("ask", self.decision(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)")))

    def test_symlinked_state_folder_fails_open(self):
        elsewhere = os.path.join(self.tmp.name, "elsewhere")
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(self.tmp.name, "plan-flow-test-lock"))
        self.locked()
        self.assertIsNone(self.edit("src/a.test.ts", "toBe(1)", "toBe(2)"))
        self.assertEqual([], os.listdir(elsewhere))

    def test_symlinked_state_files_are_not_followed(self):
        folder = os.path.join(self.tmp.name, "plan-flow-test-lock")
        os.makedirs(folder, mode=0o700)
        victim = os.path.join(self.tmp.name, "victim")
        with open(victim, "w") as f:
            f.write("keep")
        os.symlink(victim, os.path.join(folder, "S1.json"))
        os.symlink(victim, os.path.join(folder, "S2.json.lock"))
        self.write("src/a.test.ts", "x\n", sid="S1")
        self.write("src/b.test.ts", "x\n", sid="S2")
        with open(victim) as f:
            self.assertEqual("keep", f.read())
