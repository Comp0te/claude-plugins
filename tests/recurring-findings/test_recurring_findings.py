"""Tests for scripts/recurring-findings.py — one test per matrix row."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("recurring_findings", ROOT / "scripts/recurring-findings.py")
rf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rf)


def rec(key, subject, project="p1", verdict="fixed"):
    return {"kind": "finding", "key": key, "project": project, "subject": subject, "verdict": verdict,
            "severity": "Medium", "title": None, "issue": "x", "found_by": [], "file": None}


def ledger(classes, assignments):
    return {"version": 1,
            "classes": {k: {"name": k, "description": k, "status": "observing", "decided_on": None,
                            "decided_subjects": None, "homes": [], **v} for k, v in classes.items()},
            "assignments": {k: {"class": c, "classified_on": d} for k, (c, d) in assignments.items()}}


class CandidateTests(unittest.TestCase):
    def cands(self, records, led):
        return {c["class"]: c for c in rf.candidates(rf.class_stats(records, led), led)}

    def test_candidate(self):
        rs = [rec("k1", "s1"), rec("k2", "s1"), rec("k3", "s2")]
        led = ledger({"a": {}}, {"k1": ("a", "2026-10-25"), "k2": ("a", "2026-10-25"), "k3": ("a", "2026-10-25")})
        c = self.cands(rs, led)["a"]
        self.assertEqual((c["subjects"], c["findings"]), (2, 3))

    def test_below_threshold(self):
        rs = [rec("k1", "s1"), rec("k2", "s1")]
        led = ledger({"b": {}}, {"k1": ("b", "2026-10-25"), "k2": ("b", "2026-10-25")})
        self.assertNotIn("b", self.cands(rs, led))

    def test_dropped_findings(self):
        rs = [rec("k1", "s1"), rec("k2", "s2", verdict="dropped")]
        led = ledger({"c": {}}, {"k1": ("c", "2026-10-25"), "k2": ("c", "2026-10-25")})
        self.assertNotIn("c", self.cands(rs, led))
        self.assertEqual(rf.class_stats(rs, led)["c"]["subjects"], 1)

    def test_rereview_is_one_subject(self):
        rs = [rec("p1/.claude/reviews/branch-x-aaa1111.md#F1", "branch-x"),
              rec("p1/.claude/reviews/branch-x-bbb2222.md#F1", "branch-x")]
        led = ledger({"a": {}}, {r["key"]: ("a", "2026-10-25") for r in rs})
        self.assertEqual(rf.class_stats(rs, led)["a"]["subjects"], 1)

    def test_rejected_stays_rejected(self):
        rs = [rec(f"k{i}", f"s{i}") for i in range(3)]
        led = ledger({"d": {"status": "rejected", "decided_subjects": 2}}, {r["key"]: ("d", "2026-10-25") for r in rs})
        self.assertNotIn("d", self.cands(rs, led))

    def test_rejected_regrows(self):
        rs = [rec(f"k{i}", f"s{i}") for i in range(4)]
        led = ledger({"d": {"status": "rejected", "decided_subjects": 2}}, {r["key"]: ("d", "2026-10-25") for r in rs})
        self.assertTrue(self.cands(rs, led)["d"]["reopened"])

    def test_accepted_and_landed_not_reproposed(self):
        rs = [rec(f"k{i}", f"s{i}") for i in range(4)]
        for status in ("accepted", "landed"):
            led = ledger({"e": {"status": status}}, {r["key"]: ("e", "2026-10-25") for r in rs})
            self.assertNotIn("e", self.cands(rs, led), status)

    def test_agreements_eligibility(self):
        rs = [rec("k1", "s1", "p1"), rec("k2", "s2", "p2"), rec("k3", "s3", "p2")]
        led = ledger({"a": {}}, {r["key"]: ("a", "2026-10-25") for r in rs})
        self.assertTrue(self.cands(rs, led)["a"]["agreements_eligible"])
        two = rs[:2]
        led2 = ledger({"a": {}}, {r["key"]: ("a", "2026-10-25") for r in two})
        self.assertFalse(self.cands(two, led2)["a"]["agreements_eligible"])
        one_project = [rec(f"k{i}", f"s{i}", "p1") for i in range(3)]
        led3 = ledger({"a": {}}, {r["key"]: ("a", "2026-10-25") for r in one_project})
        self.assertFalse(self.cands(one_project, led3)["a"]["agreements_eligible"])


class DemotionTests(unittest.TestCase):
    def kinds(self, records, led, quiet_after=10):
        return {(d["class"], d["kind"]) for d in rf.demotions(records, led, quiet_after)}

    def test_ineffective(self):
        rs = [rec("k1", "s1"), rec("k2", "s2")]
        home = {"rung": "reviewer", "target": "t", "text": "x", "landed_on": "2026-10-01"}
        led = ledger({"a": {"status": "landed", "homes": [home]}},
                     {"k1": ("a", "2026-10-05"), "k2": ("a", "2026-10-06")})
        self.assertIn(("a", "ineffective"), self.kinds(rs, led))

    def test_superseded(self):
        homes = [{"rung": "agreements", "target": "wa.md", "text": "rule", "landed_on": "2026-10-01"},
                 {"rung": "lint", "target": "eslint", "text": "no-empty", "landed_on": "2026-10-10"}]
        led = ledger({"a": {"status": "landed", "homes": homes}}, {})
        found = [d for d in rf.demotions([], led, 10) if d["kind"] == "superseded"]
        self.assertEqual(found[0]["home"]["text"], "rule")

    def test_quiet(self):
        others = [rec(f"o{i}", f"s{i}") for i in range(10)]
        agreements = {"rung": "agreements", "target": "wa.md", "text": "rule", "landed_on": "2026-10-01"}
        led = ledger({"a": {"status": "landed", "homes": [agreements]}, "z": {}},
                     {r["key"]: ("z", "2026-10-05") for r in others})
        self.assertIn(("a", "quiet"), self.kinds(others, led, 10))
        lint = {"rung": "lint", "target": "eslint", "text": "x", "landed_on": "2026-10-01"}
        led["classes"]["a"]["homes"] = [lint]
        self.assertNotIn(("a", "quiet"), self.kinds(others, led, 10))


class LedgerAndBudgetTests(unittest.TestCase):
    def test_budget(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "wa.md"
            p.write_text("x\n" * 62)
            self.assertEqual(rf.budget(p, 60), {"lines": 62, "limit": 60, "over": True})
            self.assertEqual(rf.budget(Path(t) / "missing.md", 60), {"lines": None, "limit": 60, "over": False})

    def test_bad_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "l.json"
            p.write_text(json.dumps({"version": 2, "classes": {}, "assignments": {}}))
            with self.assertRaises(rf.LedgerError):
                rf.load_ledger(p)
            p.write_text(json.dumps({"version": 1, "classes": {},
                                     "assignments": {"k": {"class": "ghost", "classified_on": "2026-10-25"}}}))
            with self.assertRaisesRegex(rf.LedgerError, "ghost"):
                rf.load_ledger(p)

    def test_empty_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(rf.load_ledger(Path(t) / "none.json"),
                             {"version": 1, "classes": {}, "assignments": {}})


if __name__ == "__main__":
    unittest.main()
