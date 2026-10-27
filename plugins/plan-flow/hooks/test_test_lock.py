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
