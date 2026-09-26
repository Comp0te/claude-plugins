"""Tests for scripts/roster-stats.py's parsing functions (Task 1).

One test per row of the plan's I/O & Edge-Case Matrix.
"""
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
