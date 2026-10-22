"""Regression tests for #611: the beam-synthesis detector must sit at focus.

``propagate_to_image(image_plane_x=None)`` documented a paraxial image plane
but placed the detector at ``get_total_length() + 50`` - an arbitrary plane
50 mm past the last vertex. For a 100 mm singlet (BFL ~95.9 mm, last vertex at
5 mm) that is 55 mm instead of ~101 mm: a ~46 mm defocus, and a PSF that
cannot be compared with the diffraction PSF, which uses the paraxial focus.
"""

import math
import unittest

from openlens.analysis.beam_synthesis import BeamSynthesisPropagator
from openlens.analysis.paraxial import find_paraxial_focus
from openlens.constants import NM_TO_MM, WAVELENGTH_GREEN
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    NUMPY_AVAILABLE = False


def _singlet():
    system = OpticalSystem(name="Singlet")
    system.add_lens(
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5168,
            material="BK7",
        )
    )
    return system


class TestDefaultImagePlane(unittest.TestCase):
    """The plane used when the caller does not name one."""

    def setUp(self):
        self.system = _singlet()
        self.propagator = BeamSynthesisPropagator(self.system)
        self.wavelength_mm = WAVELENGTH_GREEN * NM_TO_MM

    def test_the_default_is_the_paraxial_focus(self):
        """The shared focus search, not a fixed offset."""
        focus = find_paraxial_focus(self.system, WAVELENGTH_GREEN)
        self.assertIsNotNone(focus)

        plane = self.propagator._default_image_plane(self.wavelength_mm)

        self.assertAlmostEqual(plane, focus, places=9)

    def test_the_default_is_not_fifty_millimetres_past_the_last_vertex(self):
        """Regression: 55 mm instead of the ~101 mm focus."""
        plane = self.propagator._default_image_plane(self.wavelength_mm)

        self.assertNotAlmostEqual(plane, self.system.get_total_length() + 50.0, places=3)

    def test_the_default_agrees_with_the_paraxial_back_focal_length(self):
        """The plane is the last vertex plus the BFL, to first order."""
        plane = self.propagator._default_image_plane(self.wavelength_mm)
        expected = self.system.get_total_length() + self.system.calculate_back_focal_length()

        self.assertAlmostEqual(plane, expected, delta=0.01 * abs(expected))

    def test_an_afocal_system_uses_the_documented_fallback(self):
        """A flat plate has no focus; the detector still lands somewhere."""
        system = OpticalSystem(name="Afocal")
        system.add_lens(
            Lens(
                # A zero radius is a plano surface, and two of them in the
                # same glass leave the exit ray collimated.
                radius_of_curvature_1=0.0,
                radius_of_curvature_2=0.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
                material="BK7",
            )
        )
        self.assertIsNone(system.calculate_back_focal_length())
        self.assertIsNone(find_paraxial_focus(system, WAVELENGTH_GREEN))

        plane = BeamSynthesisPropagator(system)._default_image_plane(self.wavelength_mm)

        expected = (
            system.get_total_length()
            + BeamSynthesisPropagator.DEFAULT_IMAGE_PLANE_PAST_LAST_SURFACE
        )
        self.assertAlmostEqual(plane, expected, places=9)
        self.assertTrue(math.isfinite(plane))


@unittest.skipIf(not NUMPY_AVAILABLE, "numpy not installed")
class TestDefaultPlaneIsUsed(unittest.TestCase):
    """The default reaches the detector, not just a helper."""

    def test_the_default_map_equals_the_map_at_the_focus(self):
        system = _singlet()
        focus = find_paraxial_focus(system, WAVELENGTH_GREEN)
        propagator = BeamSynthesisPropagator(system)

        _, _, default_map = propagator.propagate_to_image(grid_size=8, detector_pixels=16)
        _, _, focus_map = propagator.propagate_to_image(
            grid_size=8, detector_pixels=16, image_plane_x=focus
        )

        self.assertTrue(np.allclose(default_map, focus_map))


if __name__ == "__main__":
    unittest.main()
