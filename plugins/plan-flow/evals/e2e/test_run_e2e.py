import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_e2e import HarnessError, require_existing, workspaces_from_result


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
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            self.assertEqual(workspace, require_existing(workspace))


if __name__ == "__main__":
    unittest.main()
