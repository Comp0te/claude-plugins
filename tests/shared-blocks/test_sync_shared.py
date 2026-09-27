"""Tests for scripts/sync-shared.py's sync().

One test per row of the plan's I/O & Edge-Case Matrix (Task 1).
"""
import importlib.util
import json
import pathlib
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "sync_shared", REPO_ROOT / "scripts/sync-shared.py"
)
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)

BODY = "Shared paragraph one.\n\nShared paragraph two."


def _write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _block(name, body=BODY):
    begin, end = ss._markers(name)
    return f"{begin}\n\n{body}\n\n{end}"


class SyncSharedTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name)
        (self.root / "plugins").mkdir()
        (self.root / "shared").mkdir()

    def _manifest(self, manifest):
        _write(self.root, "shared/blocks.json", json.dumps(manifest))

    def test_in_sync(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        _write(self.root, "plugins/a.md", f"front\n\n{_block('demo')}\n\ntail\n")

        problems = ss.sync(self.root, check=True)

        self.assertEqual(problems, [])

    def test_drifted(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        _write(self.root, "plugins/a.md", f"front\n\n{_block('demo', 'Old text.')}\n\ntail\n")

        problems = ss.sync(self.root, check=True)

        self.assertEqual(problems, ["out of sync: plugins/a.md [demo]"])

    def test_sync_writes_only_the_marked_region(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        target = _write(self.root, "plugins/a.md", f"front\n\n{_block('demo', 'Old text.')}\n\ntail\n")

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, [])
        begin, end = ss._markers("demo")
        self.assertEqual(
            target.read_text(),
            f"front\n\n{begin}\n\n{BODY}\n\n{end}\n\ntail\n",
        )

    def test_missing_source(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        target = _write(self.root, "plugins/a.md", f"front\n\n{_block('demo')}\n\ntail\n")
        before = target.read_text()

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, ["source missing or empty: shared/demo.md"])
        self.assertEqual(target.read_text(), before)

    def test_missing_target(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/missing.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, ["target missing: plugins/missing.md"])
        self.assertFalse((self.root / "plugins/missing.md").exists())

    def test_markers_absent(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        target = _write(self.root, "plugins/a.md", "front\n\nno markers here\n\ntail\n")
        before = target.read_text()

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, ["markers missing: plugins/a.md [demo]"])
        self.assertEqual(target.read_text(), before)

    def test_markers_duplicated(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        begin, end = ss._markers("demo")
        target = _write(
            self.root,
            "plugins/a.md",
            f"front\n\n{begin}\n\n{BODY}\n\n{end}\n\n{begin}\n\n{BODY}\n\n{end}\n\ntail\n",
        )
        before = target.read_text()

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, ["markers duplicated: plugins/a.md [demo]"])
        self.assertEqual(target.read_text(), before)

    def test_markers_unbalanced(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        begin, end = ss._markers("demo")
        target = _write(self.root, "plugins/a.md", f"front\n\n{end}\n\n{BODY}\n\n{begin}\n\ntail\n")
        before = target.read_text()

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, ["markers unbalanced: plugins/a.md [demo]"])
        self.assertEqual(target.read_text(), before)

    def test_orphan_markers(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        begin, end = ss._markers("demo")
        ghost_begin, ghost_end = ss._markers("ghost")
        target = _write(
            self.root,
            "plugins/a.md",
            f"front\n\n{begin}\n\n{BODY}\n\n{end}\n\n{ghost_begin}\n\nstray\n\n{ghost_end}\n\ntail\n",
        )
        before = target.read_text()

        problems = ss.sync(self.root, check=False)

        self.assertEqual(problems, ["unlisted block: plugins/a.md [ghost]"])
        self.assertEqual(target.read_text(), before)

    def test_two_blocks_one_file_synced_independently(self):
        self._manifest(
            {
                "alpha": {"source": "shared/alpha.md", "targets": ["plugins/a.md"]},
                "beta": {"source": "shared/beta.md", "targets": ["plugins/a.md"]},
            }
        )
        _write(self.root, "shared/alpha.md", "Alpha body.\n")
        _write(self.root, "shared/beta.md", "Beta body.\n")
        target = _write(
            self.root,
            "plugins/a.md",
            f"front\n\n{_block('alpha', 'Alpha body.')}\n\nmid\n\n{_block('beta', 'Old beta.')}\n\ntail\n",
        )

        problems = ss.sync(self.root, check=True)
        self.assertEqual(problems, ["out of sync: plugins/a.md [beta]"])

        problems = ss.sync(self.root, check=False)
        self.assertEqual(problems, [])

        alpha_begin, alpha_end = ss._markers("alpha")
        beta_begin, beta_end = ss._markers("beta")
        self.assertEqual(
            target.read_text(),
            (
                f"front\n\n{alpha_begin}\n\nAlpha body.\n\n{alpha_end}"
                f"\n\nmid\n\n{beta_begin}\n\nBeta body.\n\n{beta_end}\n\ntail\n"
            ),
        )
        self.assertEqual(ss.sync(self.root, check=True), [])

    def test_idempotent(self):
        self._manifest({"demo": {"source": "shared/demo.md", "targets": ["plugins/a.md"]}})
        _write(self.root, "shared/demo.md", BODY + "\n")
        target = _write(self.root, "plugins/a.md", f"front\n\n{_block('demo', 'Old text.')}\n\ntail\n")

        self.assertEqual(ss.sync(self.root, check=False), [])
        first = target.read_text()
        self.assertEqual(ss.sync(self.root, check=False), [])
        second = target.read_text()

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
