"""Tests for scripts/roster-stats.py's parsing (Task 1) and reporting (Task 2).

One test per row of the plan's I/O & Edge-Case Matrix.
"""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("roster_stats", ROOT / "scripts/roster-stats.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


class NormaliseAgentsTests(unittest.TestCase):
    def test_comma_list(self):
        self.assertEqual(
            rs.normalise_agents("a-agent, review-flow:b-agent"),
            (("a-agent", "b-agent"), ()),
        )

    def test_semicolons_and_parenthetical(self):
        self.assertEqual(
            rs.normalise_agents("a-agent (independently); b-agent"),
            (("a-agent", "b-agent"), ()),
        )

    def test_prose_item(self):
        self.assertEqual(
            rs.normalise_agents("a-agent, and the main loop's own confirmation"),
            (("a-agent",), ("the main loop's own confirmation",)),
        )

    def test_and_joiner(self):
        self.assertEqual(
            rs.normalise_agents("a-agent and b-agent"),
            (("a-agent", "b-agent"), ()),
        )

    def test_duplicate_name(self):
        self.assertEqual(
            rs.normalise_agents("a-agent, review-flow:a-agent"),
            (("a-agent",), ()),
        )


class ParseFilesChangedTests(unittest.TestCase):
    def test_plain_size(self):
        self.assertEqual(rs.parse_files_changed("71 (3032 insertions / 4834 deletions)"), 71)

    def test_committed_plus_uncommitted(self):
        self.assertEqual(rs.parse_files_changed("55 committed + 6 uncommitted (tree dirty)"), 61)

    def test_plus_joiner(self):
        self.assertEqual(
            rs.parse_files_changed("4 committed (a.ts, b.ts) plus 1 uncommitted (CHANGELOG.md)"), 5
        )


class BucketTests(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual(rs.bucket(10), "≤10")
        self.assertEqual(rs.bucket(11), "11-30")
        self.assertEqual(rs.bucket(30), "11-30")
        self.assertEqual(rs.bucket(31), ">30")
        self.assertEqual(rs.bucket(None), "unknown")


class ParseHandoffTests(unittest.TestCase):
    def test_bold_bullet_key(self):
        handoff = rs.parse_handoff("### F1\n- **found by**: a-agent\n")
        self.assertEqual(handoff.findings[0].found_by, ("a-agent",))

    def test_no_size_line(self):
        handoff = rs.parse_handoff("branch: x\n\n### F1\nfound-by: a-agent\n")
        self.assertIsNone(handoff.files_changed)
        self.assertEqual(rs.bucket(handoff.files_changed), "unknown")

    def test_checks_line(self):
        handoff = rs.parse_handoff(
            "checks that ran: x-agent, review-flow:y-agent (no findings), "
            "review-flow:finding-gate-verifier\n"
        )
        self.assertEqual(handoff.dispatched, ("x-agent", "y-agent"))

    def test_checks_section(self):
        handoff = rs.parse_handoff(
            "## Checks that ran\n\n"
            "x-agent, review-flow:y-agent, and something not on the roster\n\n"
            "## Findings\n"
        )
        self.assertEqual(handoff.dispatched, ("x-agent", "y-agent"))
        self.assertIn("something not on the roster", handoff.dispatched_unnormalised)

    def test_no_checks_info(self):
        handoff = rs.parse_handoff("branch: x\nfiles changed: 5\n")
        self.assertIsNone(handoff.dispatched)

    def test_dropped_finding(self):
        handoff = rs.parse_handoff("### F3\nfound-by: a-agent\nverdict: dropped — refuted\n")
        self.assertTrue(handoff.findings[0].dropped)

    def test_finding_without_found_by(self):
        handoff = rs.parse_handoff("### F4\nfile: src/a.ts:1\n")
        self.assertEqual(handoff.findings[0].found_by, ())


class RenderTests(unittest.TestCase):
    def test_per_bucket_table(self):
        small = rs.Handoff(files_changed=4, dispatched=("a-agent",), dispatched_unnormalised=(),
                            findings=())
        big = rs.Handoff(files_changed=50, dispatched=("a-agent",), dispatched_unnormalised=(),
                          findings=())
        out = rs.render([(Path("branch-x.md"), small), (Path("branch-y.md"), big)])
        self.assertIn("branch", out)
        self.assertIn("≤10", out)
        self.assertIn(">30", out)
        self.assertIn("| agent | dispatched | findings | sole finder | sole / dispatch |", out)

    def test_sole_finder(self):
        finding = rs.FindingRow(id="F1", found_by=("a-agent",), unnormalised=(), dropped=False)
        handoff = rs.Handoff(files_changed=5, dispatched=("a-agent",), dispatched_unnormalised=(),
                              findings=(finding,))
        out = rs.render([(Path("branch-x.md"), handoff)])
        self.assertIn("| a-agent | 1 | 1 | 1 | 1.00 |", out)

    def test_shared_finding(self):
        finding = rs.FindingRow(id="F1", found_by=("a-agent", "b-agent"), unnormalised=(),
                                 dropped=False)
        handoff = rs.Handoff(files_changed=5, dispatched=("a-agent", "b-agent"),
                              dispatched_unnormalised=(), findings=(finding,))
        out = rs.render([(Path("branch-x.md"), handoff)])
        self.assertIn("| a-agent | 1 | 1 | 0 | 0.00 |", out)
        self.assertIn("| b-agent | 1 | 1 | 0 | 0.00 |", out)

    def test_unknown_dispatch(self):
        finding = rs.FindingRow(id="F1", found_by=("a-agent",), unnormalised=(), dropped=False)
        handoff = rs.Handoff(files_changed=5, dispatched=None, dispatched_unnormalised=(),
                              findings=(finding,))
        out = rs.render([(Path("branch-x.md"), handoff)])
        self.assertIn("| a-agent | ? | 1 | 1 | - |", out)

    def test_dropped_excluded(self):
        finding = rs.FindingRow(id="F1", found_by=("a-agent",), unnormalised=(), dropped=True)
        handoff = rs.Handoff(files_changed=5, dispatched=None, dispatched_unnormalised=(),
                              findings=(finding,))
        out = rs.render([(Path("branch-x.md"), handoff)])
        self.assertNotIn("a-agent", out)
        self.assertIn("dropped: 1", out)

    def test_unnormalised_listed(self):
        finding = rs.FindingRow(id="F2", found_by=(), unnormalised=("the main loop's own confirmation",),
                                 dropped=False)
        handoff = rs.Handoff(files_changed=5, dispatched=None, dispatched_unnormalised=(),
                              findings=(finding,))
        path = Path("proj/branch-x.md")
        out = rs.render([(path, handoff)])
        self.assertIn("Unnormalised values", out)
        self.assertIn(f"{path}", out)
        self.assertIn("F2", out)
        self.assertIn("the main loop's own confirmation", out)

    def test_kind_from_filename(self):
        empty = rs.Handoff(files_changed=None, dispatched=None, dispatched_unnormalised=(),
                            findings=())
        out = rs.render([
            (Path("branch-x.md"), empty),
            (Path("pr-12-findings.md"), empty),
            (Path("other.md"), empty),
        ])
        self.assertIn("branch", out)
        self.assertIn("pr", out)
        self.assertIn("other", out)


class MainTests(unittest.TestCase):
    def test_directory_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.md").write_text(
                "files changed: 5\n\n### F1\nfound-by: a-agent\n"
            )
            (tmp_path / "a-deferred.md").write_text(
                "files changed: 5\n\n### F1\nfound-by: b-agent\n"
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = rs.main([str(tmp_path)])
            self.assertEqual(code, 0)
            self.assertIn("a-agent", out.getvalue())
            self.assertNotIn("b-agent", out.getvalue())
            self.assertIn("a.md", out.getvalue())
            self.assertNotIn("a-deferred.md", out.getvalue())

    def test_nothing_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = rs.main([tmp])
            self.assertEqual(code, 1)
            self.assertNotEqual(err.getvalue().strip(), "")


if __name__ == "__main__":
    unittest.main()
