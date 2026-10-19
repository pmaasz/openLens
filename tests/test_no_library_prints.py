"""#478: library code logs, it does not print.

The CLI (``lens_editor``) and the GUI entry point print for the user, and
``dependencies.print_dependency_status`` is a presentation helper by name.
Every other module under ``openlens/`` must use a logger: a print in library
code is invisible in the GUI and never reaches the log file.
"""

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "openlens"

#: Front-ends and the presentation helper keep their prints, by design.
EXEMPT = {
    "lens_editor.py",  # interactive CLI: the terminal is the UI
    "__main__.py",  # --version / --help before Qt starts
    "dependencies.py",  # print_dependency_status() exists to print a report
}


def print_calls(path: Path):
    """Return the line numbers of print() calls in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


class TestNoLibraryPrints(unittest.TestCase):
    def test_library_modules_do_not_print(self):
        offenders = []
        for path in sorted(PACKAGE_ROOT.rglob("*.py")):
            relative = path.relative_to(PACKAGE_ROOT).as_posix()
            if relative in EXEMPT:
                continue
            for lineno in print_calls(path):
                offenders.append(f"openlens/{relative}:{lineno}")

        self.assertEqual(
            offenders,
            [],
            "library code prints instead of logging: " + ", ".join(offenders),
        )

    def test_the_scan_can_see_a_print(self):
        """Canary: a broken scan must not let the gate pass silently."""
        self.assertTrue(print_calls(PACKAGE_ROOT / "lens_editor.py"))


class TestExamplesCompile(unittest.TestCase):
    def test_moved_examples_compile(self):
        examples = sorted((REPO_ROOT / "examples").glob("*_demo.py"))
        self.assertTrue(examples, "no example demos found")
        for path in examples:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")


if __name__ == "__main__":
    unittest.main()
