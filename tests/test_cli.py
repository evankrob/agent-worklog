"""The worklog command."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


def _run(args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "worklog", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class CliTests(unittest.TestCase):
    def test_help_and_demo_build(self):
        help_run = _run(["--help"], ROOT)
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("extract", help_run.stdout)
        self.assertIn("serve", help_run.stdout)
        with TemporaryDirectory() as tmp:
            demo = _run(["demo", "--dir", tmp], ROOT)
            self.assertEqual(demo.returncode, 0, demo.stderr + demo.stdout)
            index = Path(tmp) / "site" / "index.html"
            self.assertTrue(index.is_file(), demo.stdout + demo.stderr)
            html = index.read_text(encoding="utf-8")
            self.assertIn("Agent Team Work Log", html)
            self.assertNotIn("UNIQUE_TOOL_BODY_DO_NOT_PUBLISH_9f3c", html)
            again = _run(["build", "-c", str(Path(tmp) / "worklog.toml")], ROOT)
            self.assertEqual(again.returncode, 0, again.stderr)
            missing = _run(["build"], ROOT)
            # The repo root has no worklog.toml until the demo is generated there.
            if not (ROOT / "worklog.toml").exists():
                self.assertEqual(missing.returncode, 1)
                self.assertIn("worklog.toml", missing.stderr)

    def test_bad_config_is_a_clean_error(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "worklog.toml"
            path.write_text('days = "nope"\n', encoding="utf-8")
            result = _run(["build", "-c", str(path)], ROOT)
            self.assertEqual(result.returncode, 1)
            self.assertIn("days", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
