import json, os, pathlib, shutil, subprocess, sys, tempfile, types, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_e2e import (
    HarnessError, require_existing, workspaces_from_result,
    find_plan, parse_tap, tap_result_or_raise, run_node_tap, copy_workspace,
    run_phase2, score_tests, compute_report, render_summary, write_report,
    run_case, main,
)


def result_with(*trace_paths):
    return {"cases": [{"name": "e2e-01-ledger-report",
                       "arms": {"with": [{"tracePath": p} for p in trace_paths]}}]}


class WorkspacesFromResult(unittest.TestCase):
    def test_one_run_yields_one_workspace(self):
        r = result_with("/private/tmp/e-AAA111/out/trace.jsonl")
        self.assertEqual([pathlib.Path("/private/tmp/e-AAA111/sealed/home/cwd")],
                         workspaces_from_result(r))

    def test_three_runs_yield_three_workspaces_in_order(self):
        r = result_with(
            "/private/tmp/e-AAA111/out/trace.jsonl",
            "/private/tmp/e-BBB222/out/trace.jsonl",
            "/private/tmp/e-CCC333/out/trace.jsonl",
        )
        self.assertEqual(
            [
                pathlib.Path("/private/tmp/e-AAA111/sealed/home/cwd"),
                pathlib.Path("/private/tmp/e-BBB222/sealed/home/cwd"),
                pathlib.Path("/private/tmp/e-CCC333/sealed/home/cwd"),
            ],
            workspaces_from_result(r),
        )

    def test_missing_with_arm_raises_harness_error_naming_the_case(self):
        r = {"cases": [{"name": "e2e-01-ledger-report", "arms": {}}]}
        with self.assertRaises(HarnessError) as ctx:
            workspaces_from_result(r)
        self.assertIn("e2e-01-ledger-report", str(ctx.exception))

    def test_malformed_trace_path_raises_harness_error_naming_the_path(self):
        r = result_with("/private/tmp/e-AAA111/out/somewhere-else.jsonl")
        with self.assertRaises(HarnessError) as ctx:
            workspaces_from_result(r)
        self.assertIn("/private/tmp/e-AAA111/out/somewhere-else.jsonl", str(ctx.exception))


class RequireExisting(unittest.TestCase):
    def test_missing_workspace_raises_harness_error_naming_path_and_keep_temp(self):
        workspace = pathlib.Path("/private/tmp/e-does-not-exist-XYZ/sealed/home/cwd")
        with self.assertRaises(HarnessError) as ctx:
            require_existing(workspace)
        message = str(ctx.exception)
        self.assertIn(str(workspace), message)
        self.assertIn("временных файлов", message)

    def test_existing_workspace_is_returned_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            self.assertEqual(workspace, require_existing(workspace))

    def test_sealed_ancestor_raises_harness_error_naming_the_seal(self):
        root = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        sealed = root / "sealed"
        workspace = sealed / "home" / "cwd"
        workspace.mkdir(parents=True)
        try:
            os.chmod(sealed, 0o000)
            os.chmod(root, 0o500)
            with self.assertRaises(HarnessError) as ctx:
                require_existing(workspace)
            message = str(ctx.exception)
            self.assertIn(str(sealed), message)
            self.assertIn("chmod 700", message)
        finally:
            os.chmod(root, 0o700)
            os.chmod(sealed, 0o700)
            shutil.rmtree(root)


class FindPlan(unittest.TestCase):
    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp)
            (ws / "docs" / "plans").mkdir(parents=True)
            plan = ws / "docs" / "plans" / "2026-09-15-x.md"
            plan.write_text("# plan")
            self.assertEqual(plan, find_plan(ws))

    def test_folder_with_plan_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp)
            plan_dir = ws / "docs" / "plans" / "2026-09-15-x"
            plan_dir.mkdir(parents=True)
            plan = plan_dir / "plan.md"
            plan.write_text("# plan")
            self.assertEqual(plan, find_plan(ws))

    def test_empty_plans_dir_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_plan(pathlib.Path(tmp)))

    def test_two_plans_returns_newest_by_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = pathlib.Path(tmp)
            (ws / "docs" / "plans").mkdir(parents=True)
            older = ws / "docs" / "plans" / "2026-09-10-a.md"
            newer = ws / "docs" / "plans" / "2026-09-15-b.md"
            older.write_text("old")
            newer.write_text("new")
            os.utime(older, (1000, 1000))
            os.utime(newer, (2000, 2000))
            self.assertEqual(newer, find_plan(ws))


class ParseTap(unittest.TestCase):
    def test_fully_green_output(self):
        text = "TAP version 13\nok 1 - a\nok 2 - b\n# pass 2\n"
        self.assertEqual(
            [{"name": "a", "ok": True}, {"name": "b", "ok": True}],
            parse_tap(text),
        )

    def test_mixed_output(self):
        text = "ok 1 - a\nnot ok 2 - b\nok 3 - c\n"
        self.assertEqual(
            [{"name": "a", "ok": True}, {"name": "b", "ok": False}, {"name": "c", "ok": True}],
            parse_tap(text),
        )

    def test_no_tap_lines_yields_empty_list(self):
        self.assertEqual([], parse_tap("spec-format output, no TAP lines here\n"))


class TapResultOrRaise(unittest.TestCase):
    def test_green_result_passes_through(self):
        tests = tap_result_or_raise(0, "ok 1 - a\nok 2 - b\n", "acceptance/*.test.js")
        self.assertEqual(2, len(tests))

    def test_mixed_result_with_nonzero_exit_is_not_a_harness_error(self):
        # node --test exits non-zero on a failing test — that is a scored result, not a broken runner.
        tests = tap_result_or_raise(1, "ok 1 - a\nnot ok 2 - b\n", "acceptance/*.test.js")
        self.assertEqual([True, False], [t["ok"] for t in tests])

    def test_nonzero_exit_without_tap_lines_raises_harness_error(self):
        with self.assertRaises(HarnessError) as ctx:
            tap_result_or_raise(1, "Cannot find module 'acceptance/report.test.js'\n", "acceptance/*.test.js")
        self.assertIn("acceptance/*.test.js", str(ctx.exception))


class RunNodeTap(unittest.TestCase):
    def test_empty_glob_raises_before_running_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = pathlib.Path(tmp)
            (cwd / "acceptance").mkdir()  # exists, but no *.test.js in it
            with mock.patch("run_e2e.subprocess.run") as run:
                with self.assertRaises(HarnessError) as ctx:
                    run_node_tap(cwd, "acceptance/*.test.js")
            run.assert_not_called()
        self.assertIn("acceptance/*.test.js", str(ctx.exception))
        self.assertIn(str(cwd), str(ctx.exception))

    def test_empty_fixture_glob_also_raises_naming_pattern_and_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = pathlib.Path(tmp)
            (cwd / "test").mkdir()  # agent deleted the fixture's own tests
            with mock.patch("run_e2e.subprocess.run") as run:
                with self.assertRaises(HarnessError) as ctx:
                    run_node_tap(cwd, "test/*.test.js")
            run.assert_not_called()
        self.assertIn("test/*.test.js", str(ctx.exception))
        self.assertIn(str(cwd), str(ctx.exception))


class CopyWorkspace(unittest.TestCase):
    def test_unseals_copies_and_reseals(self):
        root = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        sealed = root / "sealed"
        workspace = sealed / "home" / "cwd"
        workspace.mkdir(parents=True)
        (workspace / "marker.txt").write_text("hi")
        os.chmod(sealed, 0o000)
        dest = root / "ws-1"
        try:
            copy_workspace(workspace, dest)
            self.assertEqual("hi", (dest / "marker.txt").read_text())
            self.assertFalse(os.access(sealed, os.X_OK))
        finally:
            os.chmod(sealed, 0o700)
            shutil.rmtree(root)

    def test_reseals_when_workspace_still_missing_after_unsealing(self):
        # Seal opens but home/cwd never materializes underneath it — require_existing's
        # second look fails, and the seal must not be left open by that failure.
        root = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        sealed = root / "sealed"
        sealed.mkdir()
        workspace = sealed / "home" / "cwd"
        os.chmod(sealed, 0o000)
        dest = root / "ws-1"
        try:
            with self.assertRaises(HarnessError):
                copy_workspace(workspace, dest)
            self.assertFalse(os.access(sealed, os.X_OK))
        finally:
            os.chmod(sealed, 0o700)
            shutil.rmtree(root)

    def test_copies_an_already_open_workspace_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp) / "ws"
            workspace.mkdir()
            (workspace / "marker.txt").write_text("hi")
            dest = pathlib.Path(tmp) / "copy"
            copy_workspace(workspace, dest)
            self.assertEqual("hi", (dest / "marker.txt").read_text())


class RunPhase2(unittest.TestCase):
    def test_timeout_yields_timeout_status(self):
        with mock.patch("run_e2e.subprocess.run",
                         side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=1)):
            result = run_phase2(pathlib.Path("/tmp/ws"), "docs/plans/x.md", pathlib.Path("/plugin"), timeout=1)
        self.assertEqual("timeout", result["status"])
        self.assertIsNone(result["cost_usd"])

    def test_normal_completion_yields_ok_status(self):
        payload = json.dumps({"result": "Done. All tasks executed.", "total_cost_usd": 3.5, "num_turns": 12})
        fake = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=payload, stderr="")
        with mock.patch("run_e2e.subprocess.run", return_value=fake):
            result = run_phase2(pathlib.Path("/tmp/ws"), "docs/plans/x.md", pathlib.Path("/plugin"), timeout=10)
        self.assertEqual({"status": "ok", "cost_usd": 3.5, "turns": 12, "text": "Done. All tasks executed."},
                          result)

    def test_stop_report_yields_halted_status(self):
        text = "The executor halts on a frozen-section conflict and brings it to the plan's author."
        payload = json.dumps({"result": text, "total_cost_usd": 1.0, "num_turns": 4})
        fake = subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=payload, stderr="")
        with mock.patch("run_e2e.subprocess.run", return_value=fake):
            result = run_phase2(pathlib.Path("/tmp/ws"), "docs/plans/x.md", pathlib.Path("/plugin"), timeout=10)
        self.assertEqual("halted", result["status"])


class ComputeReportMatrix(unittest.TestCase):
    def test_full_pass_scores_one(self):
        tests = parse_tap("\n".join(f"ok {i} - t{i}" for i in range(1, 9)))
        self.assertEqual((8, 0, 8), score_tests(tests))

    def test_partial_failure_scores_five_of_eight(self):
        lines = [f"ok {i} - t{i}" for i in range(1, 6)] + [f"not ok {i} - t{i}" for i in range(6, 9)]
        tests = parse_tap("\n".join(lines))
        passed, failed, total = score_tests(tests)
        self.assertEqual((5, 3, 8), (passed, failed, total))
        self.assertEqual(0.625, passed / total)

    def test_no_plan_run_scores_zero_without_raising(self):
        report = compute_report("case", "now", [
            {"workspace": "w", "plan_path": None, "phase2": {"status": "skipped"}, "score": 0.0},
        ], phase1_cost_usd=1.0)
        self.assertEqual(0.0, report["score"])
        self.assertEqual(0.0, report["pass_rate"])
        self.assertIsNone(report["phase2_cost_usd"])

    def test_case_score_averages_runs_and_pass_rate_counts_fully_green_ones(self):
        runs = [
            {"phase2": {"status": "ok", "cost_usd": 1.0}, "score": 1.0},
            {"phase2": {"status": "ok", "cost_usd": 2.0}, "score": 0.625},
        ]
        report = compute_report("case", "now", runs, phase1_cost_usd=None)
        self.assertAlmostEqual(0.8125, report["score"])
        self.assertEqual(0.5, report["pass_rate"])
        self.assertEqual(3.0, report["phase2_cost_usd"])


class WriteReport(unittest.TestCase):
    def test_json_round_trips_and_summary_names_score_and_both_workspace_paths(self):
        report = compute_report("e2e-01-ledger-report", "2026-09-15T12:00:00Z", [
            {"workspace": "/out/ws-1", "plan_path": "docs/plans/x.md",
             "phase2": {"status": "ok", "cost_usd": 2.0, "turns": 10},
             "acceptance": {"passed": 7, "failed": 1, "total": 8, "tests": []},
             "fixture_tests": {"passed": 2, "failed": 0},
             "score": 0.875},
        ], phase1_cost_usd=1.0)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = pathlib.Path(tmp)
            result_path, summary_path = write_report(out_dir, report, ["/private/tmp/e-AAA/sealed/home/cwd"])
            self.assertEqual(report, json.loads(result_path.read_text()))
            summary = summary_path.read_text()
            self.assertIn("0.875", summary)
            self.assertIn("/out/ws-1", summary)
            self.assertIn("/private/tmp/e-AAA/sealed/home/cwd", summary)

    def test_notes_regression_when_acceptance_green_and_fixture_tests_red(self):
        report = compute_report("case", "now", [
            {"workspace": "/out/ws-1", "plan_path": "p.md",
             "phase2": {"status": "ok", "cost_usd": 1.0, "turns": 1},
             "acceptance": {"passed": 8, "failed": 0, "total": 8, "tests": []},
             "fixture_tests": {"passed": 1, "failed": 1},
             "score": 1.0},
        ], phase1_cost_usd=None)
        self.assertIn("regression", render_summary(report, ["/sealed"]))


LEDGER_JOURNAL_JS = '''const fs = require('node:fs')

function readJournal(path) {
  const text = fs.readFileSync(path, 'utf8')
  return text.split('\\n').filter(Boolean).map((line, i) => {
    let row
    try { row = JSON.parse(line) } catch { throw new Error(`bad journal line ${i + 1}`) }
    if (!Number.isInteger(row.amount)) throw new Error(`bad journal line ${i + 1}`)
    return row
  })
}

module.exports = { readJournal }
'''

# `report` deliberately skips --from/--to, so one acceptance test (date-range exclusion)
# fails and the fixture proves the score reflects a real partial result, not a stub 1.0.
LEDGER_BIN_JS = '''#!/usr/bin/env node
const fs = require('node:fs')
const { readJournal } = require('../src/journal')

function arg(name) {
  const i = process.argv.indexOf(`--${name}`)
  return i === -1 ? undefined : process.argv[i + 1]
}

function main() {
  const command = process.argv[2]
  const file = arg('file')
  if (command === 'report') {
    const category = arg('category')
    const rows = readJournal(file).filter((r) => !category || r.category === category)
    const totals = {}
    for (const r of rows) totals[r.category] = (totals[r.category] || 0) + r.amount
    for (const cat of Object.keys(totals).sort()) process.stdout.write(`${cat} ${totals[cat]}\\n`)
    return 0
  }
  process.stderr.write(`unknown command: ${command}\\n`)
  return 1
}

try { process.exit(main()) }
catch (err) { process.stderr.write(`${err.message}\\n`); process.exit(1) }
'''

LEDGER_TEST_JS = '''const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')
const { readJournal } = require('../src/journal')

const tmpFile = path.join(__dirname, 'tmp-journal.jsonl')

test('parses a well-formed journal into rows', () => {
  fs.writeFileSync(tmpFile, [
    JSON.stringify({ date: '2024-01-05', category: 'food', amount: 1200 }),
  ].join('\\n') + '\\n')
  const rows = readJournal(tmpFile)
  fs.unlinkSync(tmpFile)
  assert.strictEqual(rows.length, 1)
})
'''


def _write_ledger_fixture(workspace):
    """Draft `report` (no --from/--to) so acceptance goes 7/8, not a trivial 8/8 or 0/8."""
    (workspace / "bin").mkdir(parents=True, exist_ok=True)
    (workspace / "src").mkdir(parents=True, exist_ok=True)
    (workspace / "test").mkdir(parents=True, exist_ok=True)
    (workspace / "bin" / "ledger.js").write_text(LEDGER_BIN_JS)
    (workspace / "src" / "journal.js").write_text(LEDGER_JOURNAL_JS)
    (workspace / "test" / "journal.test.js").write_text(LEDGER_TEST_JS)


class Phase1JsonRerunIntegration(unittest.TestCase):
    """Step 6: dry-run phase 3 through the real CLI path, phase 1 skipped via --phase1-json."""

    def test_phase1_skipped_and_score_reflects_the_partial_implementation(self):
        root = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        sealed = root / "sealed"
        workspace = sealed / "home" / "cwd"
        (workspace / "docs" / "plans").mkdir(parents=True)
        (workspace / "docs" / "plans" / "2026-09-15-report.md").write_text("# report plan\n")
        _write_ledger_fixture(workspace)
        trace_dir = root / "out"
        trace_dir.mkdir()
        (trace_dir / "trace.jsonl").write_text("")
        os.chmod(sealed, 0o000)

        out_dir = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
        phase1_json = root / "phase1.json"
        phase1_json.write_text(json.dumps({
            "cases": [{"name": "e2e-01-ledger-report",
                       "arms": {"with": [{"tracePath": str(trace_dir / "trace.jsonl"), "costUsd": 0.5}]}}],
        }))
        args = types.SimpleNamespace(case="e2e-01-ledger-report", runs=1,
                                      phase1_json=str(phase1_json), out=str(out_dir))

        def _fail_if_called(*a, **kw):
            raise AssertionError("phase 1 должна была быть пропущена при --phase1-json")

        try:
            with mock.patch("run_e2e.run_phase1", side_effect=_fail_if_called), \
                 mock.patch("run_e2e.run_phase2", return_value={
                     "status": "ok", "cost_usd": 0.02, "turns": 3, "text": "done"}):
                report = run_case(args)
        finally:
            if sealed.exists():
                os.chmod(sealed, 0o700)
            shutil.rmtree(root)

        run = report["runs"][0]
        self.assertEqual(8, run["acceptance"]["total"])
        self.assertEqual(1, run["acceptance"]["failed"])
        self.assertEqual(0.875, run["score"])
        self.assertEqual(0.875, report["score"])
        self.assertEqual(0.5, report["phase1_cost_usd"])

        result_json = json.loads((out_dir / "e2e-result.json").read_text())
        self.assertEqual(0.875, result_json["score"])
        self.assertTrue((out_dir / "summary.md").exists())
        shutil.rmtree(out_dir)


class MainCli(unittest.TestCase):
    def test_exits_2_on_harness_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_json = pathlib.Path(tmp) / "phase1.json"
            bad_json.write_text(json.dumps({"cases": [{"name": "c", "arms": {}}]}))
            code = main(["--case", "c", "--phase1-json", str(bad_json), "--out", str(pathlib.Path(tmp) / "out")])
        self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
