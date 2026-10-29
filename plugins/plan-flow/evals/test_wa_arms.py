"""Tests for the two-arm sync of working-agreements candidates (rcv and tst tiers).

Run: python3 -m unittest discover -s plugins/plan-flow/evals -p 'test_wa_arms.py'
"""
import contextlib, importlib.util, io, pathlib, re, shutil, tempfile, unittest

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

    def test_promoted_candidate_needs_no_candidate_file(self):
        self.source.write_text(self.with_text())
        (self.tmp / "candidates" / "receiving-review.md").unlink()
        self.assertEqual(0, self.run_sync("--write", "--tier", "rcv", "--arm", "with")[0])
        self.assertEqual(indent(PREAMBLE + self.with_text()), self.block("01-rcv-a"))
        self.assertEqual(1, self.block("01-rcv-a").count("## Receiving Review"))
        self.assertEqual((0, ""), self.run_sync("--check", "--tier", "rcv", "--arm", "with"))

    def test_source_without_trailing_newline_keeps_next_field_on_its_own_line(self):
        self.source.write_text(AGREEMENTS.rstrip("\n"))
        self.run_sync("--write", "--tier", "rcv", "--arm", "without")
        self.assertTrue(sync.split((self.tmp / "01-rcv-a" / "case.yaml").read_text())[2].startswith("graders:\n"))
        self.assertEqual(0, self.run_sync("--check", "--tier", "rcv", "--arm", "without")[0])

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


class CaseStructure:
    """Shape checks shared by the real cases of a working-agreements tier."""
    PATTERN = TAG = COUNT = None
    PATH_SOURCE = "scaffold.sh"

    @classmethod
    def dirs(cls):
        return sorted(d for d in HERE.glob(cls.PATTERN) if d.is_dir())

    def test_expected_number_of_cases_exist(self):
        self.assertEqual(self.COUNT, len(self.dirs()))

    def test_every_case_has_the_required_shape(self):
        for d in self.dirs():
            with self.subTest(case=d.name):
                scaffold = (d / "scaffold.sh").read_text()
                case = (d / "case.yaml").read_text()
                self.assertNotIn("git init", scaffold)
                self.assertRegex(case, r"(?m)^tags: \[%s\]$" % self.TAG)
                self.assertRegex(case, r"(?m)^runs: 3$")
                self.assertIn("  append_system_prompt: |\n", case)
                self.assertRegex(case, r"(?m)^  allowed_tools: \[[^\]]*\bBash\b")

    def test_block_scalars_have_indented_text_and_no_fused_keys(self):
        for d in self.dirs():
            lines = (d / "case.yaml").read_text().splitlines()
            for i, line in enumerate(lines):
                with self.subTest(case=d.name, line=i + 1):
                    block = re.match(r"^( *)[a-z_]+: \|$", line)
                    if block:
                        nxt = lines[i + 1]
                        self.assertGreater(len(nxt) - len(nxt.lstrip()), len(block.group(1)))
                    self.assertIsNone(re.search(r"\S +(weight|min|max): ", line))

    def test_every_grader_path_is_written_by_the_scaffold(self):
        for d in self.dirs():
            source = (d / self.PATH_SOURCE).read_text()
            if self.PATH_SOURCE == "case.yaml":
                source = source.split("  append_system_prompt:")[0]
            for path in re.findall(r"(?m)^\s+path: (\S+)", (d / "case.yaml").read_text()):
                with self.subTest(case=d.name, path=path):
                    self.assertIn(path, source)


class RcvCases(CaseStructure, unittest.TestCase):
    """Structure of the real review-reception cases."""
    PATTERN, TAG, COUNT = "*-rcv-*", "review-reception", 4


class TstCases(CaseStructure, unittest.TestCase):
    """Structure of the real test-writing cases."""
    PATTERN, TAG, COUNT = "*-tst-*", "test-rules", 3
    # The agent writes the graded test file, so the task prompt must name it.
    PATH_SOURCE = "case.yaml"


def grader_pattern(case_dir, name):
    text = (HERE / case_dir / "case.yaml").read_text()
    m = re.search(r"(?m)^    name: %s\n(?:    .*\n)*?    pattern: '([^'\n]*)'" % re.escape(name), text)
    assert m, name
    return re.compile(m.group(1))


class TstRegexGraders(unittest.TestCase):
    """The not_contains patterns must match node:assert style, and only the forbidden shape."""

    def test_35_flags_assertions_whose_subject_is_the_constant(self):
        pat = grader_pattern("35-tst-retry-policy", "no-constant-assertion")
        for line in ("assert.equal(MAX_RETRIES, 3)", "assert.strictEqual(retry.MAX_RETRIES, 3)",
                     "strictEqual(MAX_RETRIES, 3)", "assert.ok(MAX_RETRIES)"):
            with self.subTest(line=line):
                self.assertTrue(pat.search(line))

    def test_35_allows_using_the_constant_as_the_expected_call_count(self):
        # Comparing observed behaviour to the constant is not an assertion on its value.
        pat = grader_pattern("35-tst-retry-policy", "no-constant-assertion")
        self.assertFalse(pat.search("assert.equal(calls, MAX_RETRIES)"))

    def test_36_flags_buildquery_as_the_expected_argument(self):
        pat = grader_pattern("36-tst-query-builder", "no-buildquery-as-expected")
        for line in ("assert.equal(out, buildQuery({a: 1}))",
                     "assert.strictEqual(buildQuery(f), buildQuery(f))"):
            with self.subTest(line=line):
                self.assertTrue(pat.search(line))

    def test_36_allows_buildquery_as_the_actual_argument(self):
        pat = grader_pattern("36-tst-query-builder", "no-buildquery-as-expected")
        for line in ("assert.equal(buildQuery({a: 'x'}), \"a = 'x'\")",
                     "assert.strictEqual(buildQuery({}), '')"):
            with self.subTest(line=line):
                self.assertFalse(pat.search(line))


if __name__ == "__main__":
    unittest.main()
