import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RpoFlagTests(unittest.TestCase):
    def test_non_positive_hours_are_rejected(self):
        for bad in ("0", "-48", "x"):
            r = subprocess.run([sys.executable, "-m", "backupattest", "coverage",
                                "--manifest", "samples/manifest.txt", "--rpo-hours", bad],
                               cwd=str(ROOT), capture_output=True, text=True,
                               env={**os.environ, "PYTHONPATH": "src"})
            self.assertNotEqual(r.returncode, 0, (bad, r.stdout, r.stderr))
            self.assertIn("rpo-hours", r.stderr, (bad, r.stderr))


if __name__ == "__main__":
    unittest.main()
