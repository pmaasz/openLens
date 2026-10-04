#!/usr/bin/env python3
"""
OpenLens must start without matplotlib.

AGENTS.md classes matplotlib as optional: "the app must start and run core
features without them". But `src/gui/dialogs/__init__.py` imported
AnalysisPlotDialog at module scope, and `openlens.py` imported it from there
at module scope too. On a clean `pip install PySide6` the app therefore died
during startup with a raw ModuleNotFoundError - no editor, no message - even
though the lens editor, assembly builder and the QPainter-based 2D/3D
visualisations need no matplotlib at all.

`src/gui/__init__.py` already wrapped its imports in try/except ImportError,
which made the codebase look compliant, but that guard was dead weight:
openlens.py imports the submodules directly.

matplotlib is blocked in a subprocess, since removing an already-imported
module from sys.meta_path mid-process is unreliable.
"""

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_BLOCKER = """
import sys


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("No module named 'matplotlib' (simulated)")
        return None


sys.meta_path.insert(0, _Blocker())
try:
    import matplotlib
except ImportError:
    pass
else:
    raise SystemExit("blocker failed")
"""


def _run_without_matplotlib(body):
    """Run ``body`` in a subprocess where importing matplotlib raises."""
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run(
        [sys.executable, "-c", _BLOCKER + body],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=REPO_ROOT,
        env=env,
    )


class TestAppStartsWithoutMatplotlib(unittest.TestCase):
    def test_openlens_entry_point_imports(self):
        """Regression: the headline symptom was a startup crash."""
        result = _run_without_matplotlib(
            "import openlens; print('OK', openlens.OpenLensWindow.__name__)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK OpenLensWindow", result.stdout)

    def test_dialogs_package_imports(self):
        result = _run_without_matplotlib(
            "import src.gui.dialogs as d; print('OK', d.ANALYSIS_PLOTS_AVAILABLE)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK False", result.stdout)

    def test_startup_dialog_is_still_available(self):
        """The dialog that does not need matplotlib must survive."""
        result = _run_without_matplotlib(
            "from src.gui.dialogs import StartupDialog; print('OK', StartupDialog.__name__)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK StartupDialog", result.stdout)

    def test_requester_raises_an_actionable_import_error(self):
        result = _run_without_matplotlib(
            "from src.gui.dialogs import require_analysis_plot_dialog\n"
            "try:\n"
            "    require_analysis_plot_dialog()\n"
            "except ImportError as e:\n"
            "    print('RAISED', e)\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RAISED", result.stdout)
        self.assertIn("matplotlib", result.stdout)

    def test_no_module_scope_matplotlib_import_in_openlens(self):
        """A static guard, so the eager import cannot creep back in."""
        with open(os.path.join(REPO_ROOT, "openlens.py"), encoding="utf-8") as f:
            source = f.read()
        eager = [
            line
            for line in source.splitlines()
            if line.startswith(("import matplotlib", "from matplotlib"))
        ]
        self.assertEqual(eager, [], "openlens.py must not import matplotlib at module scope")

    def test_dialogs_package_guards_the_plot_import(self):
        with open(
            os.path.join(REPO_ROOT, "src", "gui", "dialogs", "__init__.py"),
            encoding="utf-8",
        ) as f:
            source = f.read()
        self.assertIn("except ImportError", source)
        self.assertIn("ANALYSIS_PLOTS_AVAILABLE", source)


class TestWithMatplotlibPresent(unittest.TestCase):
    """The normal path must be unaffected."""

    def test_requester_returns_the_class(self):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            self.skipTest("matplotlib not installed")
        from src.gui.dialogs import ANALYSIS_PLOTS_AVAILABLE, require_analysis_plot_dialog

        self.assertTrue(ANALYSIS_PLOTS_AVAILABLE)
        self.assertIs(require_analysis_plot_dialog().__name__.split(".")[-1], "AnalysisPlotDialog")

    def test_openlens_imports_normally(self):
        result = subprocess.run(
            [sys.executable, "-c", "import openlens; print('OK')"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONPATH": REPO_ROOT, "QT_QPA_PLATFORM": "offscreen"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
