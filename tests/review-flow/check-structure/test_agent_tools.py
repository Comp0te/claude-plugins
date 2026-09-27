"""Tests for scripts/check-structure.py's review-flow agent tools guard."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("check_structure", ROOT / "scripts/check-structure.py")
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


class AgentToolsGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def agent(self, name, tools_block):
        path = self.dir / f"{name}.md"
        path.write_text(f"---\nname: {name}\ndescription: d\n{tools_block}---\n\nbody\n")
        return path

    def problems(self, *paths):
        out = []
        cs.check_agent_tools(out, paths)
        return out

    def test_comma_form_parsed(self):
        path = self.agent("a", "tools: Read, Grep, Bash\n")
        self.assertEqual(cs.agent_tools(path), ["Read", "Grep", "Bash"])

    def test_block_form_parsed(self):
        path = self.agent("a", "tools:\n  - Read\n  - Bash\n")
        self.assertEqual(cs.agent_tools(path), ["Read", "Bash"])

    def test_reviewer_with_read_only_tools_and_bash_passes(self):
        self.assertEqual(self.problems(self.agent("deletion-check", "tools: Read, Grep, Glob, Bash\n")), [])

    def test_missing_tools_fails(self):
        problems = self.problems(self.agent("a", ""))
        self.assertEqual(len(problems), 1)
        self.assertIn("no tools field", problems[0])

    def test_write_edit_agent_fail_in_either_form(self):
        comma = self.agent("a", "tools: Read, Write, Edit\n")
        block = self.agent("b", "tools:\n  - Read\n  - Agent\n")
        problems = self.problems(comma, block)
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("Write" in p for p in problems))
        self.assertTrue(any("Edit" in p for p in problems))
        self.assertTrue(any("Agent" in p for p in problems))

    def test_bash_forbidden_only_for_verifiers(self):
        gate = self.agent("finding-gate-verifier", "tools:\n  - Read\n  - Bash\n")
        fix = self.agent("fix-verifier", "tools: Read, Bash\n")
        problems = self.problems(gate, fix)
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("Bash" in p for p in problems))

    def test_repository_agents_pass(self):
        self.assertEqual(self.problems(*sorted((ROOT / "plugins/review-flow/agents").glob("*.md"))), [])


if __name__ == "__main__":
    unittest.main()
