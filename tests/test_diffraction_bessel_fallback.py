"""#477: the no-scipy Bessel fallbacks must vectorise, not recurse per pixel.

Without scipy, array inputs to j0() and j1() walked ``arr.flat`` in Python
and evaluated the series once per element - 65,536 interpreter-level calls
for a default 256x256 PSF. The fallbacks are now module-level functions,
keep the scalar fast path, and evaluate whole arrays with numpy masks.
These tests call them directly, so they run whether or not scipy is
installed.
"""

import unittest
from unittest import mock

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:  # pragma: no cover - optional dependency guard
    HAS_NUMPY = False
    np = None  # type: ignore[assignment]

from openlens import diffraction


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestJ1Fallback(unittest.TestCase):
    def test_scalar_series_values_match_reference(self):
        """|x| < 8 uses the series branch; reference values from scipy."""
        cases = [
            (0.0, 0.0),
            (1.0, 0.4400505857449335),
            (3.0, 0.33905895852593646),
            (5.0, -0.3275791375914652),
            (-2.5, -0.4970941024642741),
        ]
        for x, expected in cases:
            with self.subTest(x=x):
                self.assertAlmostEqual(diffraction._j1_fallback(x), expected, places=9)

    def test_scalar_asymptotic_values_are_a_close_approximation(self):
        """|x| >= 8 uses the asymptotic branch, which is approximate."""
        self.assertAlmostEqual(diffraction._j1_fallback(10.0), 0.043472746168861445, delta=0.012)
        self.assertAlmostEqual(diffraction._j1_fallback(-10.0), -0.043472746168861445, delta=0.012)
        # The approximation tightens as the argument grows.
        self.assertAlmostEqual(diffraction._j1_fallback(50.0), -0.09751182812517517, delta=0.001)
        self.assertAlmostEqual(diffraction._j1_fallback(-50.0), 0.09751182812517517, delta=0.001)

    def test_vector_path_matches_the_scalar_path(self):
        xs = np.array([0.0, 1e-15, 0.5, 7.999, 8.0, 12.0, 40.0, -2.5, -9.5])
        vector = diffraction._j1_fallback(xs)
        scalar = np.array([diffraction._j1_fallback(float(x)) for x in xs])
        np.testing.assert_allclose(vector, scalar, rtol=0.0, atol=1e-12)

    def test_a_large_array_never_touches_the_scalar_path(self):
        """Per-element recursion would hit _j1_scalar 65,536 times."""
        with mock.patch.object(
            diffraction, "_j1_scalar", side_effect=AssertionError("scalar path used")
        ):
            values = diffraction._j1_fallback(np.linspace(0.0, 100.0, 65536))
        self.assertEqual(values.shape, (65536,))


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestJ0Fallback(unittest.TestCase):
    def test_scalar_series_values_match_reference(self):
        """|x| < 8 uses the series branch; reference values from scipy."""
        cases = [
            (0.0, 1.0),
            (1.0, 0.7651976865579666),
            (2.0, 0.22389077914123567),
            (5.0, -0.1775967713143383),
        ]
        for x, expected in cases:
            with self.subTest(x=x):
                self.assertAlmostEqual(diffraction._j0_fallback(x), expected, places=9)

    def test_negative_arguments_fold_to_the_even_function(self):
        """J0 is even; the previous asymptotic branch took sqrt of a negative."""
        self.assertAlmostEqual(
            diffraction._j0_fallback(-10.0), diffraction._j0_fallback(10.0), places=12
        )
        self.assertAlmostEqual(diffraction._j0_fallback(-2.0), 0.22389077914123567, places=9)

    def test_scalar_asymptotic_values_are_a_close_approximation(self):
        """|x| >= 8 uses the asymptotic branch, which is approximate."""
        self.assertAlmostEqual(diffraction._j0_fallback(10.0), -0.2459357644513483, delta=0.002)

    def test_vector_path_matches_the_scalar_path(self):
        xs = np.array([0.0, 1e-15, 0.5, 7.999, 8.0, 12.0, 40.0, -2.5, -9.5])
        vector = diffraction._j0_fallback(xs)
        scalar = np.array([diffraction._j0_fallback(float(x)) for x in xs])
        np.testing.assert_allclose(vector, scalar, rtol=0.0, atol=1e-12)

    def test_a_large_array_never_touches_the_scalar_path(self):
        """Per-element recursion would hit _j0_scalar 65,536 times."""
        with mock.patch.object(
            diffraction, "_j0_scalar", side_effect=AssertionError("scalar path used")
        ):
            values = diffraction._j0_fallback(np.linspace(0.0, 100.0, 65536))
        self.assertEqual(values.shape, (65536,))


@unittest.skipUnless(HAS_NUMPY, "numpy not available")
class TestPSFUsesTheVectorisedFallback(unittest.TestCase):
    def test_psf_pattern_is_unchanged_when_j1_is_swapped(self):
        """compute_psf must draw the same pattern through the fallback.

        Only the asymptotic tail (v > 8, where the PSF is already tiny)
        differs from scipy, so a generous absolute bound is enough.
        """
        calculator = diffraction.DiffractionCalculator(wavelength_m=550e-9)
        reference = calculator.point_spread_function_2d(
            size_um=20.0, focal_length_mm=50.0, aperture_diameter_mm=10.0, pixels=64
        )
        with mock.patch.object(diffraction, "j1", diffraction._j1_fallback):
            approximated = calculator.point_spread_function_2d(
                size_um=20.0, focal_length_mm=50.0, aperture_diameter_mm=10.0, pixels=64
            )

        self.assertEqual(approximated.shape, reference.shape)
        self.assertLess(float(np.max(np.abs(approximated - reference))), 0.01)


if __name__ == "__main__":
    unittest.main()
