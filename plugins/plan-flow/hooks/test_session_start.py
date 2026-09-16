"""Unit tests for the session-start hook.

Run: python3 -m unittest discover -s plugins/plan-flow/hooks -p 'test_*.py'
"""
import contextlib, importlib.util, io, json, os, pathlib, tempfile, unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "session_start", pathlib.Path(__file__).parent / "session-start.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

PLUGIN = pathlib.Path(__file__).resolve().parent.parent
AGREEMENTS = (PLUGIN / "references" / "working-agreements.md").read_text()


@contextlib.contextmanager
def session(memory_lines=None, root=None, in_repo=True):
    """Run the hook against a fake ~/.claude/CLAUDE.md; yields its injected text, or None."""
    with tempfile.TemporaryDirectory() as tmp:
        memory = pathlib.Path(tmp) / "CLAUDE.md"
        if memory_lines is not None:
            memory.write_text(memory_lines)
        out = io.StringIO()
        run = mock.DEFAULT if in_repo else mock.Mock(side_effect=OSError("not a repo"))
        with mock.patch.object(ss, "MEMORY", str(memory)), \
             mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(root or PLUGIN)}), \
             mock.patch("subprocess.run", run), \
             mock.patch("sys.stdin", io.StringIO("{}")), contextlib.redirect_stdout(out):
            ss.main()
        written = out.getvalue()
        yield (json.loads(written)["hookSpecificOutput"]["additionalContext"]
               if written else None)


def import_line():
    return "@" + str(PLUGIN / "references" / "working-agreements.md") + "\n"


class OutsideARepository(unittest.TestCase):
    def test_says_nothing(self):
        with session(memory_lines=import_line(), in_repo=False) as text:
            self.assertIsNone(text)


class ImportIsWorking(unittest.TestCase):
    def test_operating_rules_are_injected(self):
        with session(memory_lines=import_line()) as text:
            self.assertIn("How work gets done here", text)

    def test_no_warning(self):
        with session(memory_lines=import_line()) as text:
            self.assertNotIn("Setup warning", text)

    def test_the_agreements_are_not_injected_twice(self):
        """The import is already delivering them; repeating them is pure context cost."""
        with session(memory_lines=import_line()) as text:
            self.assertNotIn("## Code Comments", text)


class ImportIsMissing(unittest.TestCase):
    def test_warns(self):
        with session(memory_lines="# my notes\n") as text:
            self.assertIn("Setup warning", text)
            self.assertIn("no import line", text)

    def test_falls_back_to_the_agreements_verbatim(self):
        with session(memory_lines="# my notes\n") as text:
            self.assertIn(AGREEMENTS, text)

    def test_the_fallback_carries_the_comment_rule(self):
        with session(memory_lines="# my notes\n") as text:
            for clause in ("## Code Comments", "Why, not what", "Private members get nothing",
                           "No process artifacts", "Budget: 2 lines inline"):
                self.assertIn(clause, text)

    def test_the_fallback_says_it_covers_this_conversation_only(self):
        with session(memory_lines="# my notes\n") as text:
            self.assertIn("cover this conversation", text)

    def test_a_missing_memory_file_is_treated_as_a_missing_import(self):
        with session(memory_lines=None) as text:
            self.assertIn("Setup warning", text)
            self.assertIn(AGREEMENTS, text)


class ImportIsBroken(unittest.TestCase):
    def test_a_dangling_import_warns_and_falls_back(self):
        with session(memory_lines="@/nowhere/working-agreements.md\n") as text:
            self.assertIn("points at a missing file", text)
            self.assertIn(AGREEMENTS, text)

    def test_a_stale_import_warns_without_duplicating(self):
        """It is still delivering: a second, differing copy beside it is worse than old text."""
        with tempfile.TemporaryDirectory() as tmp:
            stale = pathlib.Path(tmp) / "working-agreements.md"
            stale.write_text("# Working Agreements\n\nan older copy\n")
            with session(memory_lines="@%s\n" % stale) as text:
                self.assertIn("One of them is stale", text)
                self.assertNotIn(AGREEMENTS, text)
                self.assertNotIn("Until that import is in place", text)


class MissingPluginFiles(unittest.TestCase):
    def test_absent_operating_rules_is_a_silent_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            with session(memory_lines="# my notes\n", root=tmp) as text:
                self.assertIsNone(text)

    def test_absent_agreements_still_warns_without_a_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "hooks").mkdir()
            (pathlib.Path(tmp) / "hooks" / "operating-rules.md").write_text("# rules\n")
            with session(memory_lines="# my notes\n", root=tmp) as text:
                self.assertIn("Setup warning", text)
                self.assertNotIn("Until that import is in place", text)


if __name__ == "__main__":
    unittest.main()
