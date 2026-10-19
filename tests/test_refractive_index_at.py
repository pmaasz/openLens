"""Regression: refractive_index_at must not invent an index for an unknown material.

``refractive_index_at`` queried the material database for whatever string the
lens carried. When the material is not in the catalog, the lookup fell back to
a BK7 default and returned it - so a lens explicitly given its own index was
silently given a different one:

    Lens(material="Custom", refractive_index=1.7).refractive_index_at(587.6)
    # -> 1.5168, not 1.7

The stored index is what the tracer uses, so wavelength-dependent calculations
disagreed with the geometry. A material that is not in the catalog must keep the
index it was given.
"""

import unittest

from openlens.lens import Lens


class TestUnknownMaterialKeepsItsIndex(unittest.TestCase):
    """A material the catalog does not have must not borrow BK7's index."""

    def test_an_explicit_index_is_kept(self):
        lens = Lens(material="Custom", refractive_index=1.7)

        self.assertAlmostEqual(lens.refractive_index_at(587.6), 1.7, places=6)

    def test_the_index_is_kept_at_every_wavelength(self):
        """Not just at the d-line - the whole point is the stored value."""
        lens = Lens(material="Nonexistent-Glass", refractive_index=1.9)

        for wavelength in (486.1, 587.6, 656.3):
            with self.subTest(wavelength=wavelength):
                self.assertAlmostEqual(lens.refractive_index_at(wavelength), 1.9, places=6)

    def test_a_known_material_still_uses_the_catalog(self):
        """The fix must not disable the lookup for real glasses."""
        lens = Lens(material="BK7", refractive_index=1.5168)

        index = lens.refractive_index_at(587.6)

        self.assertAlmostEqual(index, 1.5168, delta=0.002)

    def test_a_known_material_keeps_its_dispersion(self):
        """Blue must still refract more than red - that needs the catalog."""
        lens = Lens(material="BK7", refractive_index=1.5168)

        blue = lens.refractive_index_at(486.1)
        red = lens.refractive_index_at(656.3)

        self.assertGreater(blue, red)

    def test_model_glass_mode_is_unaffected(self):
        """Model glass computes from nd/vd, not from the catalog."""
        lens = Lens(
            material="Whatever",
            refractive_index=1.5,
            model_glass_mode=True,
            model_nd=1.6200,
            model_vd=60.3,
        )

        index = lens.refractive_index_at(587.6)

        self.assertAlmostEqual(index, 1.6200, delta=0.01)


if __name__ == "__main__":
    unittest.main()
