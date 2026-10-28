"""Tests for the two-arm sync of working-agreements candidates (rcv and tst tiers).

Run: python3 -m unittest discover -s plugins/plan-flow/evals -p 'test_wa_arms.py'
"""
import contextlib, importlib.util, io, pathlib, shutil, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sync_comment_rule", HERE / "sync-comment-rule.py")
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

AGREEMENTS = """# Working Agreements

## Before Writing Code

- Ask first.

## Scope Control

- Touch only what is needed.

## Verifying Work

- Run the checks.

### UI verification

- Verify in the app.
"""
CANDIDATE = "## Receiving Review\n\n- Check each claim.\n"
TST_CANDIDATE = "## Writing Tests\n\n- Name the break first.\n"
CASE = """id: x
runs: 3
config:
  append_system_prompt: |
    stale
graders:
  - type: contains
"""
PREAMBLE = "The project's working agreements are below. Follow them.\n\n"


def indent(text):
    return "".join("    " + l if l.strip() else "\n" for l in text.splitlines(keepends=True))


class Arms(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "candidates").mkdir()
        (self.tmp / "candidates" / "receiving-review.md").write_text(CANDIDATE)
        (self.tmp / "candidates" / "writing-tests.md").write_text(TST_CANDIDATE)
        self.source = self.tmp / "working-agreements.md"
        self.source.write_text(AGREEMENTS)
        for name in ("01-rcv-a", "02-rcv-b", "03-tst-a", "04-cmt-a"):
            (self.tmp / name).mkdir()
            (self.tmp / name / "case.yaml").write_text(CASE)
        saved = sync.SOURCE, sync.ROOT
        sync.SOURCE, sync.ROOT = self.source, self.tmp
        self.addCleanup(lambda: setattr(sync, "SOURCE", saved[0]) or setattr(sync, "ROOT", saved[1]))

    def run_sync(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sync.main(list(args))
        return code, out.getvalue()

    def block(self, name):
        return sync.split((self.tmp / name / "case.yaml").read_text())[1]

    def with_text(self):
        return AGREEMENTS.replace("## Verifying Work", CANDIDATE + "\n## Verifying Work")

    def test_write_without_arm_carries_current_agreements_verbatim(self):
        self.assertEqual(0, self.run_sync("--write", "--tier", "rcv", "--arm", "without")[0])
        for name in ("01-rcv-a", "02-rcv-b"):
            self.assertEqual(indent(PREAMBLE + AGREEMENTS), self.block(name))
            self.assertNotIn("## Receiving Review", self.block(name))
        self.assertEqual("    stale\n", self.block("03-tst-a"))
        self.assertEqual("    stale\n", self.block("04-cmt-a"))

    def test_write_with_arm_inserts_candidate_before_verifying_work(self):
        self.run_sync("--write", "--tier", "rcv", "--arm", "with")
        self.assertEqual(indent(PREAMBLE + self.with_text()), self.block("01-rcv-a"))
        self.assertLess(self.block("01-rcv-a").index("## Receiving Review"),
                        self.block("01-rcv-a").index("## Verifying Work"))

    def test_tst_with_arm_inserts_after_verifying_work_section(self):
        self.run_sync("--write", "--tier", "tst", "--arm", "with")
        text = self.block("03-tst-a")
        self.assertLess(text.index("### UI verification"), text.index("## Writing Tests"))
        self.assertEqual(indent(PREAMBLE + AGREEMENTS.rstrip("\n") + "\n\n" + TST_CANDIDATE),
                         text)

    def test_check_matches_after_write(self):
        self.run_sync("--write", "--tier", "rcv", "--arm", "with")
        self.assertEqual((0, ""), self.run_sync("--check", "--tier", "rcv", "--arm", "with"))

    def test_check_names_the_drifted_case(self):
        self.run_sync("--write", "--tier", "rcv", "--arm", "with")
        path = self.tmp / "02-rcv-b" / "case.yaml"
        path.write_text(path.read_text().replace("Check each claim", "Check each claim!"))
        code, out = self.run_sync("--check", "--tier", "rcv", "--arm", "with")
        self.assertEqual(1, code)
        self.assertIn("02-rcv-b", out)
        self.assertNotIn("01-rcv-a", out)

    def test_check_fails_when_the_other_arm_is_asked_for(self):
        self.run_sync("--write", "--tier", "rcv", "--arm", "with")
        self.assertEqual(1, self.run_sync("--check", "--tier", "rcv", "--arm", "without")[0])

    def test_promoted_candidate_is_not_duplicated_and_is_removed_for_without(self):
        self.source.write_text(self.with_text())
        self.run_sync("--write", "--tier", "rcv", "--arm", "with")
        self.assertEqual(indent(PREAMBLE + self.with_text()), self.block("01-rcv-a"))
        self.assertEqual(1, self.block("01-rcv-a").count("## Receiving Review"))
        self.run_sync("--write", "--tier", "rcv", "--arm", "without")
        self.assertEqual(indent(PREAMBLE + AGREEMENTS), self.block("01-rcv-a"))

    def test_unknown_tier_prints_usage_and_exits_2(self):
        code, out = self.run_sync("--check", "--tier", "xyz", "--arm", "with")
        self.assertEqual(2, code)
        self.assertIn("--tier", out)

    def test_tier_without_arm_exits_2(self):
        self.assertEqual(2, self.run_sync("--check", "--tier", "rcv")[0])

    def test_no_tier_leaves_tier_cases_alone(self):
        self.run_sync("--write", "--tier", "rcv", "--arm", "with")
        before = self.block("01-rcv-a")
        self.source.write_text("## Code Comments\n\n- Why.\n\n## Before Writing Code\n\n- Ask.\n")
        self.assertEqual(1, self.run_sync("--check")[0])
        self.run_sync("--write")
        self.assertEqual(before, self.block("01-rcv-a"))
        self.assertIn("- Why.", self.block("04-cmt-a"))


if __name__ == "__main__":
    unittest.main()
