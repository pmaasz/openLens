import unittest
from src.optical_system import OpticalSystem, Lens
from src.analysis.ghost import GhostAnalyzer, GhostPath
from src.vector3 import vec3
from src.constants import WAVELENGTH_GREEN, NM_TO_MM

class TestGhostAnalysis(unittest.TestCase):
    def setUp(self):
        # Create a simple single lens system
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=10.0,
            diameter=25.0,
            material="BK7"
        )
        self.system = OpticalSystem()
        self.system.add_lens(self.lens)
        
        self.analyzer = GhostAnalyzer(self.system)

    def test_surface_list_building(self):
        """Test that surfaces are correctly enumerated."""
        surfaces = self.analyzer.surfaces
        self.assertEqual(len(surfaces), 2)
        self.assertEqual(surfaces[0]['type'], 'front')
        self.assertEqual(surfaces[1]['type'], 'back')
        self.assertEqual(surfaces[0]['id'], 0)
        self.assertEqual(surfaces[1]['id'], 1)

    def test_ghost_path_detection(self):
        """Test detection of internal reflection ghost (Back->Front)."""
        # We expect a ghost from i=1 (Back) then j=0 (Front)
        ghosts = self.analyzer.trace_ghosts(num_rays=3)
        
        # Should find at least one ghost path (1 -> 0)
        found_internal_ghost = False
        for ghost in ghosts:
            if ghost.reflection_1_index == 1 and ghost.reflection_2_index == 0:
                found_internal_ghost = True
                self.assertTrue(len(ghost.rays) > 0)
                # Check ray direction at end (should be propagating forward +X)
                final_ray = ghost.rays[0]
                self.assertTrue(final_ray.direction.x > 0)
                self.assertTrue(final_ray.terminated or len(final_ray.path) > 3) 
                
        self.assertTrue(found_internal_ghost, "Did not find expected internal ghost (Back->Front reflection)")

    def test_ghost_path_validity(self):
        """Trace a specific ghost and verify ray path length."""
        # Trace specifically 1->0
        ghost = self.analyzer._trace_ghost_path(1, 0, num_rays=1, wavelength=WAVELENGTH_GREEN * NM_TO_MM)
        self.assertIsNotNone(ghost)
        ray = ghost.rays[0]
        
        # Path: 
        # 1. Start (Origin)
        # 2. Front (Refract)
        # 3. Back (Reflect)
        # 4. Front (Reflect)
        # 5. Back (Refract)
        # 6. End (Propagated)
        # Total points: at least 5 intersection points + origin = 6 points?
        # Let's count interactions.
        # trace_surface adds point on intersection.
        # Ray initialized with origin (1 point).
        # Refract Front (1 point)
        # Reflect Back (1 point)
        # Reflect Front (1 point)
        # Refract Back (1 point)
        # Propagate? trace_ghost_path doesn't explicitly propagate at end, just returns ray.
        # Wait, step 5 calls _trace_sequence, which calls _interact.
        # _interact calls trace_surface.
        # trace_surface adds point.
        # So we expect Origin + 4 points = 5 points.
        
        self.assertGreaterEqual(len(ray.path), 5)
        
    def test_no_ghosts_for_empty_system(self):
        empty_sys = OpticalSystem()
        analyzer = GhostAnalyzer(empty_sys)
        ghosts = analyzer.trace_ghosts()
        self.assertEqual(len(ghosts), 0)

if __name__ == '__main__':
    unittest.main()
