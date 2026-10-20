#!/usr/bin/env python3
"""MANIFEST.in must describe the source tree, not a developer's working copy (#567).

``recursive-include data *.json`` pointed at a gitignored directory. In a clean
checkout it matches nothing, so an sdist shipped no material catalog at all; on
a developer machine it shipped that developer's ``data/materials.json`` (test
materials included). The runtime does not need it: built-in materials are always
loaded, and the writable catalog lives in the user data directory. The checkout
file remains only as a one-time migration source.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "MANIFEST.in"
GITIGNORE = REPO_ROOT / ".gitignore"

#: ``include foo`` / ``recursive-include foo *.json``; captures the target.
_INCLUDE = re.compile(r"^(?:recursive-)?include\s+(\S+)")


def _gitignored_directories():
    """Top-level directories ignored by git, without the trailing slash."""
    ignored = set()
    for line in GITIGNORE.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or entry.startswith("!"):
            continue
        if entry.endswith("/") and "/" not in entry.rstrip("/"):
            ignored.add(entry.rstrip("/"))
    return ignored


class TestManifestMatchesTheSourceTree(unittest.TestCase):
    def test_no_include_targets_a_gitignored_directory(self):
        """A release must not depend on files that are not in the repository."""
        ignored = _gitignored_directories()
        self.assertIn("data", ignored, "this test's premise: data/ is gitignored")

        for line_number, line in enumerate(
            MANIFEST.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = _INCLUDE.match(line.strip())
            if match is None:
                continue
            target = match.group(1).rstrip("/")
            with self.subTest(line=line_number, target=target):
                self.assertNotIn(
                    target,
                    ignored,
                    f"MANIFEST.in:{line_number} packages gitignored {target}/, "
                    "so the sdist depends on local files",
                )

    def test_the_stale_setup_verifier_is_not_referenced(self):
        """``verify_setup.py`` no longer exists; the manifest must not miss it."""
        self.assertFalse((REPO_ROOT / "verify_setup.py").exists())
        self.assertNotIn(
            "verify_setup",
            MANIFEST.read_text(encoding="utf-8"),
            "MANIFEST.in still lists a setup verifier that is not in the tree",
        )


if __name__ == "__main__":
    unittest.main()
