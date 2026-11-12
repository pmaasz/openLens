"""#664: Fresnel facet counts must be bounded."""

import time
import unittest

from openlens.geometry import LensGeometry
from openlens.lens import Lens


class TestFresnelFacetCap(unittest.TestCase):
    def test_an_absurd_pitch_does_not_materialise_millions_of_facets(self):
        lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            is_fresnel=True,
            groove_pitch=1e-6,
        )

        t0 = time.time()
        facets = LensGeometry.fresnel_facets(lens, 1)
        elapsed = time.time() - t0

        self.assertLessEqual(len(facets), 10000)
        self.assertLess(elapsed, 2.0)

    def test_from_dict_clamps_an_out_of_range_groove_pitch(self):
        lens = Lens.from_dict(
            {"name": "imported", "is_fresnel": True, "groove_pitch": 1e-6, "diameter": 20.0}
        )

        self.assertAlmostEqual(lens.groove_pitch, 0.01, places=6)

    def test_a_normal_pitch_is_unchanged(self):
        lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=20.0,
            is_fresnel=True,
            groove_pitch=0.5,
        )

        self.assertEqual(len(LensGeometry.fresnel_facets(lens, 1)), 20)


if __name__ == "__main__":
    unittest.main()
