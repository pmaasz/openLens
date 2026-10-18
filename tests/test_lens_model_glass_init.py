"""Regression: the Lens constructor must honour model-glass mode.

Two defects, both about the constructor disagreeing with the methods that
follow it.

**Model glass.** The constructor recorded ``model_glass_mode`` and ``model_nd``
but resolved the working ``refractive_index`` from the material. So a BK7-named
model-glass lens with ``model_nd=1.7`` started at ``n=1.5168`` and only reached
``n~1.7`` after ``update_refractive_index()`` - a focal length of 97.58 mm
becoming 72.17 mm, with nothing in between to say why.

**Type presets.** ``use_type_defaults`` called ``_update_radii_for_type()``
*before* the parabolic flags and sags were assigned, so the reset the method
performs could not touch them. A plano-convex preset built with
``is_parabolic_1=True`` kept its paraboloid, while calling
``set_lens_type("Plano-Convex")`` afterwards cleared it. The two paths for the
same intent disagreed.
"""

import unittest

from src.constants import WAVELENGTH_D_LINE
from src.lens import Lens


class TestModelGlassModeStartsWithItsOwnIndex(unittest.TestCase):
    """A model-glass lens is defined by its nd/vd, not by its material name."""

    def _lens(self, **kwargs):
        options = dict(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="BK7",
            model_glass_mode=True,
            model_nd=1.7,
            model_vd=64.17,
        )
        options.update(kwargs)
        return Lens(**options)

    def test_the_index_comes_from_the_model_not_the_material(self):
        lens = self._lens()

        self.assertAlmostEqual(
            lens.refractive_index,
            1.7,
            delta=0.01,
            msg=f"a model-glass lens started at n={lens.refractive_index}, which "
            f"is BK7's index, not its own model_nd",
        )

    def test_the_index_does_not_change_on_the_first_update(self):
        """The whole defect: the constructor and the first update disagreed."""
        lens = self._lens()

        before = lens.refractive_index
        lens.update_refractive_index()
        after = lens.refractive_index

        self.assertAlmostEqual(
            before,
            after,
            delta=1e-6,
            msg=f"the constructor gave n={before} but update_refractive_index() "
            f"moved it to {after}; the lens jumps focal length on first use",
        )

    def test_the_focal_length_is_the_same_before_and_after_an_update(self):
        lens = self._lens()

        before = lens.calculate_focal_length()
        lens.update_refractive_index()
        after = lens.calculate_focal_length()

        self.assertIsNotNone(before)
        self.assertAlmostEqual(
            before,
            after,
            places=3,
            msg=f"EFL was {before:.2f} mm at construction and {after:.2f} mm "
            f"after the first update",
        )

    def test_two_model_glasses_with_different_nd_differ(self):
        low = self._lens(model_nd=1.50)
        high = self._lens(model_nd=1.80)

        self.assertNotAlmostEqual(
            low.refractive_index,
            high.refractive_index,
            places=2,
            msg="two model glasses with different nd started at the same index",
        )

    def test_an_explicit_index_still_wins(self):
        """Precedence: an explicit index overrides everything, for round-trips."""
        lens = self._lens(refractive_index=1.62)

        self.assertAlmostEqual(lens.refractive_index, 1.62, places=9)

    def test_a_real_glass_is_unaffected(self):
        """Without model-glass mode the material still decides."""
        lens = Lens(material="BK7", refractive_index=None)

        self.assertAlmostEqual(
            lens.refractive_index, 1.5168, delta=1e-3, msg="BK7 moved off its index"
        )

    def test_the_default_construction_is_unaffected(self):
        lens = Lens()

        self.assertAlmostEqual(lens.refractive_index, 1.5168, delta=1e-3)

    def test_refractive_index_at_agrees_with_the_stored_index(self):
        """The non-mutating accessor and the stored value must not diverge."""
        lens = self._lens()

        self.assertAlmostEqual(
            lens.refractive_index_at(WAVELENGTH_D_LINE),
            lens.refractive_index,
            delta=1e-6,
        )


class TestTypePresetAndParabolicSurfaces(unittest.TestCase):
    """A type preset is spherical, so it and a paraboloid cannot both apply."""

    def test_use_type_defaults_matches_set_lens_type(self):
        """The two paths for the same intent must agree.

        The constructor applies the preset before the parabolic properties are
        assigned, so the reset inside _update_radii_for_type() has nothing to
        clear. set_lens_type() applies it afterwards and does clear them.
        """
        constructed = Lens(
            lens_type="Plano-Convex",
            use_type_defaults=True,
            is_parabolic_1=True,
            parabolic_sag_1=4.0,
        )
        changed = Lens(is_parabolic_1=True, parabolic_sag_1=4.0)
        changed.set_lens_type("Plano-Convex")

        self.assertFalse(
            constructed.is_parabolic_1,
            "the constructor kept a paraboloid that set_lens_type would have "
            "cleared, so the same preset behaves differently depending on how "
            "it was applied",
        )
        self.assertEqual(
            constructed.is_parabolic_1,
            changed.is_parabolic_1,
            msg="the constructor and set_lens_type disagree about the preset",
        )
        self.assertAlmostEqual(
            constructed.get_effective_radius_1(),
            changed.get_effective_radius_1(),
            places=6,
            msg="the effective radius differs between the two paths",
        )

    def test_the_preset_clears_the_sag_too(self):
        lens = Lens(
            lens_type="Plano-Convex",
            use_type_defaults=True,
            is_parabolic_1=True,
            parabolic_sag_1=4.0,
            is_parabolic_2=True,
            parabolic_sag_2=2.0,
        )

        self.assertFalse(lens.is_parabolic_1)
        self.assertFalse(lens.is_parabolic_2)
        self.assertEqual(lens.parabolic_sag_1, 0.0)
        self.assertEqual(lens.parabolic_sag_2, 0.0)

    def test_parabolic_surfaces_survive_without_the_preset(self):
        """The default path must not touch the caller's surfaces."""
        lens = Lens(
            lens_type="Plano-Convex",
            use_type_defaults=False,
            is_parabolic_1=True,
            parabolic_sag_1=4.0,
        )

        self.assertTrue(
            lens.is_parabolic_1,
            "a paraboloid was cleared without the caller asking for a preset",
        )
        self.assertAlmostEqual(lens.parabolic_sag_1, 4.0, places=6)

    def test_the_preset_still_sets_the_radii(self):
        lens = Lens(
            lens_type="Plano-Convex",
            use_type_defaults=True,
            radius_of_curvature_1=999.0,
            radius_of_curvature_2=888.0,
        )

        self.assertNotAlmostEqual(lens.radius_of_curvature_1, 999.0)
        self.assertNotAlmostEqual(lens.radius_of_curvature_2, 888.0)

    def test_an_unknown_type_preserves_everything(self):
        lens = Lens(
            lens_type="Biconvex",
            radius_of_curvature_1=123.0,
            radius_of_curvature_2=-123.0,
        )

        self.assertAlmostEqual(lens.radius_of_curvature_1, 123.0, places=6)
        self.assertAlmostEqual(lens.radius_of_curvature_2, -123.0, places=6)


if __name__ == "__main__":
    unittest.main()
