import importlib.util, io, json, os, pathlib, subprocess, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run-evals.py")
rn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rn)

FAKE_CLAUDE = ROOT / "tests/review-flow/reviewer-evals/fake_claude.py"
REAL_RUN = subprocess.run
SMALL = {"ref": "v1", "plan_flow": [{"tier": "comment-rules", "case": "26-cmt-neg-keep-the-why"}],
         "reviewer": []}
BIG = {"ref": "v1", "plan_flow": [{"tier": "plan-execution", "case": None}], "reviewer": []}
MIXED = {"ref": "v1", "plan_flow": [{"tier": "comment-rules", "case": "26-cmt-neg-keep-the-why"},
                                     {"tier": "plan-command", "case": None}],
         "reviewer": ["01-swallowed-catch", "02-deleted-guard"]}


class TTY(io.StringIO):
    def isatty(self):
        return True


class RunEvalsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.calls = []
        self.gate_calls = []
        self.gate_rc = 0
        self.write_pf = True
        self.real_reviewer = False
        for name, val in (("PF_RESULTS", self.tmp / "pf"), ("RV_RESULTS", self.tmp / "rv")):
            p = mock.patch.object(rn, name, val)
            p.start()
            self.addCleanup(p.stop)
        for target in (mock.patch.object(rn.subprocess, "run", side_effect=self.fake_run),
                       mock.patch.object(rn.gate, "main", side_effect=self.fake_gate)):
            target.start()
            self.addCleanup(target.stop)

    def fake_run(self, argv, cwd=None, **kw):
        self.calls.append((list(argv), cwd))
        if "plugin" in argv and "eval" in argv and self.write_pf:
            out = argv[argv.index("--json") + 1]
            pathlib.Path(out).write_text("{}")
        if self.real_reviewer and str(rn.RV_DIR / "run.py") in argv:
            return REAL_RUN(argv, cwd=cwd, capture_output=True, text=True)
        return subprocess.CompletedProcess(argv, 0)

    def fake_gate(self, argv):
        self.gate_calls.append(argv)
        pathlib.Path(argv[argv.index("--summary") + 1]).write_text("gate summary\n")
        print("gate summary")
        return self.gate_rc

    def run_main(self, argv, sel, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(rn, "compute_selection", return_value=sel), \
                mock.patch("sys.stdin", stdin or io.StringIO()), \
                redirect_stdout(out), redirect_stderr(err):
            rc = rn.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def claude_calls(self):
        return [c for c in self.calls if c[0][0] == "claude"]

    def test_nothing_to_measure(self):
        rc, out, _ = self.run_main([], {"ref": "v1", "plan_flow": [], "reviewer": []})
        self.assertEqual(rc, 0)
        self.assertIn("nothing to measure since v1", out)
        self.assertEqual(self.calls, [])

    def test_dry_run(self):
        rc, out, _ = self.run_main(["--dry-run"], MIXED)
        self.assertEqual(rc, 0)
        self.assertIn("comment-rules / 26-cmt-neg-keep-the-why: 1 case(s), 3 run(s), ~$0.24", out)
        self.assertIn("reviewer: 2 case(s)", out)
        self.assertIn("estimate: ~$", out)
        self.assertEqual(self.calls, [])

    def test_dry_run_never_prompts_above_threshold(self):
        rc, _, _ = self.run_main(["--dry-run"], BIG)
        self.assertEqual(rc, 0)
        self.assertEqual(self.calls, [])

    def test_below_threshold_runs_without_asking(self):
        rc, out, _ = self.run_main([], SMALL)
        self.assertEqual(rc, 0)
        self.assertNotIn("Proceed", out)
        self.assertEqual(len(self.claude_calls()), 1)

    def test_above_threshold_confirmed(self):
        big = {**BIG, "plan_flow": BIG["plan_flow"] + [{"tier": "plan-writing", "case": None}]}
        rc, out, _ = self.run_main([], big, stdin=TTY("y\n"))
        self.assertEqual(rc, 0)
        self.assertIn("Proceed?", out)
        self.assertEqual(len(self.claude_calls()), 2)

    def test_above_threshold_declined(self):
        big = {**BIG, "plan_flow": BIG["plan_flow"] + [{"tier": "plan-writing", "case": None}]}
        rc, out, _ = self.run_main([], big, stdin=TTY("n\n"))
        self.assertEqual(rc, 0)
        self.assertIn("cancelled", out)
        self.assertEqual(self.calls, [])

    def test_above_threshold_non_interactive(self):
        big = {**BIG, "plan_flow": BIG["plan_flow"] + [{"tier": "plan-writing", "case": None}]}
        rc, _, err = self.run_main([], big)
        self.assertEqual(rc, 3)
        self.assertRegex(err, r"estimate \$\d+\.\d\d above \$10; pass --yes")
        self.assertEqual(self.calls, [])

    def test_yes_skips_prompt(self):
        big = {**BIG, "plan_flow": BIG["plan_flow"] + [{"tier": "plan-writing", "case": None}]}
        rc, out, _ = self.run_main(["--yes"], big)
        self.assertEqual(rc, 0)
        self.assertNotIn("Proceed", out)
        self.assertEqual(len(self.claude_calls()), 2)

    def test_plan_flow_invocation(self):
        self.run_main(["--claude", "claude"], MIXED)
        (argv, cwd), second = self.claude_calls()
        self.assertEqual(cwd, rn.PF_DIR)
        self.assertEqual(argv[:4], ["claude", "plugin", "eval", "."])
        self.assertEqual(argv[4:8], ["--tag", "comment-rules", "--case", "26-cmt-neg-keep-the-why"])
        self.assertIn("--trust-plugin", argv)
        self.assertTrue(argv[argv.index("--json") + 1].endswith("/pf-1.json"))
        self.assertEqual(argv[argv.index("--max-cost-usd") + 1], "2.00")
        # entry estimate 15 runs * 0.13 = 1.95; 1.5x = 2.925 -> 2.92 or 2.93 per float rounding
        ceiling = float(second[0][second[0].index("--max-cost-usd") + 1])
        self.assertAlmostEqual(ceiling, 2.93, delta=0.01)
        self.assertTrue(second[0][second[0].index("--json") + 1].endswith("/pf-2.json"))

    def test_plan_flow_failure_does_not_stop_loop(self):
        def failing(argv, cwd=None, **kw):
            self.calls.append((list(argv), cwd))
            return subprocess.CompletedProcess(argv, 1)
        with mock.patch.object(rn.subprocess, "run", side_effect=failing):
            rc, _, _ = self.run_main([], MIXED)
        self.assertEqual(len(self.claude_calls()), 2)
        self.assertEqual(rc, 2)

    def test_reviewer_cases_then_regrade(self):
        self.real_reviewer = True
        sel = {"ref": "v1", "plan_flow": [], "reviewer": ["01-swallowed-catch", "02-deleted-guard"]}
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_MODE": "ok-caught"}):
            rc, out, _ = self.run_main(["--claude", str(FAKE_CLAUDE)], sel)
        run_py = [c[0] for c in self.calls if str(rn.RV_DIR / "run.py") in c[0]]
        self.assertEqual(len(run_py), 3)
        for argv, name in zip(run_py, sel["reviewer"]):
            self.assertEqual(argv[argv.index("--case") + 1], name)
            self.assertEqual(argv[argv.index("--runs") + 1], "3")
            self.assertEqual(argv[argv.index("-j") + 1], "2")
        self.assertIn("--regrade", run_py[-1])
        (rv_dir,) = (self.tmp / "rv").iterdir()
        self.assertTrue((rv_dir / "summary.json").exists())
        self.assertEqual(self.gate_calls[0][self.gate_calls[0].index("--reviewer") + 1],
                         str(rv_dir / "summary.json"))
        self.assertIn(f"reviewer results: {rv_dir}", out)

    def test_gate_inputs_summary_and_exit_code(self):
        self.gate_rc = 1
        rc, out, _ = self.run_main([], MIXED)
        self.assertEqual(rc, 1)
        (run_dir,) = (self.tmp / "pf").iterdir()
        self.assertTrue(run_dir.name.startswith("run-"))
        argv = self.gate_calls[0]
        i = argv.index("--plan-flow")
        self.assertEqual(argv[i + 1:i + 3], [str(run_dir / "pf-1.json"), str(run_dir / "pf-2.json")])
        self.assertEqual((run_dir / "gate.md").read_text(), "gate summary\n")
        self.assertIn("gate summary", out)

    def test_missing_pf_result_is_harness_failure(self):
        self.write_pf = False
        rc, _, err = self.run_main([], SMALL)
        self.assertEqual(rc, 2)
        self.assertIn("pf-1.json", err)

    def test_run_locations_printed(self):
        _, out, _ = self.run_main([], MIXED)
        (run_dir,) = (self.tmp / "pf").iterdir()
        (rv_dir,) = (self.tmp / "rv").iterdir()
        self.assertIn(f"plan-flow results: {run_dir}", out)
        self.assertIn(f"reviewer results: {rv_dir}", out)
        self.assertNotEqual(run_dir.name, rv_dir.name)
        self.assertEqual(run_dir.name, "run-" + rv_dir.name)

    def test_arguments_forwarded_to_selector(self):
        args = rn.argparse.Namespace(all=False, smoke=False, plugin="review-flow", since="abc")
        with mock.patch.object(rn.es, "resolve_ref", return_value="abc") as rr, \
                mock.patch.object(rn.es, "changed_files", return_value=[]), \
                mock.patch.object(rn.es, "select", return_value={"plan_flow": [], "reviewer": []}):
            sel = rn.compute_selection(args)
        rr.assert_called_once_with("review-flow", "abc", rn.ROOT)
        self.assertEqual(sel["ref"], "abc")
        self.assertEqual(rn.compute_selection(rn.argparse.Namespace(
            all=False, smoke=True, plugin=None, since=None))["reviewer"], rn.es.SMOKE["reviewer"])
        self.assertIn("reviewer", rn.compute_selection(rn.argparse.Namespace(
            all=True, smoke=False, plugin=None, since=None)))

    def test_unknown_ref_exits_2(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(rn.subprocess, "run", REAL_RUN), \
                redirect_stdout(out), redirect_stderr(err):
            rc = rn.main(["--since", "no-such-ref-xyz"])
        self.assertEqual(rc, 2)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
