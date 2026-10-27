import contextlib, importlib.util, io, json, pathlib, subprocess, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FX = pathlib.Path(__file__).resolve().parent / "fixtures"
SCRIPT = ROOT / "scripts" / "eval-gate.py"
spec = importlib.util.spec_from_file_location("eval_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
sys.modules["eval_gate"] = gate
spec.loader.exec_module(gate)


def load(name):
    return json.loads((FX / name).read_text())


def pf(name):
    return gate.compare_pf(load("pf_baseline.json"), gate.pf_metrics(load(name)))[0]


def rv(name):
    return {v.key: v for v in gate.compare_rv(load("rv_baseline.json"), load(name))}


def run_main(*args):
    err = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gate.main(list(map(str, args)))
    return code, out.getvalue(), err.getvalue()


def pf_args(name):
    return ["--plan-flow", FX / name, "--pf-baseline", FX / "pf_baseline.json"]


class PlanFlow(unittest.TestCase):
    def test_all_good(self):
        self.assertEqual(pf("pf_ok.json").status, "ok")
        self.assertEqual(run_main(*pf_args("pf_ok.json"))[0], 0)

    def test_one_in_three_miss(self):
        self.assertEqual(pf("pf_miss.json").status, "ok")

    def test_consistent_failure(self):
        v = pf("pf_consistent.json")
        self.assertEqual(v.status, "regressed")
        self.assertIn("grader g failed every run (baseline 3/3)", v.reasons)
        self.assertEqual(run_main(*pf_args("pf_consistent.json"))[0], 1)

    def test_score_drop(self):
        v = pf("pf_drop.json")
        self.assertEqual(v.status, "regressed")
        self.assertEqual(v.reasons, ["score 0.70 < baseline 1.00 − 0.20"])

    def test_single_run_skips_consistent_rule(self):
        v = pf("pf_single.json")
        self.assertEqual(v.status, "ok")
        low = load("pf_single.json")
        low["cases"][0]["aggregates"]["score"] = 0.5
        v = gate.compare_pf(load("pf_baseline.json"), gate.pf_metrics(low))[0]
        self.assertEqual(v.status, "regressed")
        self.assertTrue(v.reasons[0].startswith("score"))

    def test_no_baseline(self):
        self.assertEqual(pf("pf_nobase.json").status, "unbaselined")
        code, out, _ = run_main(*pf_args("pf_nobase.json"))
        self.assertEqual(code, 0)
        self.assertIn("unbaselined", out)

    def test_missing_baseline_file_means_unbaselined(self):
        code, out, _ = run_main("--plan-flow", FX / "pf_ok.json", "--pf-baseline", FX / "absent.json")
        self.assertEqual(code, 0)
        self.assertIn("unbaselined", out)

    def test_invalid_run_is_harness(self):
        code, out, _ = run_main(*pf_args("pf_invalid.json"))
        self.assertEqual(code, 2)
        self.assertIn("| harness |", out)
        self.assertIn("run 1: timeout", out)

    def test_invalid_zero_judge_cost(self):
        result = load("pf_ok.json"); result["cases"][0]["graders"] = [{"name": "j", "type": "llm"}]
        result["cases"][0]["arms"]["with"][0]["graders"].append(
            {"name": "j", "passed": False, "scored": True, "withOnly": False})
        path = FX / "_tmp_llm.json"
        path.write_text(json.dumps(result))
        try:
            code, out, _ = run_main("--plan-flow", path, "--pf-baseline", FX / "pf_baseline.json")
        finally:
            path.unlink()
        self.assertEqual(code, 2)
        self.assertIn("did not run", out)

    def test_invalid_with_regression_elsewhere_exits_1(self):
        code, _, _ = run_main(*pf_args("pf_invalid.json"), "--plan-flow", FX / "pf_drop.json")
        self.assertEqual(code, 1)

    def test_partial(self):
        code, out, _ = run_main(*pf_args("pf_partial.json"))
        self.assertEqual(code, 2)
        self.assertIn("partial result", out)


class Reviewer(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(all(v.status == "ok" for v in rv("rv_ok.json").values()))

    def test_caught_drop(self):
        v = rv("rv_caught.json")["01-x/defect"]
        self.assertEqual(v.status, "regressed")
        self.assertIn("caught 1/3 (baseline 3/3)", v.reasons)

    def test_scope_drop(self):
        v = rv("rv_scope.json")["01-x/defect"]
        self.assertEqual(v.status, "regressed")
        self.assertTrue(any(r.startswith("scope_ok") for r in v.reasons))

    def test_claim_drop(self):
        v = rv("rv_claim.json")["01-x/defect"]
        self.assertEqual(v.status, "regressed")
        self.assertTrue(any(r.startswith("claim_ok") for r in v.reasons))

    def test_claim_null_not_compared(self):
        self.assertEqual(rv("rv_claim_null.json")["01-x/defect"].status, "ok")

    def test_fp_rise_any_variant(self):
        v = rv("rv_fp.json")["01-x/clean"]
        self.assertEqual(v.status, "regressed")
        self.assertEqual(v.reasons, ["fp_mean 1.50 > baseline 0.00 + 1.0"])

    def test_invalid_row(self):
        self.assertEqual(rv("rv_invalid.json")["01-x/defect"].status, "harness")
        code, _, _ = run_main("--reviewer", FX / "rv_invalid.json", "--rv-baseline", FX / "rv_baseline.json")
        self.assertEqual(code, 2)

    def test_unparsed_is_ok_with_note(self):
        v = rv("rv_unparsed.json")["01-x/defect"]
        self.assertEqual(v.status, "ok")
        self.assertEqual(v.reasons, ["unparsed 1/3"])

    def test_unbaselined_row(self):
        self.assertEqual(rv("rv_nobase.json")["99-new/defect"].status, "unbaselined")

    def test_regression_exit_code(self):
        code, _, _ = run_main("--reviewer", FX / "rv_caught.json", "--rv-baseline", FX / "rv_baseline.json")
        self.assertEqual(code, 1)


class Summary(unittest.TestCase):
    def test_header_and_regressed_first(self):
        vs = [gate.Verdict("plan-flow", "a", "ok"), gate.Verdict("plan-flow", "b", "regressed", ["r"])]
        text = gate.render(vs, ["**plan-flow** x: claudeVersion 2.1.311, cost $0.05"])
        self.assertTrue(text.startswith("**plan-flow** x: claudeVersion 2.1.311"))
        self.assertLess(text.index("| b |"), text.index("| a |"))

    def test_summary_file_and_version_header(self):
        out = FX / "_summary.md"
        try:
            code, stdout, _ = run_main(*pf_args("pf_ok.json"), "--summary", out)
            self.assertEqual(out.read_text(), stdout)
        finally:
            out.unlink(missing_ok=True)
        self.assertIn("claudeVersion 2.1.311", stdout)
        self.assertIn("cost $0.50", stdout)


class WriteBaseline(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.pfb = self.tmp / "pf.json"
        self.rvb = self.tmp / "sub" / "rv.json"

    def write(self, *extra, pf_name="pf_ok.json", rv_name="rv_ok.json"):
        return run_main("--write-baseline", "--plan-flow", FX / pf_name, "--reviewer", FX / rv_name,
                        "--pf-baseline", self.pfb, "--rv-baseline", self.rvb, *extra)

    def test_writes_pf_baseline(self):
        self.assertEqual(self.write()[0], 0)
        doc = json.loads(self.pfb.read_text())
        self.assertEqual(doc["claudeVersion"], "2.1.311")
        self.assertEqual(doc["cases"]["c1"]["graders"], {"g": 3, "h": 3})
        self.assertEqual(doc["cases"]["c1"]["runs"], 3)
        self.assertEqual(doc["cases"]["c1"]["score"], 1.0)
        self.assertIn("recorded", doc)

    def test_writes_rv_baseline_with_parsed_runs(self):
        self.assertEqual(self.write(rv_name="rv_unparsed.json")[0], 0)
        rows = json.loads(self.rvb.read_text())["rows"]
        self.assertEqual(rows["01-x/defect"], {"runs": 2, "caught": 2, "scope_ok": 2,
                                               "claim_ok": 2, "fp_mean": 0.33})
        self.assertEqual(rows["01-x/clean"]["caught"], None)
        self.assertEqual(rows["01-x/clean"]["runs"], 3)

    def test_written_baseline_gates_its_own_run(self):
        self.write()
        code, out, _ = run_main("--plan-flow", FX / "pf_ok.json", "--reviewer", FX / "rv_ok.json",
                                "--pf-baseline", self.pfb, "--rv-baseline", self.rvb)
        self.assertEqual(code, 0)
        self.assertNotIn("unbaselined", out)

    def test_merge_keeps_other_cases_and_replaces_this_run(self):
        self.pfb.write_text(json.dumps({"recorded": "2020-01-01", "cases": {
            "other": {"runs": 3, "score": 0.5, "graders": {"x": 1}},
            "c1": {"runs": 1, "score": 0.0, "graders": {}}}}))
        self.rvb.parent.mkdir()
        self.rvb.write_text(json.dumps({"rows": {"zz/defect": {"runs": 3, "caught": 1}}}))
        self.assertEqual(self.write()[0], 0)
        cases = json.loads(self.pfb.read_text())["cases"]
        self.assertEqual(cases["other"], {"runs": 3, "score": 0.5, "graders": {"x": 1}})
        self.assertEqual(cases["c1"]["runs"], 3)
        rows = json.loads(self.rvb.read_text())["rows"]
        self.assertEqual(rows["zz/defect"], {"runs": 3, "caught": 1})
        self.assertIn("01-x/defect", rows)

    def test_exclude(self):
        self.assertEqual(self.write("--exclude", "c1", "01-x/clean")[0], 0)
        self.assertNotIn("c1", json.loads(self.pfb.read_text())["cases"])
        rows = json.loads(self.rvb.read_text())["rows"]
        self.assertNotIn("01-x/clean", rows)
        self.assertIn("01-x/defect", rows)

    def test_harness_writes_nothing_and_names_case(self):
        code, _, err = self.write(pf_name="pf_invalid.json")
        self.assertEqual(code, 2)
        self.assertIn("c1", err)
        self.assertFalse(self.pfb.exists())
        self.assertFalse(self.rvb.exists())

    def test_reviewer_harness_writes_nothing(self):
        code, _, err = self.write(rv_name="rv_invalid.json")
        self.assertEqual(code, 2)
        self.assertIn("01-x/defect", err)
        self.assertFalse(self.pfb.exists())
        self.assertFalse(self.rvb.exists())

    def test_unreadable_input_writes_nothing(self):
        code, _, _ = self.write(pf_name="nope.json")
        self.assertEqual(code, 2)
        self.assertFalse(self.pfb.exists())


class BadInput(unittest.TestCase):
    def test_missing_file(self):
        p = subprocess.run([sys.executable, str(SCRIPT), "--plan-flow", str(FX / "nope.json")],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn(f"eval-gate: cannot read {FX / 'nope.json'}", p.stderr)

    def test_non_json(self):
        bad = FX / "not_json.txt"
        p = subprocess.run([sys.executable, str(SCRIPT), "--reviewer", str(bad)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("eval-gate: cannot read", p.stderr)


if __name__ == "__main__":
    unittest.main()
