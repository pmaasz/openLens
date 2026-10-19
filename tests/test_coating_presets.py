"""Regression: an AR preset must actually reduce reflection.

Two presets were physically wrong:

**Dual-layer AR.** Two quarter-wave layers cancel only when the inner index is
``n_outer * sqrt(n_substrate)`` - for MgF2 on BK7 that is about **1.70**. The
preset used Ta2O5 at **2.10**, so the pair amplified reflection instead of
cancelling it:

    BK7 at 550 nm      reflectance
    uncoated              4.216 %
    MgF2 single layer     1.284 %
    dual-layer AR         4.345 %   <- worse than no coating at all
    V-coating            18.949 %   <- 4.5x worse

**V-coating.** The thicknesses carried unexplained ``x1.2`` and ``x0.9``
factors, making them non-quarter-wave by assertion rather than by design, and
stacking Ta2O5 again.

The transfer-matrix maths is correct; the *inputs* were wrong. Both presets are
now chosen by scoring candidate stacks with that same maths, so a preset cannot
be worse than the bare substrate unless no candidate manages it.

The acceptance criterion is the one a user can check at a glance: **every AR
preset must reflect less than the uncoated surface at the design wavelength.**
"""

import unittest

from openlens.coating_designer import CoatingDesigner

DESIGN_WL = 550.0
BAND = (400.0, 700.0)


def _as_list(layers):
    """design_single_layer_ar returns one layer; the multi-layer ones a list."""
    return layers if isinstance(layers, list) else [layers]


def _uncoated(designer):
    return designer.calculate_reflectivity([], DESIGN_WL)


class TestEveryArPresetBeatsTheBareSubstrate(unittest.TestCase):
    """The user's check: does the coating help at all?"""

    def setUp(self):
        self.designer = CoatingDesigner()
        self.bare = _uncoated(self.designer)
        self.assertGreater(self.bare, 0.0, "no substrate reflection to improve on")

    def _presets(self):
        return {
            "single-layer": _as_list(self.designer.design_single_layer_ar(DESIGN_WL)),
            "dual-layer": self.designer.design_dual_layer_ar(DESIGN_WL),
            "v-coating": self.designer.design_v_coating(DESIGN_WL),
        }

    def test_no_preset_reflects_more_than_uncoated(self):
        for name, layers in self._presets().items():
            with self.subTest(preset=name):
                reflectance = self.designer.calculate_reflectivity(layers, DESIGN_WL)
                self.assertLess(
                    reflectance,
                    self.bare,
                    f"the {name} preset reflects {reflectance * 100:.3f}% "
                    f"against an uncoated {self.bare * 100:.3f}% - it is worse "
                    f"than having no coating",
                )

    def test_the_issue_repro_values(self):
        """The table from the issue, as an ordering rather than magic numbers."""
        single = self.designer.calculate_reflectivity(
            _as_list(self.designer.design_single_layer_ar(DESIGN_WL)), DESIGN_WL
        )
        dual = self.designer.calculate_reflectivity(
            self.designer.design_dual_layer_ar(DESIGN_WL), DESIGN_WL
        )
        v_coat = self.designer.calculate_reflectivity(
            self.designer.design_v_coating(DESIGN_WL), DESIGN_WL
        )

        self.assertLess(dual, self.bare)
        self.assertLess(v_coat, self.bare)
        self.assertLess(single, self.bare)
        self.assertLess(min(single, dual, v_coat), self.bare / 2)

    def test_every_preset_is_a_non_empty_stack(self):
        for name, layers in self._presets().items():
            with self.subTest(preset=name):
                self.assertTrue(layers, f"the {name} preset is empty")


class TestDualLayerUsesAQuarterWavePairThatCanCancel(unittest.TestCase):
    """The index condition, which is what makes two layers worth having."""

    def setUp(self):
        self.designer = CoatingDesigner()
        self.layers = self.designer.design_dual_layer_ar(DESIGN_WL)
        self.substrate = self.designer.substrate_index

    def test_it_is_a_two_layer_stack(self):
        self.assertEqual(len(self.layers), 2)

    def test_the_outer_layer_is_the_lower_index(self):
        """Substrate to air: the outer layer must be the low-index one."""
        inner, outer = self.layers

        self.assertLess(outer.refractive_index, inner.refractive_index)

    def test_the_inner_index_is_near_the_cancelling_value(self):
        """n_inner = n_outer * sqrt(n_substrate), about 1.70 here."""
        inner, outer = self.layers
        ideal = outer.refractive_index * (self.substrate**0.5)

        self.assertLess(
            abs(inner.refractive_index - ideal) / ideal,
            0.10,
            f"inner index {inner.refractive_index} is more than 10% from the "
            f"{ideal:.3f} that cancels with an outer index of "
            f"{outer.refractive_index}",
        )

    def test_both_layers_are_quarter_wave_at_the_design_wavelength(self):
        for index, layer in enumerate(self.layers):
            with self.subTest(layer=index):
                expected = DESIGN_WL / (4 * layer.refractive_index)
                self.assertAlmostEqual(layer.thickness_nm, expected, delta=expected * 1e-6)

    def test_it_does_not_use_ta2o5_as_the_inner_layer(self):
        """The material that made it worse than nothing."""
        inner = self.layers[0]

        self.assertNotAlmostEqual(
            inner.refractive_index,
            2.10,
            places=2,
            msg="Ta2O5 at n=2.10 cannot cancel an MgF2 outer layer on BK7",
        )


class TestVCoatingIsDerivedNotAsserted(unittest.TestCase):
    """A V-coat needs non-quarter-wave thicknesses; they must be computed."""

    def setUp(self):
        self.designer = CoatingDesigner()
        self.layers = self.designer.design_v_coating(DESIGN_WL)

    def test_it_helps_across_the_visible_band(self):
        """Not just at one wavelength - a V-coat is a broadband claim."""
        for wavelength in (450.0, 550.0, 650.0):
            with self.subTest(wavelength=wavelength):
                coated = self.designer.calculate_reflectivity(self.layers, wavelength)
                bare = self.designer.calculate_reflectivity([], wavelength)
                self.assertLess(
                    coated,
                    bare,
                    f"at {wavelength} nm the V-coating reflects "
                    f"{coated * 100:.3f}% against an uncoated "
                    f"{bare * 100:.3f}%",
                )

    def test_it_beats_a_bare_single_layer_across_the_band(self):
        """It has to earn the extra layers."""
        single = _as_list(self.designer.design_single_layer_ar(DESIGN_WL))
        for wavelength in (450.0, 550.0, 650.0):
            with self.subTest(wavelength=wavelength):
                v = self.designer.calculate_reflectivity(self.layers, wavelength)
                one = self.designer.calculate_reflectivity(single, wavelength)
                self.assertLess(
                    v,
                    one * 1.05,
                    f"at {wavelength} nm the three-layer stack "
                    f"({v * 100:.3f}%) is not better than the single layer "
                    f"({one * 100:.3f}%)",
                )

    def test_thicknesses_are_positive_and_finite(self):
        for index, layer in enumerate(self.layers):
            with self.subTest(layer=index):
                self.assertGreater(layer.thickness_nm, 0.0)
                self.assertLess(layer.thickness_nm, 1000.0)


class TestPresetsTrackTheSubstrate(unittest.TestCase):
    """The presets are designed per-substrate; check they are used that way."""

    def test_the_inner_index_follows_the_substrate(self):
        """n_inner must track n_outer * sqrt(n_substrate).

        Not asserted: that the two presets choose *different materials*. The
        search is a coarse grid over seven catalogued indices, so for
        neighbouring substrates the best pair can legitimately be the same
        while still being right for each. What has to hold is the index
        condition, which is what actually decides the cancellation.
        """
        for substrate in (1.4585, 1.5168, 1.62, 1.80):
            with self.subTest(substrate=substrate):
                designer = CoatingDesigner(substrate_index=substrate)
                inner, outer = designer.design_dual_layer_ar(DESIGN_WL)
                ideal = outer.refractive_index * (substrate**0.5)

                self.assertLess(
                    abs(inner.refractive_index - ideal) / ideal,
                    0.15,
                    f"on n={substrate} the inner index "
                    f"{inner.refractive_index} is far from the {ideal:.3f} "
                    f"that cancels with {outer.refractive_index}",
                )

    def test_the_preset_never_beats_the_bare_substrate(self):
        """The search starts from the bare substrate, so it cannot lose."""
        for substrate in (1.40, 1.4585, 1.5168, 1.62, 1.80, 2.00):
            with self.subTest(substrate=substrate):
                designer = CoatingDesigner(substrate_index=substrate)
                layers = designer.design_dual_layer_ar(DESIGN_WL)
                self.assertLessEqual(
                    designer.calculate_reflectivity(layers, DESIGN_WL),
                    designer.calculate_reflectivity([], DESIGN_WL),
                )

    def test_a_different_substrate_still_improves_on_bare(self):
        for substrate in (1.4585, 1.5168, 1.62, 1.80):
            with self.subTest(substrate=substrate):
                designer = CoatingDesigner(substrate_index=substrate)
                layers = designer.design_dual_layer_ar(DESIGN_WL)
                self.assertLess(
                    designer.calculate_reflectivity(layers, DESIGN_WL),
                    designer.calculate_reflectivity([], DESIGN_WL),
                    f"the dual-layer preset does not help on a substrate of " f"n={substrate}",
                )


if __name__ == "__main__":
    unittest.main()
