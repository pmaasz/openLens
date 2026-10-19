"""#460: one paraxial-focus search shared by spot, geometric and PSF analysis.

The three copies disagreed on the launch offset (10 vs 20 mm), the
collimation threshold (1e-9 vs 1e-12) and whether the lens indices were
updated for the traced wavelength. These tests pin the shared helper, the
agreement of the public entry points that used to hold the copies, and the
state restoration.
"""

import unittest

from openlens.analysis.geometric import GeometricTraceAnalysis
from openlens.analysis.paraxial import find_paraxial_focus
from openlens.analysis.spot_diagram import SpotDiagram
from openlens.constants import (
    WAVELENGTH_C_LINE,
    WAVELENGTH_F_LINE,
    WAVELENGTH_GREEN,
)
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

#: Focus of the singlet below, measured with the pre-#460 copies (the spot
#: diagram and geometric implementations agreed exactly); the shared search
#: must not move it.
PINNED_GREEN_FOCUS = 54.826135397161735


def _singlet() -> OpticalSystem:
    system = OpticalSystem(name="Singlet")
    system.add_lens(
        Lens(
            name="Crown",
            radius_of_curvature_1=51.68,
            radius_of_curvature_2=-51.68,
            thickness=6.0,
            diameter=25.4,
            material="N-BK7",
            refractive_index=1.5168,
        )
    )
    return system


class TestFindParaxialFocus(unittest.TestCase):
    def test_focus_matches_the_pre_refactor_value(self):
        self.assertAlmostEqual(
            find_paraxial_focus(_singlet(), WAVELENGTH_GREEN),
            PINNED_GREEN_FOCUS,
            places=6,
        )

    def test_focus_is_chromatic(self):
        """The search must use the wavelength's indices: blue focuses shorter."""
        system = _singlet()
        blue = find_paraxial_focus(system, WAVELENGTH_F_LINE)
        green = find_paraxial_focus(system, WAVELENGTH_GREEN)
        red = find_paraxial_focus(system, WAVELENGTH_C_LINE)
        self.assertLess(blue, green)
        self.assertLess(green, red)

    def test_lens_state_is_restored_after_the_search(self):
        system = _singlet()
        lens = system.elements[0].lens
        before = (lens.wavelength, lens.refractive_index)
        find_paraxial_focus(system, WAVELENGTH_F_LINE)
        self.assertEqual((lens.wavelength, lens.refractive_index), before)

    def test_a_callers_wavelength_swap_survives_the_search(self):
        system = _singlet()
        lens = system.elements[0].lens
        lens.update_refractive_index(wavelength_nm=WAVELENGTH_C_LINE)
        expected = (lens.wavelength, lens.refractive_index)
        find_paraxial_focus(system, WAVELENGTH_F_LINE)
        self.assertEqual((lens.wavelength, lens.refractive_index), expected)

    def test_empty_system_has_no_focus(self):
        self.assertIsNone(find_paraxial_focus(OpticalSystem(name="Empty")))


class TestEntryPointsShareTheSearch(unittest.TestCase):
    def test_spot_diagram_image_plane_matches_the_helper(self):
        system = _singlet()
        focus = find_paraxial_focus(system, WAVELENGTH_GREEN)
        spot = SpotDiagram(system).trace_spot(wavelength_nm=WAVELENGTH_GREEN)
        self.assertAlmostEqual(spot["image_plane_x"], focus, places=9)

    def test_geometric_image_plane_matches_the_helper(self):
        system = _singlet()
        focus = find_paraxial_focus(system, WAVELENGTH_GREEN)
        plane = GeometricTraceAnalysis(system)._get_image_plane_x(WAVELENGTH_GREEN)
        self.assertAlmostEqual(plane, focus, places=9)

    def test_spot_diagram_image_plane_is_chromatic(self):
        """One copy was missing the wavelength wrapper; none may regress."""
        blue = SpotDiagram(_singlet()).trace_spot(wavelength_nm=WAVELENGTH_F_LINE)
        red = SpotDiagram(_singlet()).trace_spot(wavelength_nm=WAVELENGTH_C_LINE)
        self.assertLess(blue["image_plane_x"], red["image_plane_x"])


if __name__ == "__main__":
    unittest.main()
