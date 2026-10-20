#!/usr/bin/env python3
"""The type-hint contract is actually checked (#550).

AGENTS.md requires type hints on every signature, but nothing verified them:
an ``Optional`` used without a ``None`` check stayed invisible until runtime.
mypy now runs in the lint job with a lenient configuration - third-party
imports are skipped and the modules that still carry a pre-existing error
baseline are listed one by one with ``ignore_errors``.

The list in ``mypy.ini`` is a burn-down baseline, not a dumping ground. These
tests pin that it stays per-module, that every entry names a real module, that
the configuration does not silence the whole package, and that both the dev
extra and the lint job actually invoke mypy.
"""

import configparser
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MYPY_INI = REPO_ROOT / "mypy.ini"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SETUP_PY = REPO_ROOT / "setup.py"


class TestMyPyConfiguration(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MYPY_INI.is_file(), "mypy.ini is missing")
        self.config = configparser.ConfigParser()
        self.config.read(MYPY_INI)

    def test_it_checks_the_package_leniently(self):
        self.assertIn("mypy", self.config)
        section = self.config["mypy"]
        self.assertEqual(section["files"], "openlens")
        self.assertTrue(section.getboolean("ignore_missing_imports"))
        self.assertNotIn("ignore_errors", section, "the whole package must not be silenced")
        self.assertNotIn("disable_error_code", section)

    def test_burn_down_entries_are_real_modules(self):
        entries = [name for name in self.config.sections() if name.startswith("mypy-")]
        self.assertTrue(entries, "the pre-existing baseline should be recorded, not hidden")

        for section in entries:
            with self.subTest(section=section):
                self.assertTrue(section.startswith("mypy-openlens."))
                self.assertNotIn("*", section, "exclusions must name a module, not a subtree")
                self.assertTrue(self.config[section].getboolean("ignore_errors"))

                module = section[len("mypy-") :]
                base = REPO_ROOT.joinpath(*module.split("."))
                exists = base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()
                self.assertTrue(exists, f"{section} names a module that does not exist")

    def test_the_baseline_is_sorted(self):
        modules = [name for name in self.config.sections() if name.startswith("mypy-")]
        self.assertEqual(modules, sorted(modules))


class TestTheGateRuns(unittest.TestCase):
    def test_the_dev_extra_installs_mypy(self):
        setup_py = SETUP_PY.read_text(encoding="utf-8")
        dev_extra = re.search(r"['\"]dev['\"]:\s*\[(.*?)\n\s*\],", setup_py, re.DOTALL)
        self.assertIsNotNone(dev_extra, "no dev extras block in setup.py")
        self.assertIn("mypy==", dev_extra.group(1))

    def test_the_lint_job_runs_mypy(self):
        ci = CI.read_text(encoding="utf-8")
        self.assertIn("Type checking (mypy)", ci)
        self.assertRegex(ci, r"(?m)^\s+run:\s*mypy\s*$")


if __name__ == "__main__":
    unittest.main()
