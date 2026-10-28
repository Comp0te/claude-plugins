import os, pathlib, subprocess, tempfile, unittest

SCRIPT = pathlib.Path(__file__).with_name("find-polluter.sh")


class FindPolluter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.runner = self.dir / "runner.sh"
        self.runner.write_text(
            '#!/usr/bin/env bash\n'
            'echo "$1" >> ran.log\n'
            '[ "$1" = "$POLLUTER" ] && touch artefact\n'
            '[ "$1" = "$FAILER" ] && exit 3\n'
            'exit 0\n')
        self.runner.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, polluter="", failer=""):
        env = {**os.environ, "POLLUTER": polluter, "FAILER": failer}
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.dir, env=env,
                              capture_output=True, text=True)

    def ran(self):
        log = self.dir / "ran.log"
        return log.read_text().splitlines() if log.exists() else []

    def test_polluter_found_stops_there(self):
        r = self.run_script("artefact", "./runner.sh", "a.test.ts", "b.test.ts", "c.test.ts",
                            polluter="b.test.ts")
        self.assertEqual(r.returncode, 1)
        self.assertIn("b.test.ts", r.stdout)
        self.assertEqual(self.ran(), ["a.test.ts", "b.test.ts"])

    def test_no_polluter(self):
        r = self.run_script("artefact", "./runner.sh", "a.test.ts", "b.test.ts", "c.test.ts")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no polluter among 3 files", r.stdout)

    def test_refuses_dirty_start(self):
        (self.dir / "artefact").touch()
        r = self.run_script("artefact", "./runner.sh", "a.test.ts")
        self.assertEqual(r.returncode, 2)
        self.assertIn("remove it first", r.stderr)
        self.assertEqual(self.ran(), [])

    def test_usage(self):
        r = self.run_script("artefact")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage:", r.stderr)

    def test_failing_test_is_not_a_polluter(self):
        r = self.run_script("artefact", "./runner.sh", "a.test.ts", "b.test.ts", failer="a.test.ts")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.ran(), ["a.test.ts", "b.test.ts"])

    def test_file_name_with_spaces(self):
        r = self.run_script("artefact", "./runner.sh", "a b.test.ts", polluter="a b.test.ts")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.ran(), ["a b.test.ts"])


if __name__ == "__main__":
    unittest.main()
