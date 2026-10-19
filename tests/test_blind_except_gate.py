"""#479: the blind-except gate must stay green.

``ruff.toml`` selects BLE001 (blind ``except Exception``) for the library
and the tests. GUI/CLI event boundaries are exempt as deliberate, and the
files still carrying pre-existing broad handlers are listed as the #479
burn-down baseline; this test fails if a new blind handler shows up
anywhere else.
"""

import os
import shutil
import subprocess
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestBlindExceptGate(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ruff"), "ruff is not installed")
    def test_no_new_blind_except_handlers(self):
        """Only the documented exemptions may contain `except Exception`."""
        result = subprocess.run(
            ["ruff", "check", "--select", "BLE001", "openlens", "tests"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
