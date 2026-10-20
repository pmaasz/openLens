#!/usr/bin/env python3
"""Documentation has one source of truth: the Sphinx tree (#568).

``docs/`` carried overlapping Markdown duplicates: three feature/project status
snapshots, two ray-tracing pages (one already saying it was migrated), and the
Nikon prescription note that the Sphinx tree did not have. They duplicated the
RST pages, drifted, and had to be edited twice.

These tests pin the consolidation: the redundant files stay deleted, every
remaining Markdown file is accounted for in ``docs/README.md``, the policy is
stated, and the Nikon example lives in the Sphinx tree and is linked from the
seeder.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
SPHINX = DOCS / "sphinx" / "source"

#: Redundant pages removed by the consolidation.
REMOVED = (
    "FEATURES_IMPLEMENTED.md",
    "FEATURES_SUMMARY.md",
    "PROJECT_SUMMARY.md",
    "RAY_TRACING_GUIDE.md",
    "RAYTRACING_IMPLEMENTATION.md",
    "NIKON_SERIES_E_50MM.md",
)

#: The Markdown files that remain, each with a reason in docs/README.md.
EXPECTED_MARKDOWN = {
    "README.md",
    "CONTRIBUTING.md",
    "TESTING.md",
    "ARCHITECTURE.md",
    "API_DOCUMENTATION.md",
    "FEATURE_ABERRATIONS.md",
}


class TestTheDuplicatesAreGone(unittest.TestCase):
    def test_removed_pages_stay_removed(self):
        for name in REMOVED:
            with self.subTest(name=name):
                self.assertFalse(
                    (DOCS / name).exists(),
                    f"{name} is a duplicate of the Sphinx docs and must stay gone",
                )

    def test_no_remaining_document_links_to_a_removed_page(self):
        markdown = list(DOCS.glob("*.md")) + [REPO_ROOT / "README.md"]
        for path in markdown:
            text = path.read_text(encoding="utf-8")
            for name in REMOVED:
                with self.subTest(path=path.name, name=name):
                    self.assertNotIn(name, text)


class TestEverythingIsAccountedFor(unittest.TestCase):
    def test_docs_readme_lists_every_markdown_file(self):
        present = {path.name for path in DOCS.glob("*.md")}
        self.assertEqual(
            present,
            EXPECTED_MARKDOWN,
            "docs/README.md must account for every Markdown file under docs/",
        )

    def test_docs_readme_states_the_policy(self):
        text = (DOCS / "README.md").read_text(encoding="utf-8")
        self.assertIn("source of truth", text.lower())
        self.assertIn("Do not add new Markdown files", text)

    def test_root_readme_document_links_resolve(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\((docs/[^)]+)\)", readme):
            with self.subTest(target=target):
                self.assertTrue((REPO_ROOT / target).exists(), f"README links to missing {target}")


class TestTheNikonExampleMovedToSphinx(unittest.TestCase):
    def test_the_page_exists_and_is_in_a_toctree(self):
        page = SPHINX / "nikon_series_e_50mm.rst"
        self.assertTrue(page.is_file(), "the Nikon prescription page is missing")
        self.assertIn("nikon_series_e_50mm", (SPHINX / "index.rst").read_text(encoding="utf-8"))

    def test_the_seeder_points_at_the_sphinx_page(self):
        seed_data = (REPO_ROOT / "openlens" / "seed_data.py").read_text(encoding="utf-8")
        self.assertIn("nikon_series_e_50mm.rst", seed_data)
        self.assertNotIn("NIKON_SERIES_E_50MM.md", seed_data)


if __name__ == "__main__":
    unittest.main()
