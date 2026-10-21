#!/usr/bin/env python3
"""Documentation structure and freshness checks (#285).

The Sphinx tree is the source of truth. These tests pin the three top-level
audiences - users, developers, and readers interested in the physics - and
guard the architecture pages against drifting back to the pre-PySide6/Tkinter
and JSON-library era.
"""

import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPHINX = REPO_ROOT / "docs" / "sphinx" / "source"


def _toctree_entries(path):
    """Yield the docname entries of every ``toctree`` directive in *path*."""
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip() != ".. toctree::":
            index += 1
            continue
        index += 1
        while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
            entry = lines[index].strip()
            if entry and not entry.startswith(":"):
                yield entry
            index += 1


def _python_blocks(path):
    """Yield the source of every ``.. code-block:: python`` in *path*."""
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip() != ".. code-block:: python":
            index += 1
            continue
        index += 1
        block = []
        while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
            block.append(lines[index])
            index += 1
        yield textwrap.dedent("\n".join(block))


class TestDocumentationIsDividedByAudience(unittest.TestCase):
    def test_index_has_the_three_audience_sections(self):
        index = (SPHINX / "index.rst").read_text(encoding="utf-8")

        self.assertIn("User Documentation", index)
        self.assertIn("Technical Documentation", index)
        self.assertIn("Scientific Documentation", index)

    def test_scientific_section_has_an_index_and_pages(self):
        self.assertIn("scientific/index", (SPHINX / "index.rst").read_text(encoding="utf-8"))
        for name in ("index.rst", "optics.rst", "image_quality.rst", "thermal_mechanical.rst"):
            with self.subTest(name=name):
                self.assertTrue((SPHINX / "scientific" / name).is_file())

    def test_scientific_index_links_every_scientific_page(self):
        index = (SPHINX / "scientific" / "index.rst").read_text(encoding="utf-8")
        for name in ("optics", "image_quality", "thermal_mechanical"):
            with self.subTest(name=name):
                self.assertIn(name, index)


class TestToctreesAreCurrent(unittest.TestCase):
    def test_every_toctree_entry_resolves_to_an_rst_page(self):
        for page in sorted(SPHINX.rglob("*.rst")):
            for entry in _toctree_entries(page):
                target = (page.parent / entry).with_suffix(".rst").resolve()
                with self.subTest(page=page.relative_to(SPHINX).as_posix(), entry=entry):
                    self.assertTrue(target.is_file(), f"missing toctree target {target}")


class TestCodeExamplesAreValidPython(unittest.TestCase):
    def test_python_code_blocks_compile(self):
        for page in sorted(SPHINX.rglob("*.rst")):
            for number, source in enumerate(_python_blocks(page), start=1):
                with self.subTest(page=page.relative_to(SPHINX).as_posix(), block=number):
                    try:
                        compile(source, str(page), "exec")
                    except SyntaxError as exc:
                        self.fail(f"invalid Python in {page}: {exc}")


class TestDocumentationMatchesTheCurrentApplication(unittest.TestCase):
    def test_pages_do_not_describe_the_retired_tkinter_gui(self):
        for name in ("index.rst", "getting_started.rst", "contributing.rst", "architecture.rst"):
            text = (SPHINX / name).read_text(encoding="utf-8").lower()
            with self.subTest(name=name):
                self.assertNotIn("tkinter", text)
                self.assertNotIn("lens_editor_gui.py", text)

    def test_architecture_names_the_current_layers(self):
        text = (SPHINX / "architecture.rst").read_text(encoding="utf-8")

        self.assertIn("PySide6", text)
        self.assertIn("SQLite", text)
        self.assertIn("openlens/gui/", text)
        self.assertIn("DatabaseManager", text)
        self.assertNotIn("lenses.json", text)

    def test_contributing_uses_the_real_test_and_setup_commands(self):
        text = (SPHINX / "contributing.rst").read_text(encoding="utf-8")

        self.assertIn("python3 -m unittest discover -s tests -t .", text)
        self.assertIn("pip install -e .[dev]", text)
        self.assertNotIn("tests/run_all_tests.py", text)
        self.assertNotIn("verify_setup.py", text)

    def test_examples_use_the_current_lens_constructor(self):
        for name in ("getting_started.rst", "user_guide.rst"):
            text = (SPHINX / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("radius_of_curvature_1", text)
                self.assertNotIn("radius_1=", text)
                self.assertNotIn("radius_2=", text)


if __name__ == "__main__":
    unittest.main()
