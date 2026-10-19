"""Regression: a non-editable install must actually work.

Every CI job installs with ``pip install -e .``, so nothing in the suite would
catch a packaging defect that only appears in a real install. That is how the
``openlens`` command shipped broken once: the entry point was a top-level
``openlens.py`` and ``find_packages()`` only finds packages, so it was absent
from every non-editable install - and an editable install hides it completely,
because the source tree is on the path anyway.

The same blind spot hid the installed package name: ``find_packages()`` found
``src``, so a real install put a top-level package called ``src`` into
site-packages, shadowing every other project's ``src/`` directory.

Building a wheel and installing it needs network access, so these tests assert
the properties that make such an install work, and CI does the real thing.
"""

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _setup_py() -> str:
    return (REPO_ROOT / "setup.py").read_text()


def _setup_kwargs() -> dict:
    """Parse setup.py and return the kwargs passed to setup(), unevaluated.

    Parsed rather than imported: importing setup.py runs setup() with whatever
    argv the test runner happens to have.
    """
    tree = ast.parse(_setup_py())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == "setup":
                return {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}
    raise AssertionError("no setup() call found in setup.py")


def _literal(node) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


class TestThePackageNameIsNotGeneric(unittest.TestCase):
    """The reported defect: the distribution installed a top-level ``src``.

    ``src`` is the most generic directory name there is. Installing it into
    site-packages shadowed, or was shadowed by, every other project on the
    machine with a ``src/`` directory - and the console scripts silently
    imported ``src.lens_editor``, so it worked in exactly the way a consumer
    would not expect.
    """

    def test_no_top_level_package_called_src_exists(self):
        self.assertFalse(
            (REPO_ROOT / "src" / "__init__.py").is_file(),
            "the source directory is still an importable package named src, "
            "so a real install puts src/ into site-packages",
        )

    def test_there_is_no_root_openlens_module_to_shadow_the_package(self):
        self.assertFalse(
            (REPO_ROOT / "openlens.py").is_file(),
            "a root openlens.py sits beside the openlens/ package and shadows "
            "it on the module path, which is how this became a problem the "
            "first time",
        )

    def test_the_declared_packages_are_all_inside_openlens(self):
        """What find_packages() may ship. Nothing outside the package."""
        kwargs = _setup_kwargs()
        packages = _literal(kwargs.get("packages"))

        if packages is None:
            # Computed by find_packages(include=[...]); assert the include
            # pattern, since that is what constrains it.
            source = _setup_py()
            self.assertIn(
                "find_packages(include=['openlens', 'openlens.*'])",
                source,
                "find_packages() is unconstrained, so a stray top-level "
                "directory can be installed as a package again",
            )
            return

        stray = [name for name in packages if name.split(".")[0] != "openlens"]
        self.assertEqual(stray, [], f"packages outside openlens would be installed: {stray}")

    def test_the_entry_point_target_is_importable_from_a_real_install(self):
        entry_points = _literal(_setup_kwargs()["entry_points"])

        self.assertIsNotNone(entry_points, "no entry_points declared")

        scripts = entry_points.get("console_scripts", [])
        self.assertTrue(scripts, "no console_scripts entry point")

        for script in scripts:
            target = script.partition("=")[2]
            module, _, attribute = target.partition(":")
            path = REPO_ROOT / f"{module.replace('.', '/')}.py"
            self.assertTrue(
                path.is_file() or (REPO_ROOT / module.replace(".", "/") / "__init__.py").is_file(),
                f"entry point {script} points at a module that is not in the tree",
            )
            self.assertTrue(
                module.split(".")[0] == "openlens",
                f"entry point {script} does not import the installed package",
            )

    def test_the_gui_entry_point_is_inside_the_package(self):
        entry = _literal(_setup_kwargs()["entry_points"])["console_scripts"]
        gui = [script for script in entry if script.startswith("openlens=")]

        self.assertEqual(gui, ["openlens=openlens.__main__:main"])
        main_py = REPO_ROOT / "openlens" / "__main__.py"
        self.assertTrue(main_py.is_file(), "the GUI entry module is missing")
        self.assertIn("def main(", main_py.read_text(), "the entry point names main()")


class TestTheMetadataIsHonest(unittest.TestCase):
    def test_the_urls_point_at_the_real_repository(self):
        kwargs = _setup_kwargs()

        url = _literal(kwargs["url"])
        self.assertIn("pmaasz/openLens", url, f"url points at the wrong repo: {url}")

        for name, target in (_literal(kwargs["project_urls"]) or {}).items():
            with self.subTest(url=name):
                self.assertIn(
                    "pmaasz/openLens",
                    target,
                    f"project_urls[{name}] points at the wrong repo",
                )

    def test_python_requires_matches_the_tested_versions(self):
        kwargs = _setup_kwargs()

        requires = _literal(kwargs["python_requires"])
        classifiers = _literal(kwargs["classifiers"]) or []

        supported = set()
        for c in classifiers:
            m = re.search(r"Python :: (\d+)\.(\d+)$", c)
            if m:
                supported.add((int(m.group(1)), int(m.group(2))))
        self.assertTrue(supported, "no version classifiers found")

        floor_match = re.search(r">=(\d+)\.(\d+)", requires)
        self.assertIsNotNone(floor_match, f"cannot parse python_requires: {requires!r}")
        floor = (int(floor_match.group(1)), int(floor_match.group(2)))

        self.assertEqual(
            floor,
            min(supported),
            "python_requires claims a lower floor than CI actually tests, so "
            "users are promised support that is never exercised",
        )
        for version in sorted(supported):
            with self.subTest(python=version):
                self.assertGreaterEqual(
                    version,
                    floor,
                    f"{version[0]}.{version[1]} has a classifier but is "
                    "excluded by python_requires",
                )

    def test_no_classifier_is_listed_twice(self):
        classifiers = _literal(_setup_kwargs()["classifiers"]) or []

        duplicates = {c for c in classifiers if classifiers.count(c) > 1}
        self.assertEqual(duplicates, set(), f"duplicated classifiers: {duplicates}")

    def test_the_development_status_is_not_overstated(self):
        classifiers = _literal(_setup_kwargs()["classifiers"]) or []

        statuses = [c for c in classifiers if c.startswith("Development Status")]
        self.assertTrue(statuses)
        for status in statuses:
            with self.subTest(status=status):
                self.assertNotIn(
                    "Production/Stable",
                    status,
                    "the project is pre-1.0; Production/Stable is a promise, not " "a description",
                )

    def test_requirements_imported_at_startup_are_declared(self):
        """numpy is imported at module load, so it cannot be optional."""
        entry = _literal(_setup_kwargs()["install_requires"]) or []
        entry_names = {re.split(r"[<>=!\[]", r)[0].strip().lower() for r in entry}

        source = (REPO_ROOT / "openlens" / "__main__.py").read_text()
        module_level = "\n".join(
            line for line in source.splitlines() if not line.startswith((" ", "\t", "#"))
        )

        for package in ("numpy",):
            with self.subTest(package=package):
                if re.search(rf"^import {package}$|^from {package}\b", module_level, re.M):
                    self.assertIn(
                        package,
                        entry_names,
                        f"{package} is imported at module load but is not a "
                        "hard requirement, so a plain install crashes at startup",
                    )

    def test_manifest_includes_nothing_that_does_not_exist(self):
        """MANIFEST.in listed verify_setup.py, which does not exist."""
        manifest = (REPO_ROOT / "MANIFEST.in").read_text().splitlines()

        for line in manifest:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"include\s+(\S+)$", line)
            if not match:
                continue
            target = REPO_ROOT / match.group(1)
            with self.subTest(entry=line):
                self.assertTrue(
                    target.exists(),
                    f"MANIFEST.in includes {match.group(1)}, which does not "
                    "exist - every build pays for it and gets nothing",
                )


class TestTheVersionIsDefinedOnce(unittest.TestCase):
    """setup.py parsed openlens/__init__.py and fell back to a hard-coded version."""

    def test_setup_py_does_not_invent_a_version(self):
        source = _setup_py()

        self.assertNotIn(
            'return "0.1.0"',
            source,
            "a fallback version silently ships a package claiming to be far "
            "older than it is, and the release manifest is driven by this",
        )

    def test_a_missing_version_is_an_error_not_a_fallback(self):
        """Proved by running get_version against a file with no version."""
        source = _setup_py()
        body = source[source.index("def get_version") : source.index("setup(")]

        self.assertIn("raise", body, "a version-less build should fail, not guess")

    def test_the_version_reported_matches_the_one_packaged(self):
        import openlens

        tree = ast.parse(_setup_py())
        get_version = next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "get_version"
        )
        self.assertTrue(get_version.body)

        packaged = subprocess.run(
            [sys.executable, "setup.py", "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if packaged.returncode != 0:
            self.skipTest(f"setup.py --version unavailable: {packaged.stderr.strip()}")

        self.assertEqual(
            packaged.stdout.strip(),
            openlens.__version__,
            "the installed distribution and the package report different versions",
        )


class TestTheInstalledCommandRuns(unittest.TestCase):
    """What CI's Package install job actually does, minus the network."""

    def _headless_flags(self, *args):
        """Run the flag handling the way the console script would."""
        from openlens import __main__

        return __main__._handle_headless_flags(list(args))

    def test_version_prints_and_exits_zero(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = self._headless_flags("--version")

        self.assertEqual(code, 0)
        self.assertRegex(
            buffer.getvalue(),
            r"^openlens \S+$",
            f"unexpected --version output: {buffer.getvalue()!r}",
        )

    def test_the_short_flag_works_too(self):
        self.assertEqual(self._headless_flags("-V"), 0)

    def test_help_prints_and_exits_zero(self):
        code = self._headless_flags("--help")

        self.assertEqual(code, 0)

    def test_no_flags_falls_through_to_the_gui(self):
        self.assertIsNone(
            self._headless_flags(),
            "the GUI never opens because a flag was mishandled",
        )

    def test_unknown_flags_fall_through_rather_than_exiting(self):
        """Qt has its own argument handling; do not pre-empt it."""
        self.assertIsNone(self._headless_flags("-style", "fusion"))

    def test_the_version_flag_needs_no_display(self):
        """CI runs this headless; a QApplication first would need a GPU."""
        source = (REPO_ROOT / "openlens" / "__main__.py").read_text()
        # To the end: a fixed-length slice started failing as soon as main()
        # grew a migration block, which is not what this test is about.
        main_body = source[source.index("def main()") :]

        self.assertLess(
            main_body.index("_handle_headless_flags"),
            main_body.index("QApplication("),
            "the headless flags are handled after QApplication is created, so "
            "--version needs a display and cannot verify an install in CI",
        )


if __name__ == "__main__":
    unittest.main()
