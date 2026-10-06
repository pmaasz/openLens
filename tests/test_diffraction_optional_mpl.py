#!/usr/bin/env python3
"""
diffraction.py's plot_* methods must honour the matplotlib availability flag.

The module sets the flag at import time:

    try:
        import matplotlib.pyplot as plt
        MATPLOTLIB_AVAILABLE = True
    except ImportError:
        MATPLOTLIB_AVAILABLE = False

but never consulted it. plot_airy_disk, plot_psf_2d and plot_encircled_energy
went straight to plt.figure / plt.subplots, so without matplotlib all three
raised:

    NameError: name 'plt' is not defined

That violates the AGENTS.md rule that the app must run its core features
without optional dependencies. Every other reviewed module guards - see
PolarizationCalculator.plot_fresnel_curves, which checks HAS_MATPLOTLIB.

The three methods now warn and return, leaving the numerical API (Airy radius,
encircled energy, point spread function) fully usable.
"""

import subprocess
import sys
import textwrap
import unittest

BLOCKER = """
import sys


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("No module named 'matplotlib' (simulated)")
        return None


sys.meta_path.insert(0, _Blocker())
"""

PLOT_METHODS = ("plot_airy_disk", "plot_psf_2d", "plot_encircled_energy")


def _run_without_matplotlib(body):
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.run(
        [sys.executable, "-c", BLOCKER + textwrap.dedent(body)],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


class TestWithoutMatplotlib(unittest.TestCase):
    """Driven in a subprocess: removing a live module is unreliable."""

    def test_flag_is_false(self):
        result = _run_without_matplotlib("""
            from src.diffraction import MATPLOTLIB_AVAILABLE
            print('FLAG', MATPLOTLIB_AVAILABLE)
            """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FLAG False", result.stdout)

    def test_plot_methods_do_not_raise(self):
        """Regression: NameError: name 'plt' is not defined."""
        result = _run_without_matplotlib("""
            from src.diffraction import DiffractionCalculator
            c = DiffractionCalculator()
            for name in %r:
                try:
                    getattr(c, name)(50.0, 25.0)
                    print('OK', name)
                except Exception as e:
                    print('RAISED', name, type(e).__name__, e)
            """ % (PLOT_METHODS,))
        self.assertEqual(result.returncode, 0, result.stderr)
        for method in PLOT_METHODS:
            self.assertIn("OK %s" % method, result.stdout)
        self.assertNotIn("RAISED", result.stdout)

    def test_every_plot_method_is_guarded(self):
        result = _run_without_matplotlib("""
            import inspect
            from src.diffraction import DiffractionCalculator
            for name, fn in sorted(vars(DiffractionCalculator).items()):
                if not name.startswith('plot_'):
                    continue
                src = inspect.getsource(fn)
                print('GUARDED', name, 'MATPLOTLIB_AVAILABLE' in src)
            """)
        self.assertEqual(result.returncode, 0, result.stderr)
        for method in PLOT_METHODS:
            self.assertIn("GUARDED %s True" % method, result.stdout)

    def test_numerical_api_still_works(self):
        """Only plotting is disabled, not the physics."""
        result = _run_without_matplotlib("""
            from src.diffraction import DiffractionCalculator
            c = DiffractionCalculator()
            airy = c.airy_disk_radius(50.0, 25.0)
            assert 1.34 < airy < 1.35, airy
            radii, encircled = c.encircled_energy(50.0, 25.0)
            assert len(radii) == len(encircled)
            assert abs(encircled[-1] - 1.0) < 1e-9, encircled[-1]
            psf = c.point_spread_function_2d(0.02, 50.0, 25.0)
            assert psf.size > 0
            print('NUMERIC OK')
            """)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NUMERIC OK", result.stdout)


class TestWithMatplotlib(unittest.TestCase):
    """The normal path must be unaffected."""

    def setUp(self):
        try:
            import matplotlib  # noqa: F401

            matplotlib.use("Agg")
        except ImportError:
            self.skipTest("matplotlib not installed")

    def test_flag_is_true(self):
        from src.diffraction import MATPLOTLIB_AVAILABLE

        self.assertTrue(MATPLOTLIB_AVAILABLE)

    def test_airy_plot_still_runs(self):
        import os
        import tempfile

        from src.diffraction import DiffractionCalculator

        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        DiffractionCalculator().plot_airy_disk(50.0, 25.0, save_path=path)
        self.assertGreater(os.path.getsize(path), 0)

    def test_psf_plot_still_runs(self):
        import os
        import tempfile

        from src.diffraction import DiffractionCalculator

        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        DiffractionCalculator().plot_psf_2d(50.0, 25.0, save_path=path)
        self.assertGreater(os.path.getsize(path), 0)

    def test_encircled_plot_still_runs(self):
        import os
        import tempfile

        from src.diffraction import DiffractionCalculator

        handle, path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        DiffractionCalculator().plot_encircled_energy(50.0, 25.0, save_path=path)
        self.assertGreater(os.path.getsize(path), 0)


if __name__ == "__main__":
    unittest.main()
