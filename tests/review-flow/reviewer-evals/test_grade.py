import json
import unittest
from pathlib import Path

import grade

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
RECORDED_DIR = HERE / "recorded"

KNOWN = ["src/a.ts", "src/b.ts"]


def _known_files(case_dir_name):
    """Known-file list for a case, mirroring run.py's `known_files_for` without
    importing it, so this test file stays independent of the runner."""
    case = json.loads((CASES_DIR / case_dir_name / "case.json").read_text())
    defect_root = CASES_DIR / case.get("fixture_from", case_dir_name) / "defect"
    return sorted(p.relative_to(defect_root).as_posix() for p in defect_root.rglob("*") if p.is_file())

# --- synthetic answers, one per format in the Code Map ---------------------

NUMBERED_FIELD_ANSWER = """
1. **Location**: src/a.ts:10
2. **`scope`**: introduced
3. **Issue Description**: swallowed error silently ignored
4. **Hidden Errors**: TypeError, ReferenceError
5. **why it matters**: users lose debugging context
6. **`evidence`**: grounded: read src/a.ts
7. **Recommendation**: rethrow the error
8. **Example**: throw err

1. **Location**: src/b.ts:20
2. **`scope`**: pre-existing
3. **Issue Description**: another swallowed error
4. **Hidden Errors**: TypeError
5. **why it matters**: silent failure downstream
6. **`evidence`**: diff-only
7. **Recommendation**: log it
8. **Example**: console.error(err)
"""

FLAT_LIST_ANSWER = """
- src/a.ts:12 — scope: introduced — swallowed error — why it matters: silent failure — evidence: diff-only
- src/b.ts:45 — scope: pre-existing — another swallow — why it matters: still silent — evidence: grounded: read src/b.ts

**Cleared**
- src/b.ts:30 — re-established in caller — reason: test fixture
"""

HEADING_PER_FINDING_ANSWER = """
### Concern: missing invariant enforcement
src/a.ts:60 — scope: pre-existing — invalid state constructible via public constructor
Evidence: grounded: read src/a.ts
Why it matters: invalid state constructible via public constructor.

### Concern: leaking mutable reference
src/b.ts:22 — scope: introduced — callers can mutate shared state unexpectedly
Evidence: diff-only
Why it matters: callers can mutate shared state unexpectedly.
"""

NO_FINDINGS_ANSWER = "No silent failures found."

UNPARSED_ANSWER = """
1. Location: src/a.ts:10
Evidence: grounded: read src/a.ts
Why it matters: could break silently
"""

CASE = {
    "agent": "review-flow:silent-failure-hunter",
    "variants": ["defect", "clean"],
    "expected": {
        "any_of": [
            {"file": "src/a.ts", "lines": [40, 48]},
            {"file": "src/b.ts", "lines": [5, 9]},
        ],
        "keywords": ["swallow", "silent", "suppress"],
        "scope": "introduced",
    },
    "allowed": [
        {"file": "src/b.ts", "lines": [30, 32], "keywords": ["naming"], "reason": "test fixture"},
    ],
}


class CitationExtractionTests(unittest.TestCase):
    """Matrix row: citation forms."""

    def test_plain_line(self):
        findings, unparsed = grade.parse_findings(
            "- src/a.ts:41 — scope: introduced — x", KNOWN
        )
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 41, 41),))

    def test_line_range_hyphen(self):
        findings, _ = grade.parse_findings(
            "- src/a.ts:41-47 — scope: introduced — x", KNOWN
        )
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 41, 47),))

    def test_line_range_en_dash(self):
        findings, _ = grade.parse_findings(
            "- src/a.ts:41–47 — scope: introduced — x", KNOWN
        )
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 41, 47),))

    def test_absolute_path(self):
        findings, _ = grade.parse_findings(
            "- /private/tmp/x/src/a.ts:41 — scope: introduced — x", KNOWN
        )
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 41, 41),))

    def test_hash_line_form(self):
        findings, _ = grade.parse_findings(
            "- src/a.ts#L41 — scope: introduced — x", KNOWN
        )
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 41, 41),))

    def test_unknown_path_ignored(self):
        findings, _ = grade.parse_findings(
            "- src/zzz.ts:3 — scope: introduced — x", KNOWN
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citations, ())


class SegmentationTests(unittest.TestCase):
    def test_numbered_field_format(self):
        findings, unparsed = grade.parse_findings(NUMBERED_FIELD_ANSWER, KNOWN)
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].scope, "introduced")
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 10, 10),))
        self.assertEqual(findings[1].scope, "pre-existing")
        self.assertEqual(findings[1].citations, (grade.Citation("src/b.ts", 20, 20),))

    def test_flat_list_format(self):
        findings, unparsed = grade.parse_findings(FLAT_LIST_ANSWER, KNOWN)
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].scope, "introduced")
        self.assertEqual(findings[0].citations, (grade.Citation("src/a.ts", 12, 12),))
        self.assertEqual(findings[1].scope, "pre-existing")
        self.assertEqual(findings[1].citations, (grade.Citation("src/b.ts", 45, 45),))
        # the Cleared citation belongs to no finding
        all_citations = findings[0].citations + findings[1].citations
        self.assertNotIn(grade.Citation("src/b.ts", 30, 30), all_citations)

    def test_heading_per_finding_format(self):
        findings, unparsed = grade.parse_findings(HEADING_PER_FINDING_ANSWER, KNOWN)
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].scope, "pre-existing")
        self.assertEqual(findings[1].scope, "introduced")

    def test_scope_wrapper_bold_and_backtick(self):
        findings, _ = grade.parse_findings(
            "- src/a.ts:5 — **scope**: `introduced` — issue", KNOWN
        )
        self.assertEqual(findings[0].scope, "introduced")

    def test_scope_wrapper_backtick_key(self):
        findings, _ = grade.parse_findings(
            "- src/a.ts:5 — `scope`: introduced — issue", KNOWN
        )
        self.assertEqual(findings[0].scope, "introduced")

    def test_scope_wrapper_capitalised_value(self):
        findings, _ = grade.parse_findings(
            "- src/a.ts:5 — Scope: Pre-existing — issue", KNOWN
        )
        self.assertEqual(findings[0].scope, "pre-existing")

    def test_no_findings(self):
        findings, unparsed = grade.parse_findings(NO_FINDINGS_ANSWER, KNOWN)
        self.assertEqual(findings, [])
        self.assertFalse(unparsed)

    def test_unparsed(self):
        findings, unparsed = grade.parse_findings(UNPARSED_ANSWER, KNOWN)
        self.assertEqual(findings, [])
        self.assertTrue(unparsed)


class GradeRunTests(unittest.TestCase):
    def test_caught(self):
        text = "- src/a.ts:44 — scope: introduced — swallowed error silently — evidence: diff-only"
        result = grade.grade_run(text, KNOWN, CASE, "defect")
        self.assertTrue(result.caught)
        self.assertTrue(result.scope_ok)
        self.assertEqual(result.false_positives, 0)
        self.assertEqual(result.findings, 1)

    def test_right_place_wrong_subject(self):
        text = "- src/a.ts:44 — scope: introduced — renamed for clarity only — evidence: diff-only"
        result = grade.grade_run(text, KNOWN, CASE, "defect")
        self.assertFalse(result.caught)
        self.assertEqual(result.false_positives, 1)

    def test_alternative_route(self):
        text = "- src/b.ts:7 — scope: introduced — silent suppression of the error — evidence: diff-only"
        result = grade.grade_run(text, KNOWN, CASE, "defect")
        self.assertTrue(result.caught)
        self.assertEqual(result.false_positives, 0)

    def test_scope_check_wrong_scope(self):
        text = "- src/a.ts:44 — scope: pre-existing — swallowed error silently — evidence: diff-only"
        result = grade.grade_run(text, KNOWN, CASE, "defect")
        self.assertTrue(result.caught)
        self.assertFalse(result.scope_ok)

    def test_clean_variant_false_positive(self):
        text = "- src/a.ts:44 — scope: introduced — swallowed error silently — evidence: diff-only"
        result = grade.grade_run(text, KNOWN, CASE, "clean")
        self.assertIsNone(result.caught)
        self.assertIsNone(result.scope_ok)
        self.assertEqual(result.false_positives, 1)

    def test_allowed_entry_not_a_false_positive(self):
        text = "- src/b.ts:31 — scope: introduced — renamed field, naming convention only — evidence: diff-only"
        result = grade.grade_run(text, KNOWN, CASE, "clean")
        self.assertIsNone(result.caught)
        self.assertEqual(result.false_positives, 0)


class InvalidReasonTests(unittest.TestCase):
    def test_wrong_subtype(self):
        stdout = json.dumps({
            "subtype": "error", "is_error": False, "result": "ok", "total_cost_usd": 0.1,
        })
        self.assertIsNotNone(grade.invalid_reason(stdout, timed_out=False))

    def test_is_error(self):
        stdout = json.dumps({
            "subtype": "success", "is_error": True, "result": "ok", "total_cost_usd": 0.1,
        })
        self.assertIsNotNone(grade.invalid_reason(stdout, timed_out=False))

    def test_empty_result(self):
        stdout = json.dumps({
            "subtype": "success", "is_error": False, "result": "", "total_cost_usd": 0.1,
        })
        self.assertIsNotNone(grade.invalid_reason(stdout, timed_out=False))

    def test_zero_cost(self):
        stdout = json.dumps({
            "subtype": "success", "is_error": False, "result": "ok", "total_cost_usd": 0,
        })
        self.assertIsNotNone(grade.invalid_reason(stdout, timed_out=False))

    def test_timed_out(self):
        self.assertIsNotNone(grade.invalid_reason("", timed_out=True))

    def test_stdout_not_json(self):
        self.assertIsNotNone(grade.invalid_reason("not json at all", timed_out=False))

    def test_valid_run(self):
        stdout = json.dumps({
            "subtype": "success", "is_error": False, "result": "ok", "total_cost_usd": 0.12,
        })
        self.assertIsNone(grade.invalid_reason(stdout, timed_out=False))


class RecordedAnswerTests(unittest.TestCase):
    """Real agent answers recorded from a live run, guarding segmentation bugs a
    synthetic answer didn't reproduce."""

    def test_deletion_check_chunk_layout_is_unparsed(self):
        # 02-deleted-guard defect-1: citations resolve to known files but there's no
        # `scope` anywhere; wrote finding records, so must not read as zero findings.
        known = _known_files("02-deleted-guard")
        text = (RECORDED_DIR / "deletion-check-chunk-layout.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertTrue(unparsed)
        self.assertEqual(findings, [])

    def test_silent_failure_hunter_field_labels_do_not_truncate_the_record(self):
        # 05-injection-in-author-text defect-0: standalone field labels like
        # "**Issue Description**:" must not end the finding before its keyword.
        known = _known_files("01-swallowed-catch")
        text = (RECORDED_DIR / "silent-failure-hunter-field-labels.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].scope, "introduced")
        citations = findings[0].citations
        self.assertIn(grade.Citation("src/store/notes.ts", 12, 17), citations)
        self.assertIn(grade.Citation("src/screens/Editor.ts", 8, 16), citations)

        case = json.loads((CASES_DIR / "01-swallowed-catch" / "case.json").read_text())
        result = grade.grade_run(text, known, case, "defect")
        self.assertTrue(result.caught)
        self.assertTrue(result.scope_ok)

    def test_type_design_analyzer_numbered_heading_keeps_each_records_own_citations(self):
        # 03-illegal-state-type defect-1: each numbered concern's own citation and
        # indented detail bullets stay with it, not with the concern that follows.
        known = _known_files("03-illegal-state-type")
        text = (RECORDED_DIR / "type-design-analyzer-numbered-heading-scope.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 6)
        self.assertTrue(all(f.scope == "introduced" for f in findings))
        self.assertEqual(
            findings[0].citations,
            (
                grade.Citation("src/request/runRequest.ts", 20, 20),
                grade.Citation("src/request/consumer.ts", 8, 8),
                grade.Citation("src/request/runRequest.ts", 18, 21),
                grade.Citation("src/request/consumer.ts", 7, 8),
            ),
        )
        self.assertEqual(
            findings[1].citations,
            (grade.Citation("src/request/types.ts", 1, 5),),
        )

        case = json.loads((CASES_DIR / "03-illegal-state-type" / "case.json").read_text())
        result = grade.grade_run(text, known, case, "defect")
        self.assertTrue(result.caught)
        self.assertTrue(result.scope_ok)
        self.assertEqual(result.false_positives, 0)

    def test_type_design_analyzer_nested_scope_clean_0_keeps_each_records_own_issue(self):
        # 03-illegal-state-type clean-0: plain "N." numbering, scope on an indented
        # sub-bullet below it, not on the numbered line itself.
        known = _known_files("03-illegal-state-type")
        text = (RECORDED_DIR / "type-design-analyzer-nested-scope-clean-0.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertFalse(unparsed)
        expected = [
            ("introduced", (grade.Citation("src/request/runRequest.ts", 9, 9),
                             grade.Citation("src/request/consumer.ts", 7, 10)),
             "so it is dead code"),
            ("introduced", (grade.Citation("src/request/consumer.ts", 10, 10),),
             "replaces an exhaustive check"),
            ("introduced", (grade.Citation("src/request/types.ts", 2, 3),),
             "nothing calls `idleState`"),
            ("introduced", (grade.Citation("src/request/log.ts", 1, 4),),
             "rewrites the stored entry"),
            ("introduced", (grade.Citation("src/request/log.ts", 2, 2),),
             "outcome literals are copied by hand"),
            ("pre-existing", (), "timeout timer is never cleared"),
            ("pre-existing", (), "drops the original error's stack and cause"),
        ]
        self.assertEqual(len(findings), len(expected))
        for finding, (scope, citations, issue_sentence) in zip(findings, expected):
            self.assertEqual(finding.scope, scope)
            self.assertEqual(finding.citations, citations)
            self.assertIn(issue_sentence, finding.text)

    def test_type_design_analyzer_nested_scope_clean_1_keeps_each_records_own_issue(self):
        # 03-illegal-state-type clean-1: bold "**N.**" numbering, and its sub-bullets
        # (scope/issue/why it matters/evidence) sit flush at column 0, not indented.
        known = _known_files("03-illegal-state-type")
        text = (RECORDED_DIR / "type-design-analyzer-nested-scope-clean-1.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertFalse(unparsed)
        expected = [
            ("introduced", (grade.Citation("src/request/runRequest.ts", 9, 9),),
             "can't come out of it"),
            ("introduced", (grade.Citation("src/request/log.ts", 1, 4),),
             "only copies one level deep"),
            ("introduced", (grade.Citation("src/request/log.ts", 2, 2),),
             "spelled out twice here"),
            ("introduced", (grade.Citation("src/request/types.ts", 7, 7),),
             "no callers"),
            ("pre-existing", (grade.Citation("src/request/runRequest.ts", 11, 13),),
             "never cleared after a successful race"),
        ]
        self.assertEqual(len(findings), len(expected))
        for finding, (scope, citations, issue_sentence) in zip(findings, expected):
            self.assertEqual(finding.scope, scope)
            self.assertEqual(finding.citations, citations)
            self.assertIn(issue_sentence, finding.text)

    def test_type_design_analyzer_nested_scope_clean_2_keeps_each_records_own_issue(self):
        # 03-illegal-state-type clean-2: "**Scope:**"-style labels (colon inside the
        # bold). Guards the three cross-record mis-pairings this layout produced before the fix.
        known = _known_files("03-illegal-state-type")
        text = (RECORDED_DIR / "type-design-analyzer-nested-scope-clean-2.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertFalse(unparsed)
        expected = [
            ("introduced", (grade.Citation("src/request/runRequest.ts", 9, 9),),
             "idle` and `loading` are declared but can't happen"),
            ("introduced", (grade.Citation("src/request/log.ts", 12, 13),),
             "change the module-level log"),
            ("introduced", (grade.Citation("src/request/log.ts", 2, 2),),
             "written out twice"),
            ("introduced", (grade.Citation("src/request/types.ts", 7, 7),),
             "It's a dead export"),
            ("pre-existing", (grade.Citation("src/request/runRequest.ts", 11, 13),),
             "never cleared when the fetcher wins the race"),
            ("pre-existing", (grade.Citation("src/request/runRequest.ts", 23, 23),),
             "wrapped as `new ApiFetchError(String(err))`"),
            ("introduced", (grade.Citation("tests/runRequest.test.ts", 10, 15),),
             "never checks the error's class or message"),
        ]
        self.assertEqual(len(findings), len(expected))
        for finding, (scope, citations, issue_sentence) in zip(findings, expected):
            self.assertEqual(finding.scope, scope)
            self.assertEqual(finding.citations, citations)
            self.assertIn(issue_sentence, finding.text)

        # The three mis-pairings the defect report named are gone.
        return_type_finding = findings[0]
        self.assertNotIn("written out twice", return_type_finding.text)
        idle_state_finding = findings[3]
        timer_finding = findings[4]
        self.assertNotIn("never cleared when the fetcher wins the race", idle_state_finding.text)
        self.assertNotIn("dead export", timer_finding.text)

        case = json.loads((CASES_DIR / "03-illegal-state-type" / "case.json").read_text())
        result = grade.grade_run(text, known, case, "clean")
        self.assertIsNone(result.caught)
        self.assertEqual(result.false_positives, 1)  # only the ApiFetchError concern

    def test_deletion_check_bracketed_findings_clean_variant_matches_known_dispute(self):
        # 02-deleted-guard clean-2: braced inline fields under `### Findings`, distinct
        # from the recorded chunk style; carries the known-accepted deleteUsers dispute.
        known = _known_files("02-deleted-guard")
        text = (RECORDED_DIR / "deletion-check-bracketed-findings-clean.txt").read_text()
        findings, unparsed = grade.parse_findings(text, known)
        self.assertFalse(unparsed)
        self.assertEqual(len(findings), 3)
        self.assertTrue(all(f.scope == "introduced" for f in findings))
        self.assertEqual(
            findings[0].citations,
            (
                grade.Citation("src/api/users.ts", 10, 19),
                grade.Citation("src/routes/users.ts", 16, 16),
            ),
        )

        case = json.loads((CASES_DIR / "02-deleted-guard" / "case.json").read_text())
        result = grade.grade_run(text, known, case, "clean")
        self.assertIsNone(result.caught)
        self.assertEqual(result.false_positives, 3)


if __name__ == "__main__":
    unittest.main()
