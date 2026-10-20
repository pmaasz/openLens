#!/usr/bin/env python3
"""The flake8/style gate must be complete and blocking (#549).

The lint job used to run flake8 twice: a blocking correctness subset
(E9/F63/F7/F82) and an advisory full run with ``--exit-zero``. 537 pre-existing
style findings therefore never failed the build, and the pre-commit action was
advisory as well.

The findings are now fixed, or recorded as justified per-file ignores in
``.flake8`` (E402 where the import order is deliberate). These tests pin the
result: the full run is the gate, there is no ``--exit-zero``, the flake8 hook
does not override the config with CLI flags, and the pre-commit action is
blocking.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLAKE8_CONFIG = REPO_ROOT / ".flake8"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PRECOMMIT = REPO_ROOT / ".pre-commit-config.yaml"


def _per_file_ignores(text):
    """Return the ``per-file-ignores`` mapping from a flake8 config."""
    lines = text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip().startswith("per-file-ignores")
        )
    except StopIteration:
        return {}

    entries = {}
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        if not line.startswith((" ", "\t")):
            break
        entry = line.strip()
        if entry.startswith("#"):
            continue
        path, codes = entry.split(":", 1)
        entries[path.strip()] = codes.strip()
    return entries


class TestTheConfig(unittest.TestCase):
    def test_the_config_file_exists(self):
        self.assertTrue(FLAKE8_CONFIG.is_file(), ".flake8 is missing")

    def test_the_project_line_length_is_preserved(self):
        text = FLAKE8_CONFIG.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^max-line-length\s*=\s*100\s*$")
        self.assertRegex(text, r"(?m)^extend-ignore\s*=.*E203")
        self.assertRegex(text, r"(?m)^extend-ignore\s*=.*W503")

    def test_only_the_deliberate_import_order_is_ignored(self):
        entries = _per_file_ignores(FLAKE8_CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(entries, "expected the tests/* E402 entry")
        self.assertEqual(entries.get("tests/*"), "E402")
        for path, codes in entries.items():
            with self.subTest(path=path):
                self.assertEqual(codes, "E402")
                if path != "tests/*":
                    self.assertTrue((REPO_ROOT / path).is_file(), f"{path} does not exist")


class TestTheGateIsBlocking(unittest.TestCase):
    def test_ci_runs_the_full_flake8(self):
        text = CI.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\s+run:\s*flake8 openlens/ tests/\s*$")
        self.assertEqual(
            len(re.findall(r"(?m)^\s+run:\s*flake8\b", text)),
            1,
            "there should be exactly one flake8 run",
        )
        self.assertNotIn("--exit-zero", text)
        self.assertNotIn("--select=E9", text)

    def test_pre_commit_is_not_advisory(self):
        text = CI.read_text(encoding="utf-8")
        block = re.search(
            r"- name: Pre-commit hooks\n(.*?)(?=\n      - name:|\n  \w|\Z)",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(block, "no pre-commit step")
        self.assertNotIn("continue-on-error", block.group(1))

    def test_the_hook_reads_the_config(self):
        text = PRECOMMIT.read_text(encoding="utf-8")
        self.assertIn("id: flake8", text)
        self.assertNotIn("--ignore", text)
        self.assertNotRegex(text, r"id: flake8\n\s+args:")

    def test_black_no_longer_excludes_the_entry_module(self):
        text = CI.read_text(encoding="utf-8")
        self.assertNotIn("--exclude", text)
        self.assertRegex(text, r"black --line-length=100 openlens/ tests/ --check")


if __name__ == "__main__":
    unittest.main()
