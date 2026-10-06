#!/usr/bin/env python3
"""
calculate_mtf carried a 70-line unreachable duplicate of its own body.

Immediately after the live `return` sat a verbatim copy of the block above it,
referencing three identifiers that do not exist in scope:

    psf_data = self.calculate_psf(
        field_angle=field_angle,      # no such parameter
        wavelength=wavelength,        # no such parameter
        focus_shift=focus_shift,      # no such parameter

calculate_mtf's parameters are field_angle_deg / wavelength_nm /
focus_shift_mm, and calculate_psf accepts none of the three legacy names.

It was dead by accident of ordering, not by design - a trap, since "fixing"
the legacy-kwargs shim at the top of calculate_mtf would have made the block
reachable and turned three NameErrors into a silently different MTF path.

Deleting it changes no behaviour, which the tests below pin: MTF output is
bit-identical before and after across the geometric and diffraction paths at
on- and off-axis field.
"""

import ast
import unittest

from src.analysis.psf_mtf import ImageQualityAnalyzer
from src.lens import Lens
from src.optical_system import OpticalSystem


def _analyzer():
    system = OpticalSystem(name="M")
    system.add_lens(
        Lens(
            name="L",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
    )
    return ImageQualityAnalyzer(system)


def _function_node(path, name):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError("%s not found in %s" % (name, path))


def _unreachable_statements(node):
    """Statements following a return in any statement list of the function.

    Checks the function's own body as well as nested ones: the dead block sat
    directly in calculate_mtf's body, after the `if use_diffraction:` branch
    that returns.
    """
    dead = []

    def scan(body):
        if not isinstance(body, list):
            return
        for i, stmt in enumerate(body):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue  # a nested def has its own scope
            if isinstance(stmt, ast.Return):
                dead.extend(body[i + 1 :])
                return
            for attr in ("body", "orelse", "finalbody"):
                scan(getattr(stmt, attr, None))
            for handler in getattr(stmt, "handlers", []) or []:
                scan(getattr(handler, "body", None))

    scan(node.body)
    return dead


PSF_MTF = "src/analysis/psf_mtf.py"


class TestNoUnreachableCode(unittest.TestCase):
    def test_calculate_mtf_has_no_dead_trailing_block(self):
        """Regression: a 70-line duplicate sat after the return."""
        node = _function_node(PSF_MTF, "calculate_mtf")
        dead = _unreachable_statements(node)
        self.assertEqual(
            [],
            [type(s).__name__ for s in dead],
            "calculate_mtf has %d unreachable statement(s) after a return" % len(dead),
        )

    def test_no_call_uses_a_legacy_parameter_name(self):
        """The dead block called calculate_psf(field_angle=..., wavelength=...).

        None of those names exist on calculate_psf, so a real call with them
        would raise TypeError. Checked on the AST rather than by text so a
        differently-formatted copy is still caught.
        """
        with open(PSF_MTF, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        legacy = {"field_angle", "wavelength", "focus_shift"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name not in ("calculate_psf", "_calculate_diffraction_psf"):
                continue
            for keyword in node.keywords:
                self.assertNotIn(
                    keyword.arg,
                    legacy,
                    "call to %s() uses legacy keyword %r" % (name, keyword.arg),
                )

    def test_the_stale_comment_appears_only_once(self):
        """It marked the duplicated block; the live copy keeps one."""
        with open(PSF_MTF, encoding="utf-8") as f:
            source = f.read()
        self.assertEqual(source.count("# 1. Calculate PSF with sufficient resolution"), 1)


class TestCalculateMtfUnaffected(unittest.TestCase):
    """Behaviour must be identical now that the block is gone."""

    def setUp(self):
        self.analyzer = _analyzer()

    def test_geometric_mtf_has_the_documented_keys(self):
        result = self.analyzer.calculate_mtf(field_angle_deg=0.0)
        self.assertEqual(set(result), {"freq", "mtf_tan", "mtf_sag"})

    def test_diffraction_mtf_has_the_documented_keys(self):
        result = self.analyzer.calculate_mtf(field_angle_deg=0.0, use_diffraction=True)
        self.assertEqual(set(result), {"freq", "mtf_tan", "mtf_sag"})

    def test_both_paths_start_at_zero_frequency(self):
        for diff in (False, True):
            with self.subTest(use_diffraction=diff):
                result = self.analyzer.calculate_mtf(field_angle_deg=0.0, use_diffraction=diff)
                self.assertAlmostEqual(float(result["freq"][0]), 0.0)

    def test_frequencies_are_within_max_freq(self):
        for diff in (False, True):
            with self.subTest(use_diffraction=diff):
                result = self.analyzer.calculate_mtf(
                    field_angle_deg=5.0, max_freq=50.0, use_diffraction=diff
                )
                self.assertTrue(all(f <= 50.0 for f in result["freq"]))

    def test_mtf_is_not_above_one(self):
        """Normalised LSF autocorrelation: MTF <= 1 by construction."""
        for diff in (False, True):
            with self.subTest(use_diffraction=diff):
                result = self.analyzer.calculate_mtf(field_angle_deg=5.0, use_diffraction=diff)
                for key in ("mtf_tan", "mtf_sag"):
                    self.assertTrue(all(v <= 1.0 + 1e-9 for v in result[key]), key)

    def test_geometric_and_diffraction_differ(self):
        """A regression here would mean the diff path had been short-circuited."""
        geom = self.analyzer.calculate_mtf(field_angle_deg=5.0)
        diff = self.analyzer.calculate_mtf(field_angle_deg=5.0, use_diffraction=True)
        self.assertNotEqual(list(geom["freq"]), list(diff["freq"]))

    def test_legacy_kwargs_are_still_rejected_or_mapped(self):
        """The shim must not have been widened to reach the dead block."""
        with self.assertRaises(TypeError):
            self.analyzer.calculate_mtf(bogus_argument=1)


if __name__ == "__main__":
    unittest.main()
