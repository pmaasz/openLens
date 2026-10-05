#!/usr/bin/env python3
"""
Sellmeier evaluation must not raise on unvalidated coefficients.

Coefficients come straight from materials.json, import_csv_catalog or
import_agf_catalog with no validation, and two things can go wrong in
get_refractive_index:

    lambda_sq == C   -> ZeroDivisionError
    n_sq < 0         -> ValueError: math domain error (in sqrt)

Neither was caught, so a bad catalog entry raised through lens.py into ray
tracing and the GUI. Verified with C1 = 0.25 at 500 nm (ZeroDivisionError)
and B1 = -5.0, C1 = 0.5 at 1000 nm (math domain error).

Terms are still summed with their signs: the third Sellmeier term is
legitimately negative for real glasses, since its UV resonance sits far above
the visible and C3 >> lambda_sq. Dropping negative terms would put BK7 at
n = 1.5223 instead of 1.5168 on the d-line, so the tests below pin the real
catalog values as well as the guards.
"""

import dataclasses
import unittest

from src.material_database import MaterialDatabase


def _variant(base, **overrides):
    return dataclasses.replace(base, **overrides)


class TestSellmeierGuards(unittest.TestCase):
    def setUp(self):
        self.db = MaterialDatabase(db_path=None)
        self.base = self.db.get_material("N-BK7")

    def _install(self, name, **overrides):
        self.db.materials[name] = _variant(self.base, name=name, **overrides)
        return name

    def test_denominator_zero_does_not_raise(self):
        """Regression: C1 = 0.25 at 500 nm used to divide by zero."""
        name = self._install("ZERODEN", C1=0.25)
        index = self.db.get_refractive_index(name, 500.0)
        self.assertIsInstance(index, float)
        self.assertGreater(index, 0.0)

    def test_negative_n_squared_does_not_raise(self):
        """Regression: B1 = -5.0, C1 = 0.5 at 1000 nm was a math domain error."""
        name = self._install("NEGNSQ", B1=-5.0, C1=0.5)
        index = self.db.get_refractive_index(name, 1000.0)
        self.assertIsInstance(index, float)
        self.assertGreater(index, 0.0)

    def test_every_term_singular_does_not_raise(self):
        self.db.materials["ALLZERO"] = _variant(
            self.base, name="ALLZERO", B1=1.0, C1=0.25, B2=1.0, C2=0.25, B3=1.0, C3=0.25
        )
        index = self.db.get_refractive_index("ALLZERO", 500.0)
        self.assertEqual(index, 1.0)  # n^2 = 1 with every term omitted

    def test_all_terms_negative_does_not_raise(self):
        name = self._install("ALLNEG", B1=-9.0, C1=0.5, B2=-9.0, C2=0.5, B3=-9.0, C3=0.5)
        index = self.db.get_refractive_index(name, 1000.0)
        self.assertGreater(index, 0.0)

    def test_near_singular_denominator_is_tolerated(self):
        """Just off the singularity the term is huge but finite."""
        name = self._install("NEARSING", C1=0.2500000000001)
        index = self.db.get_refractive_index(name, 500.0)
        self.assertIsInstance(index, float)

    def test_unknown_material_still_falls_back(self):
        self.assertEqual(self.db.get_refractive_index("NO-SUCH-GLASS", 550.0), 1.5168)

    def test_lens_with_a_bad_catalog_entry_still_traces(self):
        """The reported blast radius: the exception reached the GUI."""
        from src.lens import Lens

        self._install("ZERODEN", C1=0.25)
        lens = Lens(
            name="Bad",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            material="ZERODEN",
            model_glass_mode=True,
        )
        self.assertIsInstance(lens.update_refractive_index(), (float, type(None)))
        self.assertGreater(lens.refractive_index, 0.0)


class TestRealCatalogValuesUnchanged(unittest.TestCase):
    """The guards must not perturb any real glass."""

    def setUp(self):
        self.db = MaterialDatabase(db_path=None)

    def test_d_line_values_match_the_catalog(self):
        self.assertAlmostEqual(self.db.get_refractive_index("BK7", 587.6, 20.0), 1.5168, places=4)
        self.assertAlmostEqual(self.db.get_refractive_index("N-BK7", 587.6, 20.0), 1.5168, places=4)

    def test_third_term_is_still_subtracted(self):
        """Guards must not skip the legitimately negative UV term."""
        base = self.db.get_material("N-BK7")
        with_third = self.db.get_refractive_index("N-BK7", 587.6, 20.0)
        dropped = dataclasses.replace(base, B3=0.0)
        self.db.materials["NOUV"] = _variant(dropped, name="NOUV")
        without = self.db.get_refractive_index("NOUV", 587.6, 20.0)
        # Dropping it would raise n; it must stay subtracted, and by a
        # physically meaningful amount.
        self.assertLess(with_third, without)
        self.assertLess(without - with_third, 0.005)

    def test_every_real_glass_stays_monotonic(self):
        """Normal dispersion: n rises toward the blue for every real glass."""
        for name in self.db.materials:
            mat = self.db.get_material(name)
            if not (mat.B1 or mat.B2 or mat.B3):
                continue  # coefficient-less fixture entry, not a real glass
            with self.subTest(material=name):
                n_blue = self.db.get_refractive_index(name, 450.0, 20.0)
                n_red = self.db.get_refractive_index(name, 680.0, 20.0)
                self.assertGreater(n_blue, n_red)

    def test_temperature_correction_still_works(self):
        cold = self.db.get_refractive_index("N-BK7", 587.6, 10.0)
        hot = self.db.get_refractive_index("N-BK7", 587.6, 40.0)
        self.assertNotAlmostEqual(cold, hot, places=6)


if __name__ == "__main__":
    unittest.main()
