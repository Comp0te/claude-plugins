"""Integrity checks every case fixture must pass before it measures anything.

A broken fixture reads as a weak agent, so this runs against every case under
`cases/` rather than trusting each one was built right by hand.
"""
import json
import re
import unittest
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
ROOT = HERE.parent.parent.parent
AGENTS_DIR = ROOT / "plugins/review-flow/agents"
GIVEAWAY_RE = re.compile(r"(?i)\b(bug|buggy|planted|defect|fixme|todo)\b")


def list_files(tree: Path) -> list[Path]:
    return sorted(p for p in tree.rglob("*") if p.is_file())


def diff_stats(a_tree: Path, b_tree: Path):
    """Compare two trees file by file.

    Returns (files_touched, changed_lines, differing) where `differing` maps
    each differing file's path (relative to the trees) to the 1-based line
    numbers that changed, one set per side.
    """
    a_files = {p.relative_to(a_tree).as_posix(): p for p in list_files(a_tree)}
    b_files = {p.relative_to(b_tree).as_posix(): p for p in list_files(b_tree)}
    files_touched = 0
    changed_lines = 0
    differing: dict[str, tuple[set[int], set[int]]] = {}
    for rel in sorted(set(a_files) | set(b_files)):
        a_text = a_files[rel].read_text().splitlines() if rel in a_files else []
        b_text = b_files[rel].read_text().splitlines() if rel in b_files else []
        if a_text == b_text:
            continue
        files_touched += 1
        a_changed: set[int] = set()
        b_changed: set[int] = set()
        matcher = SequenceMatcher(a=a_text, b=b_text, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            changed_lines += (i2 - i1) + (j2 - j1)
            a_changed.update(range(i1 + 1, i2 + 1))
            b_changed.update(range(j1 + 1, j2 + 1))
        differing[rel] = (a_changed, b_changed)
    return files_touched, changed_lines, differing


class FixtureIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.cases = (
            sorted(p for p in CASES_DIR.iterdir() if not p.name.startswith("."))
            if CASES_DIR.exists()
            else []
        )
        self.assertTrue(self.cases, f"no fixtures found under {CASES_DIR}")

    def _case_json(self, case_dir: Path) -> dict:
        path = case_dir / "case.json"
        self.assertTrue(path.exists(), f"{case_dir.name}: missing case.json")
        return json.loads(path.read_text())

    def _trees_dir(self, case_dir: Path, case: dict) -> Path:
        return CASES_DIR / case.get("fixture_from", case_dir.name)

    def test_case_json_shape(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            with self.subTest(case=case_dir.name):
                for key in ("agent", "variants", "expected", "allowed"):
                    self.assertIn(key, case, f"{case_dir.name}: case.json missing {key!r}")
                agent = case["agent"]
                self.assertTrue(
                    agent.startswith("review-flow:"),
                    f"{case_dir.name}: agent {agent!r} does not start with 'review-flow:'",
                )
                agent_file = AGENTS_DIR / f"{agent.split(':', 1)[1]}.md"
                self.assertTrue(
                    agent_file.exists(),
                    f"{case_dir.name}: no agent file at {agent_file.relative_to(ROOT)}",
                )

    def test_fixture_from(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            if "fixture_from" not in case:
                continue
            with self.subTest(case=case_dir.name):
                for own in ("base", "defect", "clean"):
                    self.assertFalse(
                        (case_dir / own).exists(),
                        f"{case_dir.name}: has its own {own}/ but also names fixture_from",
                    )
                target = CASES_DIR / case["fixture_from"]
                self.assertTrue(
                    target.is_dir(),
                    f"{case_dir.name}: fixture_from {case['fixture_from']!r} is not an existing case",
                )
                self.assertEqual(
                    case["variants"],
                    ["defect"],
                    f"{case_dir.name}: variants must be ['defect'], got {case['variants']!r}",
                )
                self.assertTrue(
                    (case_dir / "author-text.md").exists(),
                    f"{case_dir.name}: missing author-text.md",
                )

    def test_diffs_non_empty(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            trees = self._trees_dir(case_dir, case)
            with self.subTest(case=case_dir.name):
                for variant in ("defect", "clean"):
                    _, _, differing = diff_stats(trees / "base", trees / variant)
                    self.assertTrue(
                        differing,
                        f"{case_dir.name}: base->{variant} has no differing files",
                    )

    def test_diff_size(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            trees = self._trees_dir(case_dir, case)
            with self.subTest(case=case_dir.name):
                files_touched, changed_lines, _ = diff_stats(trees / "base", trees / "defect")
                self.assertTrue(
                    3 <= files_touched <= 5,
                    f"{case_dir.name}: base->defect touches {files_touched} files, want 3-5",
                )
                self.assertTrue(
                    80 <= changed_lines <= 150,
                    f"{case_dir.name}: base->defect changes {changed_lines} lines, want 80-150",
                )

    def test_twin_differs_only_in_defect_zone(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            trees = self._trees_dir(case_dir, case)
            with self.subTest(case=case_dir.name):
                _, _, differing = diff_stats(trees / "defect", trees / "clean")
                self.assertTrue(
                    differing,
                    f"{case_dir.name}: defect and clean trees do not differ",
                )
                points = case["expected"]["any_of"]
                stray = []
                for rel, (defect_lines, clean_lines) in differing.items():
                    ranges = [p for p in points if p["file"] == rel]
                    for lineno in sorted(defect_lines | clean_lines):
                        if not any(r["lines"][0] <= lineno <= r["lines"][1] for r in ranges):
                            stray.append(f"{rel}:{lineno}")
                self.assertFalse(
                    stray,
                    f"{case_dir.name}: lines outside expected.any_of ranges: {', '.join(stray)}",
                )

    def test_expectation_points_exist(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            trees = self._trees_dir(case_dir, case)
            with self.subTest(case=case_dir.name):
                for point in case["expected"]["any_of"] + case["allowed"]:
                    target = trees / "defect" / point["file"]
                    with self.subTest(point=point["file"]):
                        self.assertTrue(
                            target.exists(),
                            f"{case_dir.name}: expectation point {point['file']} missing from defect/",
                        )
                        line_count = len(target.read_text().splitlines())
                        self.assertLessEqual(
                            point["lines"][1],
                            line_count,
                            f"{case_dir.name}: {point['file']} line {point['lines'][1]} "
                            f"exceeds its {line_count} lines",
                        )

    def test_no_giveaway_words(self):
        for case_dir in self.cases:
            case = self._case_json(case_dir)
            trees = self._trees_dir(case_dir, case)
            with self.subTest(case=case_dir.name):
                offenders = []
                for variant in ("base", "defect", "clean"):
                    for path in list_files(trees / variant):
                        rel = path.relative_to(trees).as_posix()
                        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
                            if GIVEAWAY_RE.search(line):
                                offenders.append(f"{rel}:{lineno}")
                self.assertFalse(
                    offenders,
                    f"{case_dir.name}: giveaway words found at {', '.join(offenders)}",
                )


if __name__ == "__main__":
    unittest.main()
