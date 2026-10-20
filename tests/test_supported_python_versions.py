#!/usr/bin/env python3
"""Supported Python versions are stated once and consistently (#569).

`setup.py` already asks for 3.10+, and CI exercises 3.10, 3.11 and 3.12, but
the README (badge, prerequisites, verification step), AGENTS.md, requirements
and several docs still advertised 3.6/3.7. This scan keeps the documents from
drifting from the packaging metadata again.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Documents that state (or used to state) an install requirement.
DOC_FILES = (
    "README.md",
    "AGENTS.md",
    "requirements.txt",
    "docs/CONTRIBUTING.md",
    "docs/API_DOCUMENTATION.md",
    "docs/sphinx/source/contributing.rst",
    "docs/sphinx/source/getting_started.rst",
)

#: "Python 3.7", "python-3.7+", "**Python:** 3.6+" - anything that attaches an
#: unsupported 3.x version to the word Python.
STALE_CLAIM = re.compile(r"(?i)python[^\n]{0,20}?3\.(?:6|7|8|9)")

SUPPORTED_MINIMUM = "3.10"
CI_VERSIONS = ("3.10", "3.11", "3.12")


class TestSupportedPythonVersions(unittest.TestCase):
    """The docs and the packaging metadata agree on 3.10+."""

    def test_no_document_claims_an_untested_python(self):
        for relative in DOC_FILES:
            path = REPO_ROOT / relative
            with self.subTest(path=relative):
                self.assertTrue(path.is_file(), f"{relative} is missing")
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    match = STALE_CLAIM.search(line)
                    if match is not None:
                        self.fail(f"{relative}:{line_number} still claims {match.group(0)!r}")

    def test_setup_declares_the_minimum(self):
        setup_py = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")
        self.assertRegex(
            setup_py,
            rf"python_requires\s*=\s*['\"]>={re.escape(SUPPORTED_MINIMUM)}['\"]",
        )

    def test_ci_exercises_the_advertised_versions(self):
        workflows = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml")
        )
        for version in CI_VERSIONS:
            with self.subTest(version=version):
                self.assertIn(f'"{version}"', workflows)

    def test_readme_names_setup_as_the_authority(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(SUPPORTED_MINIMUM, readme)
        self.assertIn("`python_requires` in `setup.py`", readme)

    def test_sphinx_install_pages_name_the_supported_version(self):
        for relative in (
            "docs/sphinx/source/getting_started.rst",
            "docs/sphinx/source/contributing.rst",
        ):
            with self.subTest(path=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn(SUPPORTED_MINIMUM, text)


if __name__ == "__main__":
    unittest.main()
