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


class RoutingSupportTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.addCleanup(self._t.cleanup)

    def write(self, name, text):
        p = self.t / name
        p.write_text(text)
        return str(p)

    def test_found_by_stats(self):
        rs = [{**rec("k1", "s1"), "found_by": ["a"]}, {**rec("k2", "s2"), "found_by": ["a", "b"]},
              {**rec("k3", "s3", verdict="dropped"), "found_by": ["a"]}]
        led = ledger({"c": {}}, {r["key"]: ("c", "2026-10-25") for r in rs})
        self.assertEqual(rf.class_stats(rs, led)["c"]["found_by"], {"a": 2, "b": 1})

    def test_found_by_in_digest(self):
        rs = [{**rec("k1", "s1"), "found_by": ["a", "b"]}, {**rec("k2", "s2"), "found_by": ["a"]},
              rec("k3", "s3"), rec("k4", "s4")]
        led = ledger({"c": {}, "d": {}}, {"k1": ("c", "2026-10-25"), "k2": ("c", "2026-10-25"),
                                          "k3": ("d", "2026-10-25"), "k4": ("d", "2026-10-25")})
        rp, lp = _env(self.t, rs, led)
        _, out = _run(["digest", "--records", str(rp), "--ledger", str(lp), "--agreements", str(self.t / "none.md")])
        lines = {l.split(" ")[1]: l for l in out.splitlines() if l.startswith("- ")}
        self.assertTrue(lines["c"].endswith(", found by: a×2, b×1"))
        self.assertTrue(lines["d"].endswith(", found by: none"))

    def budget(self, agreement_lines, add_lines, *extra):
        ag = self.write("wa.md", "x\n" * agreement_lines)
        add = self.write("add.md", "y\n" * add_lines)
        return _run(["budget-check", "--agreements", ag, "--budget", "60", "--add", add, *extra])

    def test_budget_fits(self):
        code, out = self.budget(54, 2)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"lines": 54, "after": 56, "limit": 60, "fits": True})

    def test_budget_over(self):
        code, out = self.budget(59, 2)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"lines": 59, "after": 61, "limit": 60, "fits": False})

    def test_budget_replaces(self):
        code, out = self.budget(60, 2, "--replaces", "7-8")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"lines": 60, "after": 60, "limit": 60, "fits": True})
        for bad in ("8-7", "59-61", "0-2", "x"):
            self.assertEqual(self.budget(60, 2, "--replaces", bad)[0], 2, bad)

    def check(self, text, records):
        rp = self.write("r.jsonl", "".join(json.dumps(r) + "\n" for r in records))
        return _run(["check-text", "--records", rp, "--input", self.write("t.md", text)])

    def test_check_text_clean(self):
        r = {**rec("k1", "feature-x", "acme-app"), "file": "src/widget/panel.ts", "title": "Bad `loadPanelData` call"}
        code, out = self.check("Validate input at the boundary before use.", [r])
        self.assertEqual((code, out.strip()), (0, "clean"))

    def test_check_text_hits(self):
        r = {**rec("k1", "feature-x", "acme-app"), "file": "src/widget/panel.ts",
             "title": "Bad `loadPanelData` call", "issue": "uses `retry_count` and `cfg.timeoutMs`"}
        cases = {"project": "Seen in ACME-App code.", "path": "See src/widget/panel.ts.",
                 "basename": "Edit panel.ts first.", "subject": "On feature-x we saw it.",
                 "identifier": "Do not call loadPanelData.", "snake": "Reset retry_count.", "dotted": "Read cfg.timeoutMs."}
        for name, text in cases.items():
            code, out = self.check(text, [r])
            self.assertEqual(code, 1, name)
            self.assertTrue(out.strip(), name)
        kinds = {l.split(":")[0] for l in self.check(" ".join(cases.values()), [r])[1].splitlines()}
        self.assertEqual(kinds, {"project", "path", "subject", "identifier"})
        self.assertIn("project: acme-app", self.check(cases["project"], [r])[1])
        self.assertEqual(_run(["check-text", "--records", str(self.t / "r.jsonl"), "--input", str(self.t / "gone")])[0], 2)

    def test_check_text_generic_words(self):
        r = {**rec("k1", "feature-x", "acme-app"), "title": "`expect` and `catch` on `null` via `as T`",
             "issue": "`expect` `catch` `null` `as T`"}
        code, out = self.check("Use expect, catch, null and as T carefully.", [r])
        self.assertEqual((code, out.strip()), (0, "clean"))


if __name__ == "__main__":
    unittest.main()
