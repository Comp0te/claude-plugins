"""Tests for scripts/recurring-findings.py — one test per matrix row."""
import contextlib
import importlib.util
import io
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


def _env(t, records, led):
    rp, lp = Path(t) / "r.jsonl", Path(t) / "l.json"
    rp.write_text("".join(json.dumps(r) + "\n" for r in records))
    lp.write_text(json.dumps(led))
    return rp, lp


def _run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = rf.main(argv)
    return code, buf.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = self._t.name
        self.addCleanup(self._t.cleanup)

    def env(self, records, led):
        self.rp, self.lp = _env(self.t, records, led)
        return ["--records", str(self.rp), "--ledger", str(self.lp)]

    def assign_input(self, data):
        p = Path(self.t) / "a.json"
        p.write_text(json.dumps(data))
        return ["--input", str(p)]

    def saved(self):
        return json.loads(self.lp.read_text())

    def test_unclassified(self):
        base = self.env([rec("k1", "s1"), rec("k2", "s2"), rec("k3", "s3", verdict="dropped")],
                        ledger({"a": {}}, {"k1": ("a", "2026-10-25")}))
        code, out = _run(["unclassified"] + base)
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["classes"], [{"id": "a", "name": "a", "description": "a"}])
        self.assertEqual([f["key"] for f in data["findings"]], ["k2"])
        self.assertEqual(set(data["findings"][0]), set(rf.FINDING_FIELDS))

    def test_assign_merges(self):
        base = self.env([rec("k2", "s2")], ledger({}, {}))
        inp = self.assign_input({"classes": {"new-x": {"name": "N", "description": "D"}},
                                 "assignments": {"k2": "new-x"}})
        code, _ = _run(["assign"] + base + inp + ["--today", "2026-10-25"])
        led = self.saved()
        self.assertEqual(code, 0)
        self.assertEqual(led["classes"]["new-x"], {"name": "N", "description": "D", "status": "observing",
                                                   "decided_on": None, "decided_subjects": None, "homes": []})
        self.assertEqual(led["assignments"]["k2"], {"class": "new-x", "classified_on": "2026-10-25"})

    def _assert_rejected(self, records, led, data, needle):
        base = self.env(records, led)
        before = self.lp.read_bytes()
        buf = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(buf):
            code = rf.main(["assign"] + base + self.assign_input(data))
        self.assertEqual(code, 2)
        self.assertIn(needle, buf.getvalue())
        self.assertEqual(self.lp.read_bytes(), before)

    def test_assign_unknown_key(self):
        self._assert_rejected([rec("k1", "s1")], ledger({"a": {}}, {}), {"assignments": {"ghost-key": "a"}}, "ghost-key")

    def test_assign_undefined_class(self):
        self._assert_rejected([rec("k1", "s1")], ledger({}, {}), {"assignments": {"k1": "nope"}}, "nope")

    def test_assign_bad_class_id(self):
        self._assert_rejected([rec("k1", "s1")], ledger({}, {}),
                              {"classes": {"Bad Id": {"name": "n", "description": "d"}},
                               "assignments": {"k1": "Bad Id"}}, "Bad Id")

    def test_assign_reclassification(self):
        led = ledger({"a": {}, "b": {}}, {"k1": ("a", "2026-10-01")})
        data = {"assignments": {"k1": "b"}}
        self._assert_rejected([rec("k1", "s1")], led, data, "k1")
        code, _ = _run(["assign"] + self.env([rec("k1", "s1")], led) + self.assign_input(data)
                       + ["--reassign", "--today", "2026-10-25"])
        self.assertEqual(code, 0)
        self.assertEqual(self.saved()["assignments"]["k1"], {"class": "b", "classified_on": "2026-10-01"})

    def test_atomic_write(self):
        base = self.env([rec("k1", "s1"), rec("k2", "s2")], ledger({"a": {}}, {}))
        before = self.lp.read_bytes()
        inp = self.assign_input({"assignments": {"k1": "a", "k2": "missing"}})
        code, _ = _run(["assign"] + base + inp)
        self.assertEqual(code, 2)
        self.assertEqual(self.lp.read_bytes(), before)
        self.assertEqual([p.name for p in Path(self.t).glob("*.tmp")], [])

    def digest_env(self, with_data):
        if with_data:
            rs = [rec("k1", "s1"), rec("k2", "s2"), rec("k3", "s3"), rec("k4", "s4"), rec("k5", "s5")]
            led = ledger({"a": {}, "b": {"status": "landed", "homes": [
                {"rung": "agreements", "target": "T", "text": "X", "landed_on": "2026-10-01"}]}},
                {"k1": ("a", "2026-10-25"), "k2": ("a", "2026-10-25"),
                 "k3": ("b", "2026-10-26"), "k4": ("b", "2026-10-26")})
        else:
            rs, led = [], ledger({}, {})
        base = self.env(rs, led)
        ag = Path(self.t) / "ag.md"
        ag.write_text("x\n" * 5)
        return base + ["--agreements", str(ag), "--budget", "3"]

    def test_digest(self):
        code, out = _run(["digest"] + self.digest_env(True))
        self.assertEqual(code, 0)
        i, j, k = out.index("## Candidates"), out.index("## Demotions"), out.index("## Agreements budget")
        self.assertTrue(i < j < k)
        self.assertIn("subjects 2, findings 2, projects p1, agreements-eligible: no", out[i:j])
        self.assertIn("k1", out[i:j])
        self.assertIn("k2", out[i:j])
        self.assertIn("ineffective", out[j:k])
        self.assertIn("5 of 3 lines, over budget", out[k:])

    def test_digest_empty_sections(self):
        code, out = _run(["digest"] + self.digest_env(False))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("none"), 2)
        self.assertEqual(out.split("## Demotions")[0].split("## Candidates")[1].strip(), "none")

    def test_decide(self):
        base = self.env([rec("k1", "s1"), rec("k2", "s2"), rec("k3", "s3")],
                        ledger({"a": {}}, {r: ("a", "2026-10-25") for r in ("k1", "k2", "k3")}))
        code, _ = _run(["decide"] + base + ["--class", "a", "--status", "rejected", "--today", "2026-10-26"])
        a = self.saved()["classes"]["a"]
        self.assertEqual(code, 0)
        self.assertEqual((a["status"], a["decided_on"], a["decided_subjects"]), ("rejected", "2026-10-26", 3))
        for argv in (["--class", "zz", "--status", "rejected"], ["--class", "a", "--status", "bogus"]):
            self.assertEqual(_run(["decide"] + base + argv)[0], 2)

    def test_decide_landed(self):
        base = self.env([rec("k1", "s1")], ledger({"a": {}}, {"k1": ("a", "2026-10-25")}))
        full = ["--class", "a", "--status", "landed", "--rung", "reviewer", "--target", "T", "--text", "X",
                "--today", "2026-10-27"]
        before = self.lp.read_bytes()
        for drop in ("--rung", "--target", "--text"):
            i = full.index(drop)
            self.assertEqual(_run(["decide"] + base + full[:i] + full[i + 2:])[0], 2)
        bad = full[:]
        bad[bad.index("reviewer")] = "nonsense"
        self.assertEqual(_run(["decide"] + base + bad)[0], 2)
        self.assertEqual(self.lp.read_bytes(), before)
        self.assertEqual(_run(["decide"] + base + full)[0], 0)
        a = self.saved()["classes"]["a"]
        self.assertEqual(a["status"], "landed")
        self.assertEqual(a["homes"], [{"rung": "reviewer", "target": "T", "text": "X", "landed_on": "2026-10-27"}])


if __name__ == "__main__":
    unittest.main()
