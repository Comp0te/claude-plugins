"""Structural tests for the comment-rules tier.

These run for free and catch the failures that otherwise cost a paid run to discover: a rule
copy that drifted from the working agreements, a grader pointing at a file no scaffold creates,
and a "this comment survives" grader whose pattern was never in the fixture to begin with.

Run: python3 -m unittest discover -s plugins/plan-flow/evals -p 'test_comment_rules.py'
"""
import importlib.util, pathlib, re, unittest

ROOT = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sync_comment_rule", ROOT / "sync-comment-rule.py")
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

# Graders that assert a fixture comment survived the edit. Their pattern has to match the
# scaffold's own content, or the grader is unpassable and the case measures nothing.
SURVIVAL_GRADERS = {
    "25-cmt-budget-outranks-neighbour": {"neighbours-untouched-a": "src/text.js",
                                         "neighbours-untouched-b": "src/text.js"},
    "26-cmt-neg-keep-the-why": {"why-survives": "src/clock.js",
                                "why-survives-whole": "src/clock.js"},
    "27-cmt-neg-exception-respected": {"contract-survives-rounding": "src/settlement.js",
                                       "contract-survives-fees": "src/settlement.js"},
}


def scaffolded(case):
    """{path: contents} for every file the case's scaffold writes with a heredoc."""
    body = (case / "scaffold.sh").read_text()
    pattern = r"cat > (\S+) <<'SCAFFOLD_EOF'\n(.*?)\nSCAFFOLD_EOF\n"
    return {m.group(1): m.group(2) for m in re.finditer(pattern, body, re.S)}


def graders(case):
    """[(name, {field: value})] for each grader in the case, by text — no YAML parser here."""
    body = (case / "case.yaml").read_text()
    out, current = [], None
    for line in body[body.index("\ngraders:"):].splitlines():
        if re.match(r"^  - type: (\w+)", line):
            current = {"type": re.match(r"^  - type: (\w+)", line).group(1)}
            out.append(current)
        elif current is not None:
            found = re.match(r"^\s{4,6}(name|pattern|match|path|weight): (.*)$", line)
            if found:
                current[found.group(1)] = found.group(2).strip().strip("'\"")
    return [(g.get("name", "?"), g) for g in out]


class RuleCopy(unittest.TestCase):
    def test_every_case_carries_the_current_rule(self):
        self.assertEqual(0, sync.main(["--check"]),
                         "run `python3 evals/sync-comment-rule.py --write` after editing the rule")

    def test_the_source_section_is_the_one_being_measured(self):
        text = sync.section()
        self.assertTrue(text.startswith("## Code Comments"))
        for clause in ("Why, not what", "Don't narrate the failure", "Private members get nothing",
                       "No process artifacts", "Budget: 2 lines inline"):
            self.assertIn(clause, text)


class CaseShape(unittest.TestCase):
    def setUp(self):
        self.cases = sorted(p.parent for p in ROOT.glob("*-cmt-*/case.yaml"))
        self.assertTrue(self.cases)

    def test_every_case_has_a_scaffold(self):
        for case in self.cases:
            self.assertTrue((case / "scaffold.sh").exists(), case.name)

    def test_every_case_is_tagged_for_the_tier(self):
        for case in self.cases:
            self.assertIn("tags: [comment-rules]", (case / "case.yaml").read_text(), case.name)

    def test_every_case_declares_three_runs(self):
        for case in self.cases:
            self.assertIn("\nruns: 3\n", (case / "case.yaml").read_text(), case.name)

    def test_no_case_grants_bash(self):
        """The tier grades comments, not a green test run; Bash would only buy turns."""
        for case in self.cases:
            self.assertNotIn("Bash", (case / "case.yaml").read_text(), case.name)


class GraderTargets(unittest.TestCase):
    def setUp(self):
        self.cases = sorted(p.parent for p in ROOT.glob("*-cmt-*/case.yaml"))

    def test_every_grader_path_is_a_file_the_scaffold_creates(self):
        for case in self.cases:
            files = scaffolded(case)
            for name, grader in graders(case):
                if "path" in grader:
                    self.assertIn(grader["path"], files, "%s/%s" % (case.name, name))

    def test_survival_graders_match_the_fixture_they_guard(self):
        for case in self.cases:
            expected = SURVIVAL_GRADERS.get(case.name, {})
            files = scaffolded(case)
            for name, grader in graders(case):
                if name not in expected:
                    continue
                self.assertEqual("contains", grader.get("match"), "%s/%s" % (case.name, name))
                self.assertRegex(files[expected[name]], grader["pattern"],
                                 "%s/%s cannot pass: the fixture never contained it"
                                 % (case.name, name))

    def test_every_listed_survival_grader_still_exists(self):
        for case_name, names in SURVIVAL_GRADERS.items():
            found = {name for name, _ in graders(ROOT / case_name)}
            for name in names:
                self.assertIn(name, found, "%s/%s was renamed or removed" % (case_name, name))


if __name__ == "__main__":
    unittest.main()
