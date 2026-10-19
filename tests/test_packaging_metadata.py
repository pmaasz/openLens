#!/usr/bin/env python3
"""Regression: the declared distribution must actually be installable.

A normal (non-editable) install of this project was broken in several ways
that nothing in the test suite noticed, because the tests all run against the
source tree via ``pip install -e .``. The evidence lives in ``setup.py``, so
these tests read the config it would hand to setuptools and assert that the
distribution it describes is coherent.

The headline defect this suite was written for: ``openlens=openlens:main``
pointed at a top-level ``openlens/__main__.py``, which ``find_packages()`` does not
include and nothing listed as a module, so the command was missing from a real
install. The entry module now lives inside the ``openlens`` package, and the
suite additionally pins that nothing outside that package is shipped - the
distribution used to install a top-level ``src`` into site-packages.
"""

import ast
import os
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_PY = os.path.join(REPO_ROOT, "setup.py")

#: Directories that are never packaged, and are not part of the source tree.
_IGNORED_DIRS = {"tests", "build", "dist", "docs", "__pycache__", "venv", ".venv"}


def _discover_packages():
    """Every importable package in the source tree, as dotted names.

    Stands in for ``find_packages()``, which needs setuptools. That import is
    deliberately avoided: pip builds in an isolated environment, so setuptools
    is *not* installed alongside the package and a test that needs it fails
    with ModuleNotFoundError in CI - which is precisely where these tests
    matter most.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _IGNORED_DIRS
            and not d.startswith(".")
            and not d.endswith(".egg-info")
            and not d.startswith("_")
        ]
        if "__init__.py" not in filenames:
            continue
        relative = os.path.relpath(dirpath, REPO_ROOT)
        if relative == ".":
            continue
        found.append(relative.replace(os.sep, "."))
    return sorted(found)


def _declared_version():
    """The version from openlens/__init__.py, as setup.py's get_version() reads it."""
    with open(os.path.join(REPO_ROOT, "openlens", "__init__.py"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "0.0.0"


def _setup_config():
    """The kwargs setup.py passes to setup(), read without importing setuptools.

    Parsed statically: every keyword whose value is a literal is taken as-is,
    and the two that are computed - ``packages`` and ``version`` - are
    evaluated from the source tree the same way setup.py evaluates them.

    Raises:
        AssertionError: If setup.py has no ``setup(...)`` call.
    """
    with open(SETUP_PY, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), SETUP_PY)

    call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup":
            call = node
            break
    if call is None:
        raise AssertionError("setup.py has no setup(...) call")

    config = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            continue
        try:
            config[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, SyntaxError):
            # A computed value; handled below.
            config[keyword.arg] = None

    if config.get("packages") is None:
        excluded = set(config.get("exclude") or []) if config.get("exclude") else None
        packages = _discover_packages()
        if excluded:
            packages = [p for p in packages if p not in excluded]
        config["packages"] = packages
    if config.get("version") is None:
        config["version"] = _declared_version()

    return config


def _entry_point_modules(config):
    """The top-level module each console script imports."""
    scripts = config.get("entry_points", {}).get("console_scripts", [])
    modules = []
    for script in scripts:
        target = script.split("=", 1)[-1].strip()
        modules.append(target.split(":", 1)[0].strip())
    return modules


class TestConsoleScriptsAreShipped(unittest.TestCase):
    """A console script whose module is not installed is a broken command."""

    @classmethod
    def setUpClass(cls):
        cls.config = _setup_config()

    def test_every_console_script_target_is_in_the_distribution(self):
        packages = set(self.config.get("packages", []))
        py_modules = set(self.config.get("py_modules", []))
        # What an installed distribution makes importable: every discovered
        # package, plus any top-level module listed in py_modules.
        shipped = {name.split(".")[0] for name in packages} | py_modules

        # A dotted target only needs its top-level package shipped; the rest
        # of the path is resolved inside it.
        missing = [m for m in _entry_point_modules(self.config) if m.split(".")[0] not in shipped]

        self.assertEqual(
            missing,
            [],
            f"console script targets {missing} cannot be imported from a real "
            f"install: the top-level package they belong to is not shipped",
        )

    def test_the_gui_entry_point_target_exists_on_disk(self):
        for module in _entry_point_modules(self.config):
            with self.subTest(module=module):
                self.assertTrue(
                    os.path.exists(os.path.join(REPO_ROOT, *module.split(".")) + ".py"),
                    f"{module}.py does not exist, so its console script cannot work",
                )

    def test_every_declared_package_exists(self):
        for package in self.config.get("packages", []):
            with self.subTest(package=package):
                self.assertTrue(
                    os.path.isdir(os.path.join(REPO_ROOT, *package.split("."))),
                    f"{package} is declared as a package but has no directory",
                )

    def test_every_declared_module_exists(self):
        for module in self.config.get("py_modules", []):
            with self.subTest(module=module):
                self.assertTrue(
                    os.path.exists(os.path.join(REPO_ROOT, f"{module}.py")),
                    f"{module} is declared in py_modules but the file is missing",
                )

    def test_the_tests_are_not_shipped(self):
        for package in self.config.get("packages", []):
            with self.subTest(package=package):
                self.assertFalse(
                    package == "tests" or package.startswith("tests."),
                    "the test suite is being installed into site-packages",
                )


class TestInstallRequirementsMatchReality(unittest.TestCase):
    """A plain ``pip install`` has to produce a runnable application."""

    @classmethod
    def setUpClass(cls):
        cls.config = _setup_config()

    def test_numpy_is_not_a_hard_requirement(self):
        """It was, for exactly one reason: unguarded imports.

        This assertion was added when openlens/analysis/plots.py imported numpy at
        module level and the GUI entry module imported it unconditionally - so a
        plain `pip install openlens` raised ImportError at startup.

        Those imports are guarded now (#476), and the core does not need numpy:
        Lens, the ray tracer and focal length all run without it. Requiring it
        made every one of those guards dead code, and quietly narrowed what
        AGENTS.md means by an optional dependency.
        """
        requirements = " ".join(self.config.get("install_requires", []))

        self.assertNotIn(
            "numpy",
            requirements.lower(),
            "numpy is guarded at every use site and the core optics run without "
            "it; requiring it contradicts the guards it was added to avoid",
        )

    def test_numpy_is_still_offered_as_an_extra(self):
        setup_py = (Path(__file__).resolve().parent.parent / "setup.py").read_text()
        extras = setup_py.split("extras_require")[1]

        self.assertIn("numpy", extras, "removing the hard requirement must not remove the extra")

    def test_pyside_is_a_hard_requirement(self):
        requirements = " ".join(self.config.get("install_requires", []))

        self.assertIn("pyside6", requirements.lower())

    def test_the_startup_import_is_unguarded(self):
        """Guards the premise: if numpy were made optional, this requirement
        could move to an extra."""
        with open(os.path.join(REPO_ROOT, "openlens", "analysis", "plots.py")) as handle:
            tree = ast.parse(handle.read())

        guarded = False
        for node in tree.body:
            if isinstance(node, ast.Try):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Import) and any(
                        alias.name.split(".")[0] == "numpy" for alias in sub.names
                    ):
                        guarded = True
            if isinstance(node, ast.Import) and any(
                alias.name.split(".")[0] == "numpy" for alias in node.names
            ):
                self.assertFalse(
                    guarded, "numpy turned out to be guarded; the test premise changed"
                )


class TestPythonVersionMetadata(unittest.TestCase):
    """python_requires and the classifiers have to agree with CI."""

    @classmethod
    def setUpClass(cls):
        cls.config = _setup_config()

    def test_python_requires_matches_the_oldest_tested_version(self):
        """CI tests 3.10-3.12; claiming 3.7 support that is never exercised."""
        self.assertEqual(
            self.config.get("python_requires"),
            ">=3.10",
            "python_requires claims support for versions CI does not test",
        )

    def test_no_duplicate_classifiers(self):
        """The 3.7 classifier was listed twice."""
        classifiers = self.config.get("classifiers", [])

        duplicates = {c for c in classifiers if classifiers.count(c) > 1}

        self.assertEqual(
            duplicates,
            set(),
            f"classifiers are listed more than once: {sorted(duplicates)}",
        )

    def test_every_declared_version_is_actually_tested(self):
        declared = {
            c.rsplit(" ", 1)[-1]
            for c in self.config.get("classifiers", [])
            if c.startswith("Programming Language :: Python :: 3.")
        }

        for version in declared:
            with self.subTest(version=version):
                self.assertIn(
                    version,
                    {"3.10", "3.11", "3.12"},
                    f"{version} is advertised as supported but CI does not " f"test it",
                )

    def test_the_development_status_is_not_overstated(self):
        """'Production/Stable' is a claim about a 0.x package."""
        classifiers = self.config.get("classifiers", [])
        version = str(self.config.get("version", "0.0.0"))

        self.assertNotIn(
            "Development Status :: 5 - Production/Stable",
            classifiers,
            "a 0.x package should not be classified as Production/Stable",
        )
        self.assertTrue(
            any(c.startswith("Development Status ::") for c in classifiers),
            "no Development Status classifier is declared at all",
        )
        self.assertTrue(version)


class TestProjectUrls(unittest.TestCase):
    """The URLs have to point at the repository the code actually lives in."""

    @classmethod
    def setUpClass(cls):
        cls.config = _setup_config()
        cls.repo = _remote_slug()

    def _urls(self):
        values = []
        if self.config.get("url"):
            values.append(self.config["url"])
        values.extend(self.config.get("project_urls", {}).values())
        return values

    def test_urls_point_at_the_real_repository(self):
        wrong = [url for url in self._urls() if "github.com" in url and self.repo not in url]

        self.assertEqual(
            wrong,
            [],
            f"these URLs point somewhere other than {self.repo}: {wrong}",
        )

    def test_there_is_a_bug_tracker_url(self):
        urls = {k.lower(): v for k, v in self.config.get("project_urls", {}).items()}

        self.assertTrue(
            any("issue" in k or "bug" in k for k in urls),
            "no issue-tracker URL is declared",
        )


class TestManifestIn(unittest.TestCase):
    """MANIFEST.in naming a file that does not exist is dead weight."""

    def _included_files(self):
        manifest = os.path.join(REPO_ROOT, "MANIFEST.in")
        if not os.path.exists(manifest):
            return []

        with open(manifest, encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip().startswith("include ")]
        return [line.split(None, 1)[1].strip() for line in lines]

    def test_every_included_file_exists(self):
        missing = [
            name
            for name in self._included_files()
            if not os.path.exists(os.path.join(REPO_ROOT, name))
        ]

        self.assertEqual(
            missing,
            [],
            f"MANIFEST.in includes files that do not exist: {missing}",
        )


def _remote_slug():
    """The owner/repo of origin, so the test does not hardcode the location."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "pmaasz/openLens"

    cleaned = url.removesuffix(".git").rstrip("/")
    if "github.com" in cleaned:
        return cleaned.split("github.com", 1)[1].lstrip("/:").replace(":", "/")
    return "pmaasz/openLens"


if __name__ == "__main__":
    unittest.main()
