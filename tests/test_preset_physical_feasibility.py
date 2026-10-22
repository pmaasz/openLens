"""#652: every shipped preset must describe a lens that can be made.

The preset table is literal data, so nothing checked that the surfaces meet
inside the clear aperture. Four entries had a negative edge thickness (or a
diameter larger than 2|R|, so the surface did not exist at the rim). The
application's own create path refuses the same geometry.

``check_physical_feasibility`` also emits advisory warnings for stock designs
whose thickness or diameter is large relative to the radii (for example the
Edmund 25 mm PCX). Those lenses are physically buildable, so this test checks
the hard criterion: a real surface at the rim and an edge thickness that clears
the manufacturable floor.
"""

import unittest

from openlens.constants import MIN_EDGE_THICKNESS
from openlens.preset_library import get_preset_library


class TestShippedPresetsAreManufacturable(unittest.TestCase):
    def test_every_preset_has_a_positive_edge_thickness(self):
        for preset in get_preset_library().list_presets():
            lens = preset.lens
            with self.subTest(preset=preset.name):
                edge = lens.calculate_edge_thickness()
                self.assertIsNotNone(
                    edge,
                    f"{preset.name}: the aperture overhangs a surface, so no "
                    "real surface exists at the rim",
                )
                self.assertGreaterEqual(
                    edge,
                    MIN_EDGE_THICKNESS,
                    f"{preset.name}: the rim would be too thin to manufacture",
                )


if __name__ == "__main__":
    unittest.main()
