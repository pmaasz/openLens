#!/usr/bin/env python3
import unittest
import sys
import os
import math

# Use project root as part of sys.path to allow imports from src
sys.path.insert(0, os.getcwd())

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.analysis.ghost import GhostAnalyzer, GhostPath

class TestAssemblyGhostAnalysis(unittest.TestCase):
    def setUp(self):
        # Create a doublet
        self.system = OpticalSystem(name="Ghost Doublet")
        
        # Crown
        self.l1 = Lens(
            name="Crown",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=40.0,
            material="BK7"
        )
        # Flint
        self.l2 = Lens(
            name="Flint",
            radius_of_curvature_1=-50.0,
            radius_of_curvature_2=-150.0,
            thickness=3.0,
            diameter=40.0,
            material="SF11"
        )
        
        self.system.add_lens(self.l1)
        # Small gap to ensure 4 distinct surfaces
        self.system.add_lens(self.l2, air_gap_before=0.1)
        
        # Surface indices:
        # 0: L1 Front
        # 1: L1 Back
        # 2: L2 Front
        # 3: L2 Back

    def test_ghost_trace_multi_element(self):
        """Test tracing ghosts through a multi-element system."""
        analyzer = GhostAnalyzer(self.system)
        
        # Trace ghosts
        ghosts = analyzer.trace_ghosts(num_rays=1)
        
        # We expect several ghost paths in a 4-surface system
        # (3,2), (3,1), (3,0), (2,1), (2,0), (1,0)
        self.assertGreater(len(ghosts), 0)
        
        print(f"Found {len(ghosts)} ghost paths.")
        for g in ghosts:
            print(f"Path ({g.reflection_1_index}, {g.reflection_2_index}) - Intensity: {g.intensity:.2e}")
            self.assertGreater(len(g.rays), 0)
            
        # Verify a specific path (e.g., reflection between lenses: 2 to 1)
        found_inter_element = any(g.reflection_1_index == 2 and g.reflection_2_index == 1 for g in ghosts)
        # Actually, in a 4-surface system, index 2 is L2 front, index 1 is L1 back.
        # This is a common ghost path.
        # Note: Depending on coatings and intensity, it might be very weak, but here it should be traced.
        self.assertTrue(found_inter_element, "Did not find inter-element ghost path (L2 Front -> L1 Back)")

if __name__ == '__main__':
    unittest.main()
