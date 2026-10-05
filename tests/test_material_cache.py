import unittest
import math

from src.material_database import MaterialDatabase, MaterialProperties


class TestMaterialCache(unittest.TestCase):

    def setUp(self):
        self.db = MaterialDatabase()

        # Add a custom test material
        # Use small non-zero C1 so the term is included
        self.test_mat = MaterialProperties(
            name="TEST_GLASS", catalog="TEST", nd=1.5, vd=60.0, B1=1.0, C1=0.0001
        )
        self.db.add_material(self.test_mat)

    def test_cache_hits(self):
        """Repeated calls are served from the per-instance cache"""
        n1 = self.db.get_refractive_index("TEST_GLASS", 550.0)
        self.assertEqual(len(self.db._index_cache), 1)

        n2 = self.db.get_refractive_index("TEST_GLASS", 550.0)

        self.assertEqual(n1, n2)
        # Still one entry: the second call added nothing.
        self.assertEqual(len(self.db._index_cache), 1)

    def test_cache_invalidation_on_update(self):
        """Test that updating a material clears the cache"""

        # Get initial index
        # With B1=1, C1=0.0001, at 550nm (0.55um)
        # lambda_sq = 0.3025
        # n^2 = 1 + 1.0 * 0.3025 / (0.3025 - 0.0001) ≈ 1 + 1 = 2
        # n ≈ 1.414
        n1 = self.db.get_refractive_index("TEST_GLASS", 550.0)

        # Modify material property
        new_mat = MaterialProperties(
            name="TEST_GLASS", catalog="TEST", nd=1.732, vd=60.0, B1=2.0, C1=0.0001
        )
        # New n^2 ≈ 1 + 2 = 3 -> n ≈ 1.732

        # Add material (should clear cache)
        self.db.add_material(new_mat)

        # Get new index
        n2 = self.db.get_refractive_index("TEST_GLASS", 550.0)

        self.assertNotAlmostEqual(n1, n2)
        self.assertGreater(n2, n1)

    def test_cache_clear_method(self):
        """Test explicit cache clearing"""
        self.db.get_refractive_index("TEST_GLASS", 550.0)
        self.assertGreater(len(self.db._index_cache), 0)

        self.db.clear_cache()

        self.assertEqual(len(self.db._index_cache), 0, "Cache size should be 0 after clear")


if __name__ == "__main__":
    unittest.main()
