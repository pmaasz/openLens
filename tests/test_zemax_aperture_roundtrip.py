#!/usr/bin/env python3
"""
Zemax round trip: a lens with asymmetric clear apertures must survive.

The exporter writes one semi-diameter per surface (``DIAM = clear aperture /
2``), but the importer rebuilt the mechanical diameter from the BACK surface
only and then rejected the element when the front clear aperture was the
larger one - so a valid lens vanished from the imported system.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openlens.export_formats import ZemaxSystemExporter, ZemaxSystemImporter
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


class TestZemaxClearApertureRoundTrip(unittest.TestCase):
    """The imported system must keep every element and both apertures."""

    def _round_trip(self, **apertures):
        system = OpticalSystem(name="Apertures")
        system.add_lens(
            Lens(
                name="Test Lens",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=40.0,
                material="BK7",
                **apertures,
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "apertures.zmx")
            ZemaxSystemExporter.export_system(system, path)
            return ZemaxSystemImporter.import_system(path)

    def test_a_larger_front_aperture_is_not_dropped(self):
        """CA1 > CA2 used to drop the whole element"""
        imported = self._round_trip(clear_aperture_1=38.0, clear_aperture_2=30.0)

        self.assertEqual(len(imported.elements), 1, "the element was dropped")
        lens = imported.elements[0].lens
        self.assertEqual(lens.clear_aperture_1, 38.0)
        self.assertEqual(lens.clear_aperture_2, 30.0)

    def test_a_larger_back_aperture_is_not_dropped(self):
        """The mirror image must behave the same way"""
        imported = self._round_trip(clear_aperture_1=30.0, clear_aperture_2=38.0)

        self.assertEqual(len(imported.elements), 1, "the element was dropped")
        lens = imported.elements[0].lens
        self.assertEqual(lens.clear_aperture_1, 30.0)
        self.assertEqual(lens.clear_aperture_2, 38.0)

    def test_only_a_back_aperture_is_not_dropped(self):
        """A lens with just a back aperture used to be dropped as well"""
        imported = self._round_trip(clear_aperture_2=30.0)

        self.assertEqual(len(imported.elements), 1, "the element was dropped")
        self.assertEqual(imported.elements[0].lens.clear_aperture_2, 30.0)

    def test_the_diameter_holds_both_apertures(self):
        """The restored diameter must fit the apertures it was restored with"""
        for apertures in (
            {"clear_aperture_1": 38.0, "clear_aperture_2": 30.0},
            {"clear_aperture_1": 30.0, "clear_aperture_2": 38.0},
            {"clear_aperture_1": 30.0},
            {"clear_aperture_2": 30.0},
        ):
            with self.subTest(apertures=apertures):
                imported = self._round_trip(**apertures)
                self.assertEqual(len(imported.elements), 1)
                lens = imported.elements[0].lens
                self.assertGreaterEqual(lens.diameter, lens.clear_aperture_1 or 0.0)
                self.assertGreaterEqual(lens.diameter, lens.clear_aperture_2 or 0.0)

    def test_a_lens_without_clear_apertures_keeps_its_diameter(self):
        """The common case must round-trip exactly"""
        imported = self._round_trip()

        self.assertEqual(len(imported.elements), 1)
        self.assertEqual(imported.elements[0].lens.diameter, 40.0)


if __name__ == "__main__":
    unittest.main()
