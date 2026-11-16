#!/usr/bin/env python3
"""Goal-driven lens design wizard (#788)."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.target_design import (
    design_doublet_from_target,
    design_singlet_from_target,
)


class TestSingletTargetDesign(unittest.TestCase):
    def test_common_target_produces_a_feasible_lens(self):
        result = design_singlet_from_target(
            focal_length_mm=50.0,
            f_number=2.0,
            material="BK7",
            wavelength_nm=550.0,
        )

        self.assertTrue(result.ok)
        self.assertIsInstance(result.target, Lens)
        self.assertAlmostEqual(result.merit["achieved_focal_length_mm"], 50.0, delta=1.0)
        self.assertGreater(result.target.calculate_edge_thickness(), 0.0)
        # The symmetric thick shape may need a warning-free or warned solution,
        # but it must be a usable starting point for a common camera target.
        self.assertFalse(
            any("intersect" in warning for warning in result.warnings),
            result.warnings,
        )

    def test_infeasible_geometry_reports_warnings(self):
        result = design_singlet_from_target(
            focal_length_mm=50.0,
            diameter_mm=5.0,
            material="BK7",
            wavelength_nm=550.0,
            thickness_mm=30.0,
        )

        self.assertTrue(result.ok, "a best-effort design is still previewable")
        self.assertTrue(result.warnings)
        self.assertTrue(
            any(
                "edge" in warning or "thickness" in warning or "large" in warning
                for warning in result.warnings
            ),
            result.warnings,
        )

    def test_invalid_target_is_rejected(self):
        result = design_singlet_from_target(focal_length_mm=0.0, diameter_mm=25.0)

        self.assertFalse(result.ok)
        self.assertTrue(result.warnings)


class TestDoubletTargetDesign(unittest.TestCase):
    def test_doublet_target_produces_an_assembly(self):
        result = design_doublet_from_target(
            focal_length_mm=100.0,
            diameter_mm=25.0,
            crown_material="BK7",
            flint_material="SF11",
        )

        self.assertTrue(result.ok)
        self.assertIsInstance(result.target, OpticalSystem)
        self.assertEqual(len(result.target.elements), 2)
        self.assertIsNotNone(result.merit.get("achieved_focal_length_mm"))


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestTargetWizardDialog(unittest.TestCase):
    def setUp(self):
        from openlens.gui.dialogs.target_wizard import TargetLensWizardDialog

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.dialog = TargetLensWizardDialog()

    def tearDown(self):
        self.dialog.deleteLater()

    def test_cancel_leaves_no_design_to_add(self):
        lenses = []
        self.dialog._on_design()
        self.dialog.reject()

        if self.dialog.result() == self.dialog.DialogCode.Accepted:
            target = self.dialog.designed_target()
            if target is not None:
                lenses.append(target)
        self.assertEqual(lenses, [])

    def test_preview_before_accept_enables_adding(self):
        self.assertFalse(self.dialog._add_btn.isEnabled())
        self.dialog._on_design()
        self.assertTrue(self.dialog._add_btn.isEnabled())
        self.assertIsNotNone(self.dialog.designed_target())


if __name__ == "__main__":
    unittest.main()
