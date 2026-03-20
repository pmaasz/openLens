import unittest
import math
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from material_database import MaterialDatabase, MaterialProperties

class TestMaterialCache(unittest.TestCase):
    
    def setUp(self):
        self.db = MaterialDatabase()
        
        # Add a custom test material
        # Use small non-zero C1 so the term is included
        self.test_mat = MaterialProperties(
            name="TEST_GLASS",
            catalog="TEST",
            nd=1.5,
            vd=60.0,
            B1=1.0, 
            C1=0.0001
        )
        self.db.add_material(self.test_mat)

    def test_cache_hits(self):
        """Test that repeated calls hit the cache"""
        
        # First call - should calculate
        n1 = self.db.get_refractive_index("TEST_GLASS", 550.0)
        
        # Check cache info
        info1 = self.db.get_refractive_index.cache_info()
        # hits might be > 0 if used elsewhere, but hits should increase
        
        # Second call - should be cached
        n2 = self.db.get_refractive_index("TEST_GLASS", 550.0)
        
        info2 = self.db.get_refractive_index.cache_info()
        
        self.assertEqual(n1, n2)
        self.assertGreater(info2.hits, info1.hits, "Cache hits should increase on second call")

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
            name="TEST_GLASS",
            catalog="TEST",
            nd=1.732,
            vd=60.0,
            B1=2.0,
            C1=0.0001
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
        info1 = self.db.get_refractive_index.cache_info()
        
        self.db.clear_cache()
        info2 = self.db.get_refractive_index.cache_info()
        
        self.assertEqual(info2.currsize, 0, "Cache size should be 0 after clear")

if __name__ == '__main__':
    unittest.main()
