#!/usr/bin/env python3
"""
One canonical preset library, and no lost catalogue content.

src/preset_library.py and src/preset_lenses.py both exported
get_preset_library() with the same name and the same intent but opposite
shapes:

    preset_library            preset_lenses
    PresetLibrary             PresetLensLibrary
    singleton                 factory returning a fresh instance
    search_presets -> List    search_presets -> Dict[str, Dict]

import_custom_preset on the factory version was a no-op - the imported preset
was discarded on the next call - and the two test suites encoded
contradictory contracts. Neither module was wired into the GUI.

src/preset_library.py is the survivor (typed LensPreset, singleton,
category listing, and get_lens_copy's to_dict/from_dict round-trip). This
suite covers the survivor, the catalogue migrated over from the retired
module, and the absence of the duplicate.

It replaces tests/test_preset_lenses.py, which tested the deleted module's
dict-based API.
"""

import math
import unittest

from src.constants import LARGE_NUMBER
from src.lens import Lens, _is_flat
from src.preset_library import FLAT_RADIUS
from src.validation import ValidationError
from src.preset_library import (
    LensPreset,
    PresetLibrary,
    _CATALOG_PRESETS,
    get_preset_library,
)

# Presets that existed only in the retired src/preset_lenses.py.
MIGRATED = (
    "Symmetric Biconvex",
    "Kellner Eyepiece",
    "4x Microscope Objective",
    "Telescope Objective",
    "Beam Expander Element",
    "Edmund #45-166 (25mm PCX)",
    "Edmund #45-168 (25mm PCX)",
    "Thorlabs LA1509 (25mm PCX)",
)


class TestRetiredModuleIsGone(unittest.TestCase):
    def test_preset_lenses_no_longer_imports(self):
        """The duplicate public name must not come back."""
        with self.assertRaises(ImportError):
            import src.preset_lenses  # noqa: F401

    def test_only_one_module_defines_get_preset_library(self):
        import pkgutil

        import src

        found = []
        for info in pkgutil.iter_modules(src.__path__):
            if not info.name.startswith("preset"):
                continue
            module = __import__("src.%s" % info.name, fromlist=["*"])
            if hasattr(module, "get_preset_library"):
                found.append(info.name)
        self.assertEqual(found, ["preset_library"])


class TestSingletonContract(unittest.TestCase):
    """test_preset_performance_functional.py asserted the singleton; the
    retired module contradicted it with a factory."""

    def test_returns_the_same_instance(self):
        self.assertIs(get_preset_library(), get_preset_library())

    def test_instance_is_a_preset_library(self):
        self.assertIsInstance(get_preset_library(), PresetLibrary)

    def test_search_returns_preset_objects(self):
        results = get_preset_library().search_presets("biconvex")
        self.assertTrue(results)
        for preset in results:
            self.assertIsInstance(preset, LensPreset)

    def test_search_matches_name_and_description(self):
        library = get_preset_library()
        self.assertTrue(library.search_presets("kellner"))
        self.assertTrue(library.search_presets("field of view"))


class TestMigratedContentSurvived(unittest.TestCase):
    def setUp(self):
        self.library = PresetLibrary()

    def test_every_migrated_preset_is_present(self):
        for name in MIGRATED:
            with self.subTest(preset=name):
                self.assertIsNotNone(self.library.get_preset(name))

    def test_catalogue_table_matches_what_was_migrated(self):
        self.assertEqual(len(_CATALOG_PRESETS), len(MIGRATED))

    def test_industry_standard_entries_keep_vendor_and_part_number(self):
        preset = self.library.get_preset("Edmund #45-166 (25mm PCX)")
        self.assertEqual(preset.manufacturer, "Edmund Optics")
        self.assertEqual(preset.part_number, "45-166")

    def test_applications_became_typical_use(self):
        preset = self.library.get_preset("Kellner Eyepiece")
        self.assertIn("Telescopes", preset.typical_use)

    def test_optical_data_is_unchanged(self):
        """Verbatim from the retired module."""
        expected = {
            "Kellner Eyepiece": (15.0, -30.0, 4.0, 20.0),
            "Telescope Objective": (200.0, -250.0, 10.0, 50.0),
            "Beam Expander Element": (-20.0, 40.0, 4.0, 25.4),
            "Edmund #45-166 (25mm PCX)": (25.8, None, 4.8, 25.0),
        }
        for name, (r1, r2, thickness, diameter) in expected.items():
            with self.subTest(preset=name):
                lens = self.library.get_preset(name).lens
                self.assertEqual(lens.radius_of_curvature_1, r1)
                self.assertEqual(lens.thickness, thickness)
                self.assertEqual(lens.diameter, diameter)
                if r2 is None:
                    self.assertTrue(_is_flat(lens.radius_of_curvature_2))
                else:
                    self.assertEqual(lens.radius_of_curvature_2, r2)

    def test_every_preset_is_typed(self):
        for preset in self.library.list_presets():
            self.assertIsInstance(preset, LensPreset)
            self.assertIsInstance(preset.lens, Lens)
            self.assertTrue(preset.category)
            self.assertTrue(preset.description)


class TestPhysicalValidity(unittest.TestCase):
    """Carried over from the retired suite's sweep."""

    def setUp(self):
        self.presets = PresetLibrary().list_presets()

    def test_sweep_finds_presets(self):
        self.assertGreater(len(self.presets), 10)

    def test_thickness_is_positive(self):
        for preset in self.presets:
            with self.subTest(preset=preset.name):
                self.assertGreater(preset.lens.thickness, 0)

    def test_diameter_is_positive(self):
        for preset in self.presets:
            with self.subTest(preset=preset.name):
                self.assertGreater(preset.lens.diameter, 0)

    def test_focal_length_is_never_zero(self):
        for preset in self.presets:
            with self.subTest(preset=preset.name):
                focal = preset.lens.calculate_focal_length()
                if focal is not None:
                    self.assertNotEqual(focal, 0.0)

    def test_radius_one_is_never_zero(self):
        for preset in self.presets:
            with self.subTest(preset=preset.name):
                self.assertNotEqual(preset.lens.radius_of_curvature_1, 0.0)

    def test_lens_copy_is_a_distinct_object(self):
        library = PresetLibrary()
        first = library.get_lens_copy("50mm Biconvex")
        second = library.get_lens_copy("50mm Biconvex")
        self.assertIsNot(first, second)
        self.assertNotEqual(first.id, second.id)

    def test_lens_copy_round_trips_through_to_dict(self):
        """The survivor's get_lens_copy uses to_dict/from_dict."""
        library = PresetLibrary()
        for preset in library.list_presets():
            with self.subTest(preset=preset.name):
                copy = library.get_lens_copy(preset.name)
                self.assertEqual(copy.radius_of_curvature_1, preset.lens.radius_of_curvature_1)
                self.assertEqual(copy.thickness, preset.lens.thickness)
                self.assertEqual(copy.material, preset.lens.material)

    def test_lens_copy_of_unknown_preset_is_none(self):
        self.assertIsNone(PresetLibrary().get_lens_copy("no such preset"))


class TestFlatSurfaceConvention(unittest.TestCase):
    """The preset used 1e10, which _is_flat does not recognise as flat."""

    def setUp(self):
        self.presets = PresetLibrary().list_presets()
        self.flat = [p for p in self.presets if _is_flat(p.lens.radius_of_curvature_2)]

    def test_is_flat_uses_a_strict_inequality(self):
        """The reason 1e10 was wrong: |r| > LARGE_NUMBER, not >=."""
        self.assertFalse(_is_flat(LARGE_NUMBER))
        self.assertTrue(_is_flat(LARGE_NUMBER * 2))

    def test_flat_presets_exist_and_are_recognised(self):
        names = [p.name for p in self.flat]
        self.assertIn("100mm Plano-Convex", names)
        self.assertIn("Edmund #45-166 (25mm PCX)", names)

    def test_every_flat_preset_uses_the_named_constant(self):
        for preset in self.flat:
            with self.subTest(preset=preset.name):
                self.assertEqual(preset.lens.radius_of_curvature_2, FLAT_RADIUS)

    def test_no_bare_large_literal_remains(self):
        import inspect

        import src.preset_library as module

        self.assertNotIn("radius_of_curvature_2=1e10", inspect.getsource(module))

    def test_validate_radius_cannot_express_flat(self):
        """Documents a real inconsistency rather than papering over it.

        validate_radius caps |r| at 10000 mm and rejects non-finite values, so
        no flat radius satisfies it. A flat radius is therefore internal-only
        and must not be round-tripped through that validator.
        """
        from src.validation import MAX_RADIUS_OF_CURVATURE, validate_radius

        for candidate in (FLAT_RADIUS, LARGE_NUMBER, LARGE_NUMBER * 2):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValidationError):
                    validate_radius(candidate)
        self.assertLess(MAX_RADIUS_OF_CURVATURE, LARGE_NUMBER)


class TestCategoriesAreCoherent(unittest.TestCase):
    def test_no_near_duplicate_category_names(self):
        """Migration must not split one subject across two labels."""
        categories = PresetLibrary().list_categories()
        for a in categories:
            for b in categories:
                if a is b or a == b:
                    continue
                singular = a[:-1] if a.endswith("s") else a
                other = b[:-1] if b.endswith("s") else b
                with self.subTest(pair=(a, b)):
                    self.assertNotEqual(
                        singular.lower(),
                        other.lower(),
                        "%r and %r are the same category" % (a, b),
                    )

    def test_every_category_has_at_least_one_preset(self):
        library = PresetLibrary()
        for category in library.list_categories():
            with self.subTest(category=category):
                self.assertTrue(library.list_presets(category=category))

    def test_unknown_category_returns_empty(self):
        self.assertEqual(PresetLibrary().list_presets(category="nope"), [])


if __name__ == "__main__":
    unittest.main()
