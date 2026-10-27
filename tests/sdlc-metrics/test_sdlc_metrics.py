"""Tests for scripts/sdlc-metrics.py — one test per row of the plan's matrices."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("sdlc_metrics", ROOT / "scripts/sdlc-metrics.py")
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

NEW = """# PR review
requirement: docs/plans/a.md and docs/plans/b/plan.md

## Findings

### F1
file: src/a.ts:3
severity: Medium
scope: introduced
consequence: safety-net — nothing checks the tag
issue: text
found-by: a-agent, review-flow:b-agent
verdict: posted — https://example/1

### F2

## ROUND 2

### F3
severity: Severe
issue: """ + "x" * 900 + "\n"

OLD = """# Branch review

### F1 — Title here
- **file:line**: `a.ts:3`
- **severity**: High
- **found by**: x-agent (#1)
- **issue**: text
"""


class FindingRecordTests(unittest.TestCase):
    def rec(self, text, rel=".claude/reviews/pr-121-findings.md"):
        return {r["id"]: r for r in sm.finding_records("proj", rel, text)}

    def test_new_format(self):
        r = self.rec(NEW)["F1"]
        self.assertEqual(r["severity"], "Medium")
        self.assertEqual(r["scope"], "introduced")
        self.assertEqual(r["consequence_class"], "safety-net")
        self.assertEqual(r["found_by"], ["a-agent", "b-agent"])
        self.assertEqual(r["verdict"], "posted")
        self.assertEqual(r["issue"], "text")
        self.assertIsNone(r["title"])
        self.assertEqual(r["key"], "proj/.claude/reviews/pr-121-findings.md#F1")
        self.assertEqual(r["kind"], "finding")

    def test_old_format(self):
        r = self.rec(OLD, ".claude/reviews/branch-feat-x-0824280.md")["F1"]
        self.assertEqual(r["title"], "Title here")
        self.assertEqual(r["file"], "`a.ts:3`")
        self.assertEqual(r["severity"], "High")
        self.assertEqual(r["found_by"], ["x-agent"])
        self.assertEqual(r["issue"], "text")

    def test_missing_fields(self):
        r = self.rec(NEW)["F2"]
        for key in ("title", "file", "severity", "scope", "consequence_class", "verdict", "issue"):
            self.assertIsNone(r[key], key)
        self.assertEqual(r["found_by"], [])

    def test_round_heading(self):
        recs = self.rec(NEW)
        self.assertEqual(recs["F1"]["round"], 1)
        self.assertEqual(recs["F3"]["round"], 2)

    def test_requirement_line(self):
        self.assertEqual(self.rec(NEW)["F1"]["requirements"], ["docs/plans/a.md", "docs/plans/b/plan.md"])
        self.assertEqual(self.rec(OLD)["F1"]["requirements"], [])

    def test_requirement_variants(self):
        a = "Requirement resolved: two plans, `docs/plans/a.md`\n\n### F1\n"
        c = "- **requirement:** `docs/superpowers/plans/c.md`\n\n### F1\n"
        self.assertEqual(self.rec(a)["F1"]["requirements"], ["docs/plans/a.md"])
        self.assertEqual(self.rec(c)["F1"]["requirements"], ["docs/superpowers/plans/c.md"])

    def test_subject_from_file_name(self):
        b = self.rec(OLD, ".claude/reviews/branch-feat-x-0824280.md")["F1"]
        p = self.rec(OLD, ".claude/reviews/pr-121-findings.md")["F1"]
        o = self.rec(OLD, ".claude/reviews/deferred-work.md")["F1"]
        self.assertEqual((b["subject"], b["review"]), ("branch-feat-x", "branch"))
        self.assertEqual((p["subject"], p["review"]), ("pr-121", "pr"))
        self.assertEqual(o["review"], "other")

    def test_long_issue_truncated(self):
        self.assertEqual(len(self.rec(NEW)["F3"]["issue"]), 400)

    def test_unknown_severity_kept(self):
        self.assertEqual(self.rec(NEW)["F3"]["severity"], "Severe")


# Built line by line so this plan's own headings stay unambiguous to anything parsing it.
PLAN = "\n".join([
    "# X Implementation Plan",
    "### Task 1: a",
    "### Task 2: b",
    "## Spec Change Log",
    "<!-- Append-only. -->",
    "- 2026-10-18, Task 5: matrix row disagreed",
    "- 2026-10-19, outside the plan: resetSingleChat clears state",
    "- 2026-10-19, D1 re-decided by the author: list item instead of card",
    "- 2026-10-18, Task 7 (Ask First, resolved by the user): icon from Figma",
    "- 2026-10-20: tidy wording",
    "- 2026-10-21, Task 2: first line",
    "  continued here",
]) + "\n"


class ChangeRecordTests(unittest.TestCase):
    def recs(self, text=PLAN):
        return sm.change_records("proj", "docs/plans/x.md", text)

    def test_task_entry(self):
        r = self.recs()[0]
        self.assertEqual((r["origin"], r["task"], r["date"]), ("task", 5, "2026-10-18"))
        self.assertEqual(r["key"], "proj/docs/plans/x.md#1")
        self.assertEqual(r["kind"], "plan-change")

    def test_outside_plan(self):
        r = self.recs()[1]
        self.assertEqual((r["origin"], r["task"]), ("outside-plan", None))

    def test_author_decision(self):
        recs = self.recs()
        self.assertEqual(recs[2]["origin"], "author-decision")
        self.assertEqual((recs[3]["origin"], recs[3]["task"]), ("author-decision", 7))

    def test_unclassifiable(self):
        self.assertEqual(self.recs()[4]["origin"], "other")

    def test_no_log_section(self):
        self.assertEqual(self.recs("# Plan\n### Task 1: a\n"), [])

    def test_template_only(self):
        self.assertEqual(self.recs("## Spec Change Log\n\n<!-- Append-only. -->\n"), [])

    def test_multi_line_entry(self):
        r = self.recs()[5]
        self.assertIn("continued here", r["text"])
        self.assertEqual(len(self.recs()), 6)
        long = "## Spec Change Log\n- 2026-10-21, Task 1: " + "y" * 900 + "\n"
        self.assertEqual(len(self.recs(long)[0]["text"]), 400)

    def test_task_count(self):
        self.assertEqual(sm.plan_summary("proj", "docs/plans/x.md", PLAN)["tasks"], 2)
        self.assertEqual(sm.plan_summary("proj", "docs/plans/d.md", "# Design\n")["tasks"], 0)


if __name__ == "__main__":
    unittest.main()
