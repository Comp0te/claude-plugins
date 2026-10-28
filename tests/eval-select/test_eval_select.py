import importlib.util, io, json, pathlib, subprocess, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "eval-select.py"
spec = importlib.util.spec_from_file_location("eval_select", SCRIPT)
es = importlib.util.module_from_spec(spec)
spec.loader.exec_module(es)

PF = "plugins/plan-flow"
RV = "tests/review-flow/reviewer-evals"


def write(root, rel, text="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                   check=True, capture_output=True)


def commit(root, msg):
    git(root, "add", "-A")
    git(root, "commit", "-m", msg)


def case_yaml(name, tag):
    return f"schema_version: \"1.1\"\nname: {name}\ntags: [{tag}]\n"


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls._tmp.name)
        git(cls.root, "init", "-q")
        write(cls.root, f"{PF}/evals/18-cmt-why-not-what/case.yaml",
              case_yaml("18-cmt-why-not-what", "comment-rules"))
        write(cls.root, f"{PF}/evals/30-wa-simulate-unavailable-trigger/case.yaml",
              case_yaml("30-wa", "working-agreements"))
        write(cls.root, f"{PF}/evals/e2e-01-ledger-report/case.yaml", case_yaml("e2e-01", "e2e"))
        write(cls.root, f"{PF}/evals/e2e/run_e2e.py")
        write(cls.root, f"{PF}/evals/44-int-x/case.yaml", case_yaml("44-int-x", "intent"))
        write(cls.root, f"{RV}/cases/02-deleted-guard/case.json",
              json.dumps({"agent": "review-flow:deletion-check"}))
        write(cls.root, f"{RV}/cases/05-injection/case.json",
              json.dumps({"agent": "review-flow:silent-failure-hunter",
                          "fixture_from": "02-deleted-guard"}))
        write(cls.root, f"{RV}/cases/01-swallowed-catch/case.json",
              json.dumps({"agent": "review-flow:silent-failure-hunter"}))
        commit(cls.root, "one")
        git(cls.root, "tag", "plan-flow--v0.6.1")
        write(cls.root, "README.md", "a\n")
        commit(cls.root, "two")
        git(cls.root, "tag", "plan-flow--v0.6.2")
        write(cls.root, "README.md", "b\n")
        commit(cls.root, "three")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def sel(self, *paths):
        return es.select(list(paths), self.root)

    def tiers(self, *paths):
        return self.sel(*paths)["plan_flow"]


class TestRef(Base):
    def test_ref_from_plugin_tag(self):
        self.assertEqual(es.resolve_ref("plan-flow", None, self.root), "plan-flow--v0.6.2")

    def test_changed_files_since_tag_and_uncommitted(self):
        write(self.root, "tracked.txt", "t\n")
        commit(self.root, "four")
        try:
            (self.root / "README.md").write_text("dirty\n")
            self.assertEqual(es.changed_files("plan-flow--v0.6.2", self.root),
                             ["README.md", "tracked.txt"])
        finally:
            git(self.root, "checkout", "--", "README.md")
            git(self.root, "reset", "-q", "--hard", "HEAD~1")

    def test_no_tag_for_plugin(self):
        self.assertEqual(es.resolve_ref("figma-flow", None, self.root), "HEAD~1")

    def test_no_plugin(self):
        self.assertEqual(es.resolve_ref(None, None, self.root), "HEAD~1")

    def test_explicit_ref(self):
        self.assertEqual(es.resolve_ref("plan-flow", "plan-flow--v0.6.1", self.root),
                         "plan-flow--v0.6.1")

    def test_bad_ref_exits_2(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = es.main(["--since", "nope", "--root", str(self.root)])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue().strip(), "eval-select: unknown ref nope")


class TestSelect(Base):
    def test_skill(self):
        r = self.sel(f"{PF}/skills/writing-implementation-plans/SKILL.md")
        self.assertEqual(r, {"plan_flow": [{"tier": "plan-writing", "case": None}], "reviewer": []})

    def test_debugging_skill(self):
        self.assertEqual(self.tiers(f"{PF}/skills/debugging/SKILL.md"),
                         [{"tier": "debugging", "case": None}])

    def test_debugging_script(self):
        self.assertEqual(self.tiers(f"{PF}/skills/debugging/scripts/find-polluter.sh"),
                         [{"tier": "debugging", "case": None}])

    def test_intent_skill(self):
        self.assertEqual(self.tiers(f"{PF}/skills/intent/SKILL.md"),
                         [{"tier": "intent", "case": None}])

    def test_intent_template(self):
        self.assertEqual(self.tiers(f"{PF}/skills/intent/references/intent-template.md"),
                         [{"tier": "intent", "case": None}])

    def test_intent_reader(self):
        self.assertEqual(self.tiers(f"{PF}/agents/intent-reader.md"),
                         [{"tier": "intent", "case": None}])

    def test_intent_case_edited(self):
        self.assertEqual(self.tiers(f"{PF}/evals/44-int-x/case.yaml"),
                         [{"tier": "intent", "case": "44-int-x"}])

    def test_executor(self):
        self.assertEqual(self.tiers(f"{PF}/agents/plan-executor.md"),
                         [{"tier": "plan-execution", "case": None}])

    def test_command(self):
        self.assertEqual(self.tiers(f"{PF}/commands/execute-plan.md"),
                         [{"tier": "plan-command", "case": None}])

    def test_agreements(self):
        self.assertCountEqual(self.tiers(f"{PF}/references/working-agreements.md"),
                              [{"tier": "comment-rules", "case": None},
                               {"tier": "plan-command", "case": None}])

    def test_session_start_hook(self):
        want = [{"tier": "comment-rules", "case": None}, {"tier": "plan-command", "case": None}]
        self.assertCountEqual(self.tiers(f"{PF}/hooks/session-start.py"), want)
        self.assertCountEqual(self.tiers(f"{PF}/hooks/operating-rules.md"), want)

    def test_comment_hook(self):
        self.assertCountEqual(self.tiers(f"{PF}/hooks/comment-budget.py"),
                              [{"tier": "comment-rules", "case": None},
                               {"tier": "plan-execution", "case": "12-exec-comment-budget"}])

    def test_one_case_edited(self):
        self.assertEqual(self.tiers(f"{PF}/evals/18-cmt-why-not-what/case.yaml"),
                         [{"tier": "comment-rules", "case": "18-cmt-why-not-what"}])

    def test_e2e_nothing(self):
        r = self.sel(f"{PF}/evals/e2e-01-ledger-report/case.yaml", f"{PF}/evals/e2e/run_e2e.py")
        self.assertEqual(r, {"plan_flow": [], "reviewer": []})

    def test_tag_outside_tier_flags(self):
        r = self.sel(f"{PF}/evals/30-wa-simulate-unavailable-trigger/case.yaml")
        self.assertEqual(r, {"plan_flow": [], "reviewer": []})

    def test_reviewer_agent(self):
        r = self.sel("plugins/review-flow/agents/deletion-check.md")
        self.assertEqual(r["reviewer"], ["02-deleted-guard"])
        self.assertEqual(r["plan_flow"], [])

    def test_reviewer_harness(self):
        for f in ("brief.md", "grade.py", "run.py"):
            self.assertEqual(self.sel(f"{RV}/{f}")["reviewer"],
                             ["01-swallowed-catch", "02-deleted-guard", "05-injection"])

    def test_reviewer_case_with_dependents(self):
        self.assertEqual(self.sel(f"{RV}/cases/02-deleted-guard/fixture/a.ts")["reviewer"],
                         ["02-deleted-guard", "05-injection"])

    def test_irrelevant(self):
        r = self.sel("README.md", "plugins/ui-verifier-web/x.md", "scripts/eval-select.py")
        self.assertEqual(r, {"plan_flow": [], "reviewer": []})

    def test_tier_subsumes_case(self):
        r = self.tiers(f"{PF}/references/working-agreements.md",
                       f"{PF}/evals/18-cmt-why-not-what/case.yaml")
        self.assertNotIn({"tier": "comment-rules", "case": "18-cmt-why-not-what"}, r)
        self.assertIn({"tier": "comment-rules", "case": None}, r)


class TestCli(Base):
    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = es.main([*args, "--root", str(self.root)])
        return code, json.loads(out.getvalue())

    def test_all(self):
        code, r = self.run_cli("--all")
        self.assertEqual(code, 0)
        self.assertEqual([e["tier"] for e in r["plan_flow"]],
                         ["plan-writing", "plan-execution", "plan-command", "comment-rules", "debugging", "intent"])
        self.assertTrue(all(e["case"] is None for e in r["plan_flow"]))
        self.assertEqual(r["reviewer"], ["01-swallowed-catch", "02-deleted-guard", "05-injection"])

    def test_smoke(self):
        code, r = self.run_cli("--smoke")
        self.assertEqual(r["plan_flow"], [{"tier": "comment-rules", "case": "26-cmt-neg-keep-the-why"}])
        self.assertEqual(r["reviewer"], ["01-swallowed-catch"])

    def test_diff_output_has_ref(self):
        code, r = self.run_cli("--plugin", "plan-flow")
        self.assertEqual(r["ref"], "plan-flow--v0.6.2")
        self.assertEqual(r["plan_flow"], [])

    def test_debugging_tier_grants_write_edit_bash(self):
        argv = es.pf_argv({"tier": "debugging", "case": None})
        i = argv.index("--allow-tools")
        self.assertEqual(argv[i:i + 4], ["--allow-tools", "Write", "Edit", "Bash"])

    def test_pf_argv(self):
        argv = es.pf_argv({"tier": "comment-rules", "case": "26-x"})
        self.assertEqual(argv[:4], ["--tag", "comment-rules", "--case", "26-x"])
        self.assertIn("--no-publish", argv)
        self.assertNotIn("--json", argv)


if __name__ == "__main__":
    unittest.main()
