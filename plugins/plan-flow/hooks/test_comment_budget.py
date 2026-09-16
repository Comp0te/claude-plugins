"""Unit tests for the comment-budget PostToolUse hook.

Run: python3 -m unittest discover -s plugins/plan-flow/hooks -p 'test_*.py'
"""
import contextlib, importlib.util, io, json, os, pathlib, unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "comment_budget", pathlib.Path(__file__).parent / "comment-budget.py")
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)


def fire(tool, inp, env=None):
    """Run the hook over one PostToolUse event; return its report lines, or None if silent."""
    event = json.dumps({"tool_name": tool, "tool_input": inp})
    out = io.StringIO()
    with mock.patch.dict(os.environ, env or {}, clear=False), \
         mock.patch("sys.stdin", io.StringIO(event)), contextlib.redirect_stdout(out):
        cb.main()
    written = out.getvalue()
    if not written:
        return None
    return json.loads(written)["hookSpecificOutput"]["additionalContext"].splitlines()


def write(path, content):
    return fire("Write", {"file_path": path, "content": content})


class Marker(unittest.TestCase):
    def test_hash_languages(self):
        for ext in (".py", ".rb", ".sh", ".tf"):
            self.assertEqual("#", cb.marker(ext), ext)

    def test_dash_languages(self):
        for ext in (".sql", ".lua", ".hs", ".elm"):
            self.assertEqual("--", cb.marker(ext), ext)

    def test_slash_languages(self):
        for ext in (".ts", ".tsx", ".js", ".go", ".rs", ".swift", ".css", ".scss"):
            self.assertEqual("//", cb.marker(ext), ext)

    def test_unknown_extension_has_no_marker(self):
        for ext in (".md", ".json", ".yaml", ".txt", ""):
            self.assertIsNone(cb.marker(ext), ext)


class Written(unittest.TestCase):
    def test_write_uses_content(self):
        self.assertEqual("body", cb.written("Write", {"content": "body"}))

    def test_edit_uses_only_the_new_string(self):
        self.assertEqual("new", cb.written("Edit", {"old_string": "old", "new_string": "new"}))

    def test_multiedit_joins_every_new_string(self):
        edits = {"edits": [{"new_string": "a"}, {"new_string": "b"}]}
        self.assertEqual("a\nb", cb.written("MultiEdit", edits))

    def test_unknown_tool_contributes_nothing(self):
        self.assertEqual("", cb.written("Bash", {"command": "// not a file edit"}))


class InlineCeiling(unittest.TestCase):
    def test_two_lines_is_silent(self):
        self.assertIsNone(write("a.js", "// one\n// two\nconst x = 1\n"))

    def test_three_lines_is_reported(self):
        report = write("a.js", "// one\n// two\n// three\nconst x = 1\n")
        self.assertIsNotNone(report)
        self.assertIn("3 prose lines against a budget of 2", report[1])

    def test_blank_line_starts_a_second_run(self):
        """Splitting one block in two is what the rule forbids, and the hook cannot see it."""
        self.assertIsNone(write("a.js", "// one\n// two\n\n// three\n// four\nconst x = 1\n"))

    def test_runs_are_counted_per_language_marker(self):
        report = write("a.py", "# one\n# two\n# three\nx = 1\n")
        self.assertIn("3 prose lines against a budget of 2", report[1])

    def test_a_marker_the_file_does_not_use_is_not_a_comment(self):
        self.assertIsNone(write("a.py", "// one\n// two\n// three\n"))

    def test_trailing_comments_are_not_own_line_runs(self):
        self.assertIsNone(write("a.js", "const x = 1 // one\nconst y = 2 // two\nconst z = 3 // three\n"))


class DocstringCeiling(unittest.TestCase):
    def test_four_prose_lines_is_silent(self):
        self.assertIsNone(write("a.js", "/**\n * one\n * two\n * three\n * four\n */\nconst x = 1\n"))

    def test_five_prose_lines_is_reported(self):
        report = write("a.js", "/**\n * one\n * two\n * three\n * four\n * five\n */\n")
        self.assertIn("5 prose lines against a budget of 4", report[1])

    def test_prose_on_the_opening_line_counts(self):
        report = write("a.js", "/** one\n * two\n * three\n * four\n * five\n */\n")
        self.assertIn("5 prose lines against a budget of 4", report[1])

    def test_prose_on_the_closing_line_counts(self):
        report = write("a.js", "/**\n * one\n * two\n * three\n * four\n * five */\n")
        self.assertIn("5 prose lines against a budget of 4", report[1])

    def test_a_bare_block_comment_takes_the_inline_ceiling(self):
        report = write("a.js", "/*\n * one\n * two\n * three\n */\n")
        self.assertIn("3 prose lines against a budget of 2", report[1])

    def test_single_line_block_comment_is_silent(self):
        self.assertIsNone(write("a.js", "/** one */\nconst x = 1\n"))

    def test_empty_block_comment_has_no_prose(self):
        self.assertIsNone(write("a.js", "/**/\nconst x = 1\n"))

    def test_blank_continuation_lines_do_not_count(self):
        self.assertIsNone(write("a.js", "/**\n * one\n *\n * two\n *\n * three\n */\n"))


class Pragmas(unittest.TestCase):
    def test_directive_lines_are_not_prose(self):
        body = ("// eslint-disable-next-line no-console\n// @ts-expect-error\n"
                "// prettier-ignore\n// istanbul ignore next\nconst x = 1\n")
        self.assertIsNone(write("a.js", body))

    def test_a_directive_does_not_absorb_the_prose_around_it(self):
        body = "// one\n// eslint-disable-next-line\n// two\n// three\nconst x = 1\n"
        report = write("a.js", body)
        self.assertIn("3 prose lines against a budget of 2", report[1])

    def test_noqa_is_a_directive_in_hash_languages(self):
        self.assertIsNone(write("a.py", "# noqa: E501\n# type: ignore\n# pylint: disable=all\nx = 1\n"))

    def test_shebang_is_not_prose(self):
        self.assertIsNone(write("a.sh", "#!/usr/bin/env bash\n# one\n# two\nset -eu\n"))

    def test_bang_prefixed_slash_comments_are_treated_as_directives(self):
        """`!` is in the pragma table for shebangs; it also exempts Rust `//!` module docs,
        which the budget's own barrel-module exception would exempt anyway."""
        self.assertIsNone(write("a.rs", "//! one\n//! two\n//! three\n//! four\n"))


class OffSwitch(unittest.TestCase):
    def test_off_silences_an_over_budget_block(self):
        over = {"file_path": "a.js", "content": "// one\n// two\n// three\n"}
        for value in ("off", "0", "false", "no", "OFF"):
            self.assertIsNone(fire("Write", over, {"PLAN_FLOW_COMMENT_BUDGET": value}), value)

    def test_any_other_value_leaves_the_hook_on(self):
        report = fire("Write", {"file_path": "a.js", "content": "// one\n// two\n// three\n"},
                      {"PLAN_FLOW_COMMENT_BUDGET": "on"})
        self.assertIsNotNone(report)


class Reporting(unittest.TestCase):
    def test_report_names_the_file_and_both_ceilings(self):
        report = write("/repo/src/backoff.js", "// one\n// two\n// three\n")
        self.assertIn("backoff.js", report[0])
        self.assertIn("2 lines inline, 4 in a docstring", report[0])

    def test_report_quotes_the_opening_line_of_each_over_budget_run(self):
        report = write("a.js", "// first run one\n// first run two\n// first run three\n"
                               "const x = 1\n"
                               "// second run one\n// second run two\n// second run three\n")
        quoted = [line for line in report if line.startswith("- ")]
        self.assertEqual(2, len(quoted))
        self.assertIn("first run one", quoted[0])
        self.assertIn("second run one", quoted[1])

    def test_report_ends_with_the_cut_or_ticket_instruction(self):
        report = write("a.js", "// one\n// two\n// three\n")
        self.assertIn("Never split one block into two", report[-1])


class MalformedEvent(unittest.TestCase):
    def test_invalid_json_is_silent(self):
        with mock.patch("sys.stdin", io.StringIO("{not json")), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, cb.main())
        self.assertEqual("", out.getvalue())

    def test_missing_file_path_is_silent(self):
        self.assertIsNone(fire("Write", {"content": "// one\n// two\n// three\n"}))

    def test_edit_without_a_new_string_is_silent(self):
        self.assertIsNone(fire("Edit", {"file_path": "a.js", "old_string": "x"}))


if __name__ == "__main__":
    unittest.main()
