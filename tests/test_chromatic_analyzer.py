#!/usr/bin/env python3
"""
Functional tests for Chromatic Analyzer
Tests wavelength-dependent calculations and chromatic aberration analysis
"""

import math
import unittest

from openlens.chromatic_analyzer import ChromaticAnalyzer, ChromaticResult
from openlens.material_database import MaterialDatabase


class TestChromaticAnalyzer(unittest.TestCase):
    """Test chromatic aberration analysis"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = ChromaticAnalyzer()
        self.material_db = MaterialDatabase()

    def test_wavelength_constants(self):
        """Test that standard wavelengths are defined"""
        self.assertIn("d", ChromaticAnalyzer.WAVELENGTHS)
        self.assertIn("F", ChromaticAnalyzer.WAVELENGTHS)
        self.assertIn("C", ChromaticAnalyzer.WAVELENGTHS)
        self.assertEqual(ChromaticAnalyzer.WAVELENGTHS["d"], 587.6)
        self.assertEqual(ChromaticAnalyzer.WAVELENGTHS["F"], 486.1)
        self.assertEqual(ChromaticAnalyzer.WAVELENGTHS["C"], 656.3)

    def test_abbe_number_calculation(self):
        """Test Abbe number calculation for BK7"""
        abbe = self.analyzer.calculate_abbe_number("BK7")
        # BK7 should have Abbe number around 64
        self.assertGreater(abbe, 60)
        self.assertLess(abbe, 68)

    def test_abbe_number_flint_vs_crown(self):
        """Test that flint glass has lower Abbe number than crown"""
        abbe_bk7 = self.analyzer.calculate_abbe_number("BK7")  # Crown
        abbe_f2 = self.analyzer.calculate_abbe_number("F2")  # Flint

        # Crown should have higher Abbe number (lower dispersion)
        self.assertGreater(abbe_bk7, abbe_f2)

        # F2 should have Abbe number around 36
        self.assertGreater(abbe_f2, 30)
        self.assertLess(abbe_f2, 40)

    def test_partial_dispersion(self):
        """Test partial dispersion calculation"""
        partial = self.analyzer.calculate_partial_dispersion("BK7", "g", "F")

        # Partial dispersion should be positive and reasonable
        self.assertGreater(partial, 0)
        self.assertLess(partial, 1)

    def test_refractive_index_wavelength_dependence(self):
        """Test that refractive index varies with wavelength"""
        # Blue light should have higher refractive index than red (normal dispersion)
        n_blue = self.material_db.get_refractive_index("BK7", 450)
        n_green = self.material_db.get_refractive_index("BK7", 550)
        n_red = self.material_db.get_refractive_index("BK7", 650)

        self.assertGreater(n_blue, n_green)
        self.assertGreater(n_green, n_red)

    def test_refractive_index_temperature_dependence(self):
        """Test that refractive index varies with temperature"""
        n_20c = self.material_db.get_refractive_index("BK7", 587.6, 20)
        n_50c = self.material_db.get_refractive_index("BK7", 587.6, 50)

        # Should be different (actual sign depends on material)
        self.assertNotEqual(n_20c, n_50c)

        # Change should be small but measurable
        delta_n = abs(n_50c - n_20c)
        self.assertGreater(delta_n, 1e-6)
        self.assertLess(delta_n, 1e-2)

    def test_achromatic_doublet_design(self):
        """Test achromatic doublet design"""
        focal_length = 100.0  # mm
        doublet = self.analyzer.design_achromatic_doublet(focal_length, "BK7", "F2")

        # Check structure
        self.assertIn("crown_element", doublet)
        self.assertIn("flint_element", doublet)

        # Crown element should be positive (converging)
        self.assertGreater(doublet["crown_element"]["power"], 0)

        # Flint element should be negative (diverging)
        self.assertLess(doublet["flint_element"]["power"], 0)

        # Total focal length should match
        self.assertAlmostEqual(doublet["total_focal_length"], focal_length, places=1)

        # Total power should be 1/f
        expected_power = 1.0 / focal_length
        self.assertAlmostEqual(doublet["total_power"], expected_power, places=6)

    def test_achromatic_condition(self):
        """Test that achromatic doublet satisfies chromatic correction"""
        doublet = self.analyzer.design_achromatic_doublet(100.0, "BK7", "F2")

        # For achromatic doublet: φ1/V1 + φ2/V2 = 0
        phi1 = doublet["crown_element"]["power"]
        phi2 = doublet["flint_element"]["power"]
        V1 = doublet["crown_element"]["abbe_number"]
        V2 = doublet["flint_element"]["abbe_number"]

        chromatic_sum = phi1 / V1 + phi2 / V2

        # Should be very close to zero
        self.assertAlmostEqual(chromatic_sum, 0.0, places=8)

    def test_chromatic_focal_shift(self):
        """Test chromatic focal shift calculation"""
        lens_params = {
            "radius1": 50.0,
            "radius2": -50.0,
            "thickness": 5.0,
            "diameter": 25.0,
            "material": "BK7",
        }

        result = self.analyzer.plot_chromatic_focal_shift(
            lens_params, wavelength_range=(450, 650), num_points=5
        )

        # Check structure
        self.assertIn("wavelengths", result)
        self.assertIn("focal_lengths", result)
        self.assertEqual(len(result["wavelengths"]), 5)
        self.assertEqual(len(result["focal_lengths"]), 5)

        # Wavelengths should span the range
        self.assertAlmostEqual(result["wavelengths"][0], 450, places=1)
        self.assertAlmostEqual(result["wavelengths"][-1], 650, places=1)

        # Focal lengths should be positive and vary
        for f in result["focal_lengths"]:
            self.assertGreater(f, 0)

        # Should show dispersion (different focal lengths)
        focal_range = max(result["focal_lengths"]) - min(result["focal_lengths"])
        self.assertGreater(focal_range, 0)

    def test_transmission_data(self):
        """Test transmission data retrieval"""
        # BK7 has transmission data
        trans_400 = self.material_db.get_transmission("BK7", 400)
        trans_600 = self.material_db.get_transmission("BK7", 600)

        # Should be between 0 and 1
        self.assertGreaterEqual(trans_400, 0)
        self.assertLessEqual(trans_400, 1)
        self.assertGreaterEqual(trans_600, 0)
        self.assertLessEqual(trans_600, 1)

        # Visible light should have high transmission
        self.assertGreater(trans_600, 0.9)

    def test_transmission_interpolation(self):
        """Test that transmission is interpolated correctly"""
        # Get transmission at wavelength between data points
        trans = self.material_db.get_transmission("BK7", 550)

        # Should be reasonable
        self.assertGreater(trans, 0.9)
        self.assertLessEqual(trans, 1.0)

    def test_analyze_lens_thick_focal_lengths(self):
        """Focal lengths must use the thick lensmaker equation."""
        from openlens.lens import Lens

        lens_params = {
            "radius1": 50.0,
            "radius2": -50.0,
            "thickness": 5.0,
            "diameter": 25.0,
            "material": "BK7",
        }
        result = self.analyzer.analyze_lens(lens_params)

        n_d = self.material_db.get_refractive_index("BK7", 587.6, 20.0)
        expected = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=n_d,
            material="BK7",
        ).calculate_focal_length()

        # d-line is the middle wavelength (F, d, C default order)
        self.assertAlmostEqual(result.focal_lengths[1], expected, places=6)
        # Thin model would give ~48.37; thick gives ~49.21 (1.7% apart)
        self.assertGreater(result.focal_lengths[1], 49.0)

    def test_analyze_lens_spot_scales_with_aperture(self):
        """RMS spots must grow with aperture (no f-scaled placeholder)."""
        base = {
            "radius1": 50.0,
            "radius2": -50.0,
            "thickness": 5.0,
            "material": "BK7",
        }
        small = self.analyzer.analyze_lens(dict(base, diameter=10.0))
        large = self.analyzer.analyze_lens(dict(base, diameter=20.0))

        for s_small, s_large in zip(small.spot_sizes, large.spot_sizes):
            self.assertGreater(s_large, 2.0 * s_small)
        # And differ per wavelength (dispersion, not a constant factor)
        self.assertNotAlmostEqual(small.spot_sizes[0], small.spot_sizes[2], delta=1e-6)

    def test_analyze_lens_chromatic_metrics(self):
        """Axial shift must match f/V order; lateral color physical."""
        lens_params = {
            "radius1": 50.0,
            "radius2": -50.0,
            "thickness": 5.0,
            "diameter": 25.0,
            "material": "BK7",
        }
        result = self.analyzer.analyze_lens(lens_params)

        # Axial F-C shift ~= f_d / Vd to first order (within 10%)
        f_d = result.focal_lengths[1]
        abbe = self.analyzer.calculate_abbe_number("BK7")
        self.assertAlmostEqual(
            result.axial_chromatic_aberration, f_d / abbe, delta=0.1 * f_d / abbe
        )
        # Lateral color is the chief ray's image-height difference, not a
        # bundle centroid: the chief ray passes through the front vertex, so
        # only the second-surface chromatic deviation contributes (~3 um).
        self.assertAlmostEqual(result.lateral_color, 0.002995446, places=6)

    def test_analyze_lens_afocal_raises(self):
        """Afocal geometry (flat window) raises instead of returning zeros."""
        with self.assertRaises(ValueError):
            self.analyzer.analyze_lens(
                {
                    "radius1": float("inf"),
                    "radius2": float("inf"),
                    "thickness": 5.0,
                    "diameter": 25.0,
                    "material": "BK7",
                }
            )

    def test_chromatic_result_structure(self):
        """Test ChromaticResult data structure"""
        result = ChromaticResult(
            wavelengths=[450, 550, 650],
            focal_lengths=[100.1, 100.0, 99.9],
            focal_shift=0.2,
            lateral_color=0.05,
            spot_sizes=[0.01, 0.008, 0.012],
            transverse_aberration=[0.02, 0.015, 0.025],
            axial_chromatic_aberration=0.2,
        )

        # Test to_dict conversion
        result_dict = result.to_dict()
        self.assertIn("wavelengths", result_dict)
        self.assertIn("focal_lengths", result_dict)
        self.assertIn("focal_shift", result_dict)
        self.assertEqual(result_dict["focal_shift"], 0.2)

    def test_multiple_materials(self):
        """Test analysis with different materials"""
        materials = ["BK7", "F2", "FUSEDSILICA"]

        for material in materials:
            # Should be able to calculate Abbe number
            abbe = self.analyzer.calculate_abbe_number(material)
            self.assertGreater(abbe, 0)
            self.assertLess(abbe, 100)

            # Should be able to get refractive indices
            n = self.material_db.get_refractive_index(material, 587.6)
            self.assertGreater(n, 1.0)
            self.assertLess(n, 3.0)

    def test_uv_material_fused_silica(self):
        """Test that fused silica works in UV range"""
        # Fused silica should transmit UV
        trans_250 = self.material_db.get_transmission("FUSEDSILICA", 250)
        trans_200 = self.material_db.get_transmission("FUSEDSILICA", 200)

        # Should have reasonable UV transmission
        self.assertGreater(trans_250, 0.8)
        self.assertGreater(trans_200, 0.5)

        # Can calculate refractive index in UV
        n_uv = self.material_db.get_refractive_index("FUSEDSILICA", 250)
        n_vis = self.material_db.get_refractive_index("FUSEDSILICA", 550)

        # UV should have higher index
        self.assertGreater(n_uv, n_vis)

    def test_high_index_material(self):
        """Test high refractive index material (S-LAH79)"""
        n = self.material_db.get_refractive_index("S-LAH79", 587.6)

        # Should be high index (around 2.0, but may be slightly less depending on Sellmeier fit)
        self.assertGreater(n, 1.9)
        self.assertLess(n, 2.1)

        # Should have low Abbe number (high dispersion)
        abbe = self.analyzer.calculate_abbe_number("S-LAH79")
        self.assertGreater(abbe, 25)
        self.assertLess(abbe, 32)

    def test_extreme_wavelengths(self):
        """Test behavior at extreme wavelengths"""
        # Near UV
        n_uv = self.material_db.get_refractive_index("BK7", 380)

        # Near IR
        n_ir = self.material_db.get_refractive_index("BK7", 1000)

        # Both should be reasonable
        self.assertGreater(n_uv, 1.4)
        self.assertLess(n_uv, 1.7)
        self.assertGreater(n_ir, 1.4)
        self.assertLess(n_ir, 1.6)

        # UV should have higher index
        self.assertGreater(n_uv, n_ir)


class TestMaterialDatabase(unittest.TestCase):
    """Test material database functionality"""

    def setUp(self):
        self.db = MaterialDatabase()

    def test_load_builtin_materials(self):
        """Test that built-in materials are loaded"""
        materials = self.db.list_materials()

        # Should have standard materials
        self.assertIn("BK7", materials)
        self.assertIn("F2", materials)
        self.assertIn("FUSEDSILICA", materials)

    def test_get_material(self):
        """Test getting material properties"""
        mat = self.db.get_material("BK7")

        self.assertIsNotNone(mat)
        self.assertEqual(mat.name, "BK7")
        self.assertEqual(mat.catalog, "Schott")
        self.assertAlmostEqual(mat.nd, 1.5168, places=4)
        self.assertAlmostEqual(mat.vd, 64.17, places=2)

    def test_sellmeier_coefficients(self):
        """Test that Sellmeier coefficients are present"""
        mat = self.db.get_material("BK7")

        # Should have Sellmeier coefficients
        self.assertGreater(mat.B1, 0)
        self.assertGreater(mat.C1, 0)

    def test_case_insensitive_lookup(self):
        """Test case-insensitive material lookup"""
        mat1 = self.db.get_material("BK7")
        mat2 = self.db.get_material("bk7")
        mat3 = self.db.get_material("Bk7")

        self.assertEqual(mat1.name, mat2.name)
        self.assertEqual(mat1.name, mat3.name)

    def test_list_by_catalog(self):
        """Test filtering materials by catalog"""
        schott = self.db.list_materials("Schott")
        ohara = self.db.list_materials("Ohara")
        hoya = self.db.list_materials("Hoya")

        self.assertIn("BK7", schott)
        self.assertIn("S-LAH79", ohara)
        self.assertIn("E-FD60", hoya)

    def test_temperature_coefficients(self):
        """Test that temperature coefficients exist"""
        mat = self.db.get_material("BK7")

        # Should have temperature coefficients
        self.assertIsNotNone(mat.D0)
        self.assertIsNotNone(mat.D1)

    def test_physical_properties(self):
        """Test physical property data"""
        mat = self.db.get_material("BK7")

        # Should have density
        self.assertGreater(mat.density, 0)

        # Should have thermal expansion
        self.assertGreater(mat.thermal_expansion, 0)

        # Should have resistance ratings
        self.assertIn(mat.climate_resistance, [0, 1, 2, 3, 4])
        self.assertIn(mat.acid_resistance, [0, 1, 2, 3, 4])


class TestAchromatDegenerateInputs(unittest.TestCase):
    """Same-glass achromats are unsolvable and must say so.

    The power split divides by (V1 - V2); with one glass twice that is a
    ZeroDivisionError, while the sibling designer in optical_system already
    guarded the case.
    """

    def setUp(self):
        self.analyzer = ChromaticAnalyzer()

    def test_same_glass_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.analyzer.design_achromatic_doublet(100.0, "BK7", "BK7")

    def test_same_glass_raises_for_each_catalog_pair(self):
        for glass in ("BK7", "F2", "N-BK7", "SF11"):
            with self.subTest(glass=glass):
                with self.assertRaises(ValueError):
                    self.analyzer.design_achromatic_doublet(100.0, glass, glass)

    def test_message_names_the_glasses_and_explains(self):
        with self.assertRaises(ValueError) as ctx:
            self.analyzer.design_achromatic_doublet(100.0, "BK7", "BK7")
        message = str(ctx.exception)
        self.assertIn("BK7", message)
        self.assertIn("Abbe", message)

    def test_different_glasses_still_design_normally(self):
        design = self.analyzer.design_achromatic_doublet(100.0, "BK7", "F2")
        self.assertGreater(design["crown_element"]["power"], 0)
        self.assertLess(design["flint_element"]["power"], 0)
        self.assertAlmostEqual(design["total_focal_length"], 100.0, places=6)

    def test_near_equal_abbe_numbers_are_not_rejected(self):
        """The 1e-12 guard must not fire on genuinely different glasses.

        N-BK7 and BK7 are the same catalog entry with the same V, so a pair
        with a small but non-zero spread is the real case to check.
        """
        abbe_bk7 = self.analyzer.calculate_abbe_number("BK7")
        abbe_sf11 = self.analyzer.calculate_abbe_number("SF11")
        self.assertNotAlmostEqual(abbe_bk7, abbe_sf11, places=3)
        design = self.analyzer.design_achromatic_doublet(100.0, "BK7", "SF11")
        self.assertIn("crown_element", design)

    def test_alias_glasses_with_identical_abbe_are_rejected(self):
        """BK7 and N-BK7 share an Abbe number, so they cannot be an achromat."""
        self.assertAlmostEqual(
            self.analyzer.calculate_abbe_number("BK7"),
            self.analyzer.calculate_abbe_number("N-BK7"),
            places=9,
        )
        with self.assertRaises(ValueError):
            self.analyzer.design_achromatic_doublet(100.0, "BK7", "N-BK7")

    def test_abbe_number_rejects_zero_dispersion(self):
        """V_d is undefined for a material with no F..C dispersion."""
        analyzer = self.analyzer
        original = analyzer.material_db.get_refractive_index

        # A material whose index does not vary with wavelength at all.
        analyzer.material_db.get_refractive_index = lambda material, wavelength: 1.5
        try:
            with self.assertRaises(ValueError):
                analyzer.calculate_abbe_number("FLAT")
        finally:
            analyzer.material_db.get_refractive_index = original


class TestLateralColorIsTheChiefRay(unittest.TestCase):
    """Lateral color is a chief-ray height, so it cannot scale with the stop.

    The reported value used to be the separation of two hexapolar bundle
    centroids: 0.0052 mm at 5 mm diameter, 0.0141 mm at 10 mm and 0.0536 mm
    at 25 mm for the same singlet. The chief ray through the pupil centre is
    0.002995 mm at every aperture.
    """

    BASE = {
        "radius1": 50.0,
        "radius2": -50.0,
        "thickness": 5.0,
        "material": "BK7",
    }
    WAVELENGTHS = [486.1, 587.6, 656.3]
    CHIEF_RAY_LATERAL_COLOR_MM = 0.002995446

    def setUp(self):
        self.analyzer = ChromaticAnalyzer()

    def _lateral_color(self, diameter):
        return self.analyzer.analyze_lens(
            dict(self.BASE, diameter=diameter),
            wavelengths=self.WAVELENGTHS,
            num_rays=37,
        ).lateral_color

    def test_lateral_color_does_not_depend_on_the_aperture(self):
        values = [self._lateral_color(diameter) for diameter in (5.0, 10.0, 25.0, 40.0)]

        self.assertLess(max(values) - min(values), 1e-9)
        self.assertAlmostEqual(values[0], self.CHIEF_RAY_LATERAL_COLOR_MM, places=9)

    def test_lateral_color_matches_a_hand_traced_chief_ray(self):
        from openlens.analysis.spot_diagram import SpotDiagram
        from openlens.constants import NM_TO_MM
        from openlens.lens import Lens
        from openlens.material_database import MaterialDatabase
        from openlens.optical_system import OpticalSystem
        from openlens.ray_tracer import Ray3D
        from openlens.vector3 import vec3

        database = MaterialDatabase()
        diameter = 25.0

        def build_system(wavelength_nm):
            lens = Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=diameter,
                refractive_index=database.get_refractive_index("BK7", wavelength_nm, 20.0),
                material="BK7",
                wavelength=wavelength_nm,
            )
            system = OpticalSystem("hand trace")
            system.add_lens(lens)
            return system

        # The analysis evaluates both wavelengths at the d-line image plane.
        reference = build_system(587.6)
        plane = SpotDiagram(reference).trace_spot(wavelength_nm=587.6)["image_plane_x"]

        def chief_height(wavelength_nm):
            system = build_system(wavelength_nm)
            direction = vec3(1.0, math.tan(math.radians(5.0)), 0.0).normalize()
            first_lens_x = system.elements[0].position
            start_x = first_lens_x - 50.0
            t = (first_lens_x - start_x) / direction.x
            origin = vec3(first_lens_x, 0.0, 0.0) - direction * t

            ray = Ray3D(origin, direction, wavelength=wavelength_nm * NM_TO_MM)
            SpotDiagram(system).tracer.trace_ray(ray)
            t = (plane - ray.origin.x) / ray.direction.x
            return ray.origin.y + t * ray.direction.y

        expected = abs(chief_height(self.WAVELENGTHS[0]) - chief_height(self.WAVELENGTHS[-1]))
        reported = self._lateral_color(diameter)

        self.assertAlmostEqual(reported, expected, places=9)


class TestWavelengthOrderIndependence(unittest.TestCase):
    """#644: the caller may list the wavelengths in any order."""

    PARAMS = {
        "radius1": 50.0,
        "radius2": -50.0,
        "thickness": 5.0,
        "diameter": 25.0,
        "material": "BK7",
    }
    WAVELENGTHS = [486.1, 587.6, 656.3]

    def setUp(self):
        self.analyzer = ChromaticAnalyzer()

    def test_permuted_wavelengths_give_the_same_scalar_metrics(self):
        import itertools

        reference = None
        for permutation in itertools.permutations(self.WAVELENGTHS):
            result = self.analyzer.analyze_lens(
                self.PARAMS, wavelengths=list(permutation), num_rays=11
            )
            if reference is None:
                reference = result
                continue
            self.assertAlmostEqual(
                result.axial_chromatic_aberration,
                reference.axial_chromatic_aberration,
                places=9,
                msg=f"axial colour changed for {permutation}",
            )
            self.assertAlmostEqual(
                result.focal_shift,
                reference.focal_shift,
                places=9,
                msg=f"focal shift changed for {permutation}",
            )
            self.assertAlmostEqual(
                result.lateral_color,
                reference.lateral_color,
                places=9,
                msg=f"lateral colour changed for {permutation}",
            )

    def test_axial_colour_agrees_with_the_focal_shift(self):
        result = self.analyzer.analyze_lens(
            self.PARAMS, wavelengths=[587.6, 486.1, 656.3], num_rays=11
        )

        self.assertAlmostEqual(result.axial_chromatic_aberration, result.focal_shift, places=12)
        self.assertGreater(result.axial_chromatic_aberration, 0.0)


class TestErrorTypes(unittest.TestCase):
    """#645: edge inputs must raise ValueError, not ZeroDivisionError."""

    PARAMS = {
        "radius1": 50.0,
        "radius2": -50.0,
        "thickness": 5.0,
        "diameter": 25.0,
        "material": "BK7",
    }

    def setUp(self):
        self.analyzer = ChromaticAnalyzer()

    def test_partial_dispersion_of_a_flat_material_raises_value_error(self):
        original = self.analyzer.material_db.get_refractive_index
        self.analyzer.material_db.get_refractive_index = lambda material, wavelength: 1.5
        try:
            with self.assertRaises(ValueError) as ctx:
                self.analyzer.calculate_partial_dispersion("FLAT")
        finally:
            self.analyzer.material_db.get_refractive_index = original
        self.assertIn("partial dispersion", str(ctx.exception))

    def test_partial_dispersion_of_an_unknown_material_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.analyzer.calculate_partial_dispersion("NOT_A_GLASS")

    def test_plot_chromatic_focal_shift_requires_at_least_two_points(self):
        for num_points in (1, 0, -1):
            with self.subTest(num_points=num_points):
                with self.assertRaises(ValueError) as ctx:
                    self.analyzer.plot_chromatic_focal_shift(self.PARAMS, num_points=num_points)
                self.assertIn("num_points", str(ctx.exception))

    def test_plot_chromatic_focal_shift_still_accepts_two_points(self):
        result = self.analyzer.plot_chromatic_focal_shift(self.PARAMS, num_points=2)

        self.assertEqual(len(result["wavelengths"]), 2)
        self.assertEqual(len(result["focal_lengths"]), 2)


if __name__ == "__main__":
    unittest.main()
