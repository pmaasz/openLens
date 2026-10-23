import unittest
import os
import sys

# Add the repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openlens.lens import Lens
from openlens.stl_export import export_lens_stl, STLExporter


class TestSTLExport(unittest.TestCase):
    def setUp(self):
        self.filename = "test_lens_output.stl"
        self.lens = Lens(
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=10.0,
            diameter=25.0,
            refractive_index=1.5,
        )

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_export_creates_file(self):
        """Test that export creates a valid file"""
        count = export_lens_stl(self.lens, self.filename, resolution=10)

        self.assertTrue(os.path.exists(self.filename))
        self.assertGreater(count, 0)

        # Check file size
        # Header (80) + Count (4) + Triangles (50 * count)
        expected_size = 84 + 50 * count
        self.assertEqual(os.path.getsize(self.filename), expected_size)

    def test_export_flat_surfaces(self):
        """Test export with flat surfaces"""
        flat_lens = Lens(
            radius_of_curvature_1=1e9,  # Flat
            radius_of_curvature_2=1e9,  # Flat
            thickness=5.0,
            diameter=20.0,
            refractive_index=1.5,
        )
        count = export_lens_stl(flat_lens, self.filename, resolution=10)
        self.assertGreater(count, 0)

    def test_geometry_consistency(self):
        """Test that generated triangles are valid (normals not zero)"""
        exporter = STLExporter()
        exporter.export_lens_to_stl(50, -50, 10, 25, self.filename, resolution=5)

        # Manually check a few triangles
        for tri in exporter.triangles:
            p1, p2, p3 = tri
            # Check for degenerate triangles
            self.assertNotEqual(p1, p2)
            self.assertNotEqual(p1, p3)
            self.assertNotEqual(p2, p3)


if __name__ == "__main__":
    unittest.main()


class TestSTLHelperContracts(unittest.TestCase):
    """#663: the helpers do what their docstrings say."""

    def setUp(self):
        self.exporter = STLExporter()

    def test_a_flat_surface_profile_is_none(self):
        for radius in (0.0, float("inf"), -float("inf")):
            with self.subTest(radius=radius):
                self.assertIsNone(
                    self.exporter.calculate_surface_profile(
                        radius, 25.0, is_front=True, resolution=5
                    )
                )

    def test_a_curved_surface_profile_is_still_returned(self):
        profile = self.exporter.calculate_surface_profile(50.0, 25.0, resolution=5)

        self.assertIsNotNone(profile)
        self.assertEqual(len(profile), 6)

    def test_a_closed_edge_list_wraps_the_last_segment(self):
        triangles = self.exporter.generate_edge_triangles(
            10.0, [0.0, 1.0, 2.0, 3.0], [5.0, 6.0, 7.0, 8.0], num_segments=4
        )

        self.assertEqual(len(triangles), 8)
        # Last segment: p1 = index 3, p2 wraps to index 0.
        self.assertEqual(triangles[-2][0][2], 3.0)
        self.assertEqual(triangles[-2][1][2], 0.0)
        self.assertEqual(triangles[-1][1][2], 5.0)

    def test_an_open_edge_list_uses_the_final_value(self):
        triangles = self.exporter.generate_edge_triangles(
            10.0,
            [0.0, 1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0, 9.0],
            num_segments=4,
        )

        self.assertEqual(len(triangles), 8)
        # Last segment: p1 = index 3, p2 = index 4 (no wrap).
        self.assertEqual(triangles[-2][0][2], 3.0)
        self.assertEqual(triangles[-2][1][2], 4.0)
        self.assertEqual(triangles[-1][1][2], 9.0)

    def test_an_edge_list_of_the_wrong_length_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must have 4 or 5 values"):
            self.exporter.generate_edge_triangles(10.0, [0.0, 1.0], [5.0, 6.0], num_segments=4)
