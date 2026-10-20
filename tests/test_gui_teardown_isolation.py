#!/usr/bin/env python3
"""Regression for #557: the small GUI combination must survive one process.

Running just these three modules used to end in SIGSEGV during interpreter
shutdown (or, environment-dependent, in a failing worker-payload test). Each
module created its own QApplication in a module global and waited on
``isFinished()`` rather than on the queued payload signal, so Qt was torn down
around live widgets and the worker signal could arrive after the assertion.

The suite now shares one QApplication (``tests.ensure_qapp``) that outlives the
test modules, and flushes pending deletions before shutdown. This test runs the
issue's exact command in a child process so the combination is exercised the
way a developer hits it - not through the discover run, which happened to keep
enough state alive to hide the crash.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MODULES = (
    "tests.test_performance_tab_async",
    "tests.test_performance_tab_stale_metrics",
    "tests.test_analysis_async_dialog",
)


class TestTheSmallGuiCombination(unittest.TestCase):
    def test_the_three_modules_run_in_one_process(self):
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *MODULES],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        self.assertNotIn("Segmentation fault", output)
        self.assertEqual(
            result.returncode,
            0,
            "the GUI modules crashed or failed when run together:\n" + output[-4000:],
        )


if __name__ == "__main__":
    unittest.main()
