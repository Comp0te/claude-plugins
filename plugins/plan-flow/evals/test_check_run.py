"""Unit tests for the run validator.

Run: python3 -m unittest discover -s plugins/plan-flow/evals -p 'test_*.py'
"""
import contextlib, importlib.util, io, json, pathlib, tempfile, unittest

_spec = importlib.util.spec_from_file_location(
    "check_run", pathlib.Path(__file__).resolve().parent / "check-run.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def result(graders, runs, arm="with"):
    return {"cases": [{"name": "a-case", "graders": graders, "arms": {arm: runs}}]}


def run(score=1.0, judge=0.004, error=None, names=("judged",), skipped=False):
    return {"score": score, "judgeCostUsd": judge, "error": error,
            "skippedPaidGraders": skipped,
            "graders": [{"name": n, "passed": True} for n in names]}


JUDGED = [{"name": "judged", "type": "llm"}]
FREE = [{"name": "matched", "type": "regex"}]


def verdict(res):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(res, f)
    with contextlib.redirect_stdout(io.StringIO()):
        return check.main([f.name])


class Usable(unittest.TestCase):
    def test_a_clean_judged_run_passes(self):
        self.assertEqual(0, verdict(result(JUDGED, [run()])))

    def test_a_free_case_with_no_judge_cost_passes(self):
        """A case with only regex graders spends nothing on a judge; that is not a failure."""
        self.assertEqual(0, verdict(result(FREE, [run(judge=0, names=("matched",))])))

    def test_both_arms_are_checked(self):
        res = result(JUDGED, [run()])
        res["cases"][0]["arms"]["without"] = [run(error="exit 1: boom")]
        self.assertEqual(1, verdict(res))


class NotMeasurements(unittest.TestCase):
    def test_a_harness_error_fails(self):
        self.assertEqual(1, verdict(result(JUDGED, [run(error="exit 1: session limit")])))

    def test_an_llm_grader_that_never_ran_fails(self):
        self.assertEqual(1, verdict(result(JUDGED, [run(judge=0)])))

    def test_a_missing_judge_cost_key_fails(self):
        bare = run()
        del bare["judgeCostUsd"]
        self.assertEqual(1, verdict(result(JUDGED, [bare])))

    def test_skipped_paid_graders_fail(self):
        self.assertEqual(1, verdict(result(JUDGED, [run(skipped=True)])))

    def test_an_empty_result_fails(self):
        self.assertEqual(1, verdict({"cases": []}))

    def test_a_case_with_no_runs_fails(self):
        self.assertEqual(1, verdict(result(JUDGED, [])))

    def test_a_partial_result_fails_even_when_every_run_is_clean(self):
        res = result(JUDGED, [run()])
        res.update(partial=True, partialReason="interrupted")
        self.assertEqual(1, verdict(res))


class Reasons(unittest.TestCase):
    def test_the_error_text_is_carried_through(self):
        bad = check.verdicts(result(JUDGED, [run(error="exit 1: session limit")]))
        self.assertEqual(1, len(bad))
        self.assertIn("session limit", bad[0][3])

    def test_the_ungraded_judge_names_the_grader(self):
        bad = check.verdicts(result(JUDGED, [run(judge=0)]))
        self.assertIn("judged", bad[0][3])

    def test_the_case_and_arm_are_identified(self):
        bad = check.verdicts(result(JUDGED, [run(), run(error="boom")]))
        self.assertEqual(("a-case", "with", 1), bad[0][:3])


if __name__ == "__main__":
    unittest.main()
