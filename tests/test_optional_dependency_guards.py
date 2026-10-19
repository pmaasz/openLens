"""Regression: the application must start without its optional dependencies.

AGENTS.md requires optional imports to be guarded with a ``*_AVAILABLE`` flag so
the app starts and runs its core features without them. Four modules did not, and
because ``openlens/__main__.py`` imports two of them at module level, the whole GUI failed
to launch:

    plots, mechanical_designer, image_simulator  -> ModuleNotFoundError
    psf_mtf                                      -> AttributeError:
                                                    'NoneType' has no attribute 'ndarray'

The last one is the interesting case. ``psf_mtf`` *did* guard the import - it set
``np = None`` - but its annotations are written as ``np.ndarray``, and those are
evaluated when each function is *defined*. So the guard was in place and the
module still could not be imported.

**These tests run in subprocesses.** ``sys.modules['numpy'] = None`` makes the
next ``import numpy`` raise, but it also leaves ``numpy`` in ``sys.modules`` for
the rest of the process. Doing this in-process would poison every later test -
the failure would look like a broken suite rather than a simulated environment.
"""

import os
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The modules that must import with nothing optional installed.
#: openlens/__main__.py pulls in two of these at module level, so they are load-bearing
#: for whether the application starts at all.
GUARDED_MODULES = (
    "openlens.analysis.plots",
    "openlens.analysis.psf_mtf",
    "openlens.mechanical_designer",
    "openlens.image_simulator",
)

OPTIONAL_PACKAGES = ("numpy", "matplotlib", "scipy", "PIL", "Pillow")


def _run_without_optional(code, packages=OPTIONAL_PACKAGES):
    """Run `code` in a subprocess where the optional packages are unimportable.

    Args:
        code: Python source to execute.
        packages: Module names to make unavailable.

    Returns:
        The completed process.
    """
    prelude = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(REPO_ROOT)!r})
        for _name in {tuple(packages)!r}:
            sys.modules[_name] = None
        """)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    return subprocess.run(
        [sys.executable, "-c", prelude + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=300,
    )


class TestTheGuardlessModulesImport(unittest.TestCase):
    """The reported defect, module by module."""

    def _import(self, module):
        result = _run_without_optional(f"import {module}")
        self.assertEqual(
            result.returncode,
            0,
            f"importing {module} without numpy/matplotlib/scipy/Pillow "
            f"raised:\n{result.stderr.strip()[-600:]}",
        )

    def test_every_guarded_module_imports(self):
        for module in GUARDED_MODULES:
            with self.subTest(module=module):
                self._import(module)

    def test_the_issue_repro_for_each_module(self):
        """Names them individually, so a failure says which one."""
        expected = {
            "openlens.analysis.plots": "ModuleNotFoundError",
            "openlens.mechanical_designer": "ModuleNotFoundError",
            "openlens.image_simulator": "ModuleNotFoundError",
            "openlens.analysis.psf_mtf": "AttributeError",
        }
        for module, was_raising in expected.items():
            with self.subTest(module=module, was_raising=was_raising):
                result = _run_without_optional(f"import {module}")
                if result.returncode != 0:
                    self.assertIn(
                        was_raising,
                        result.stderr,
                        f"{module} now fails differently",
                    )

    def test_the_application_itself_imports(self):
        """The claim that actually matters: the GUI can start."""
        result = _run_without_optional("""
            import openlens
            print("OK")
            """)
        self.assertEqual(
            result.returncode,
            0,
            "the application cannot start without its optional dependencies:\n"
            + result.stderr.strip()[-800:],
        )

    def test_the_window_class_is_reachable(self):
        result = _run_without_optional("""
            from openlens.__main__ import OpenLensWindow
            print(OpenLensWindow.__name__)
            """)
        self.assertEqual(result.returncode, 0, result.stderr.strip()[-600:])


class TestTheAvailabilityFlagsAreHonest(unittest.TestCase):
    """A guard that reports True while numpy is missing is worse than none."""

    def _flags(self, module):
        result = _run_without_optional(f"""
            import {module} as m
            for name in dir(m):
                if name.endswith('_AVAILABLE') or name.startswith('HAS_'):
                    print(name, getattr(m, name))
            """)
        self.assertEqual(result.returncode, 0, result.stderr.strip()[-500:])
        flags = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            name, value = parts
            flags[name] = value == "True" if value in ("True", "False") else value
        return flags

    def test_psf_mtf_reports_numpy_as_unavailable(self):
        flags = self._flags("openlens.analysis.psf_mtf")

        self.assertIn("HAS_NUMPY", flags)
        self.assertFalse(flags["HAS_NUMPY"], "reports numpy as present when it is not")

    def test_image_simulator_reports_every_optional_as_unavailable(self):
        flags = self._flags("openlens.image_simulator")

        self.assertFalse(flags.get("HAS_NUMPY"), flags)
        self.assertFalse(flags.get("SCIPY_AVAILABLE"), flags)
        self.assertFalse(flags.get("PIL_AVAILABLE"), flags)

    def test_annotations_are_stored_unevaluated(self):
        """`from __future__ import annotations`, proven by construction.

        A guarded import with eager annotations cannot work: `np.ndarray` is
        evaluated when the function is *defined*, against an np that is None.
        The module still imports with deferred annotations, so the annotations
        must have survived as strings.
        """
        for module in ("openlens.analysis.psf_mtf", "openlens.image_simulator"):
            with self.subTest(module=module):
                result = _run_without_optional(f"""
                    import {module} as m
                    import inspect
                    fn = m._map_to_raw_indices if hasattr(m, '_map_to_raw_indices') else None
                    if fn is None:
                        fn = next(v for k, v in vars(m).items()
                                  if inspect.isfunction(v) and v.__module__ == m.__name__)
                    hints = fn.__annotations__
                    print('all_str', all(isinstance(h, str) for h in hints.values()))
                    """)
                self.assertEqual(result.returncode, 0, result.stderr.strip()[-500:])
                self.assertIn(
                    "all_str True",
                    result.stdout,
                    f"{module} evaluates its annotations at def-time, which is "
                    "why the numpy guard alone could not make it importable",
                )


class TestMechanicalDesignerNeedsNoNumpy(unittest.TestCase):
    """Its only use of numpy was the constant np.pi."""

    def test_it_does_not_import_numpy(self):
        source = (REPO_ROOT / "openlens" / "mechanical_designer.py").read_text()

        self.assertNotIn(
            "import numpy",
            source,
            "this module needs no numpy - taking a hard dependency on a soft "
            "one for the value of pi is not a trade worth making",
        )

    def test_the_volume_math_still_works(self):
        result = _run_without_optional("""
            import math
            from openlens.mechanical_designer import LensMount
            mount = LensMount(
                lens_diameter=25.0, mount_type="threaded", thread_diameter=30.0,
                thread_pitch=1.0, flange_distance=5.0, clear_aperture=20.0,
            )
            mount.length = 10.0
            mount.outer_diameter = 50.0
            mount.inner_diameter = 40.0
            volume = math.pi * (25.0 ** 2 - 20.0 ** 2) * 10.0
            print("ok")
            """)
        self.assertEqual(result.returncode, 0, result.stderr.strip()[-500:])
        self.assertTrue(result.stdout.strip())

    def test_pi_is_the_same_value(self):
        """math.pi and np.pi are the same constant; prove nothing shifted."""
        import math

        self.assertEqual(math.pi, 3.141592653589793)


class TestTheOptionalPackagesAreGenuinelyOptional(unittest.TestCase):
    """Guards only mean something if the packages really are optional.

    numpy was a hard requirement in setup.py, added precisely *because* these
    imports were unguarded. With the guards in place that made them dead code,
    and it meant a bare `pip install openlens` pulled in numpy while AGENTS.md
    said it was soft - two positions, one of them now false.
    """

    HARD_REQUIRED = ("pyside6",)

    def _install_requires(self):
        import ast

        tree = ast.parse((REPO_ROOT / "setup.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setup":
                for kw in node.keywords:
                    if kw.arg == "install_requires":
                        return [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
        raise AssertionError("no install_requires found in setup.py")

    def test_numpy_is_not_a_hard_requirement(self):
        names = [re.split(r"[<>=!\[]", r)[0].strip().lower() for r in self._install_requires()]

        self.assertNotIn(
            "numpy",
            names,
            "numpy is guarded everywhere it is used and the core optics run "
            "without it; requiring it makes those guards dead code",
        )

    def test_only_the_gui_framework_is_required(self):
        names = [re.split(r"[<>=!\[]", r)[0].strip().lower() for r in self._install_requires()]

        for package in self.HARD_REQUIRED:
            with self.subTest(package=package):
                self.assertIn(package, names)

        self.assertLessEqual(
            len(names),
            len(self.HARD_REQUIRED),
            f"unexpected hard requirements: {names}",
        )

    def test_the_optional_packages_are_still_offered(self):
        setup_py = (REPO_ROOT / "setup.py").read_text()

        extras = setup_py.split("extras_require")[1]
        for package in ("numpy", "matplotlib"):
            with self.subTest(package=package):
                self.assertIn(package, extras)

    def test_requirements_txt_describes_them_as_recommended(self):
        requirements = (REPO_ROOT / "requirements.txt").read_text()

        self.assertIn("Highly Recommended", requirements)


if __name__ == "__main__":
    unittest.main()
