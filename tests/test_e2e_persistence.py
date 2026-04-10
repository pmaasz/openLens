#!/usr/bin/env python3
"""
End-to-end verification for Design-Save-Reload-Simulate cycle.
Verifies that complex nested assemblies are correctly persisted in the database.
"""

import sys
import os
import unittest
import tempfile
import math
import json
import sqlite3

# Adjust path to find src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from database import DatabaseManager
from optical_system import OpticalSystem, create_doublet
from lens import Lens

class TestEndToEndPersistence(unittest.TestCase):

    def setUp(self):
        # Create a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        self.db_manager = DatabaseManager(self.db_path)

    def tearDown(self):
        # Remove temporary database
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_design_save_reload_simulate(self):
        """Verify full lifecycle for a doublet assembly."""
        # 1. Design: Create a doublet
        system = create_doublet(focal_length=100.0, diameter=40.0)
        system.name = "E2E Doublet"
        system.id = "e2e_doublet_123"
        
        # Calculate initial focal length for comparison later
        initial_fl = system.get_system_focal_length()
        self.assertIsNotNone(initial_fl)
        
        # 2. Save: Use DatabaseManager to persist the system
        # OpticalSystem.to_dict() is used for serialization
        system_dict = system.to_dict()
        self.db_manager.save_assembly(system_dict)
        
        # 3. Reload: Load all items from database and find our assembly
        loaded_items = self.db_manager.load_all()
        
        # Filter for the assembly
        assemblies = [item for item in loaded_items if item.get('id') == "e2e_doublet_123" and item.get('type') == 'OpticalSystem']
        self.assertEqual(len(assemblies), 1, "Assembly not found in database")
        loaded_dict = assemblies[0]
        
        # Reconstruct OpticalSystem from dict
        loaded_system = OpticalSystem.from_dict(loaded_dict)
        
        # 4. Verify properties
        self.assertEqual(loaded_system.name, "E2E Doublet")
        self.assertEqual(len(loaded_system.elements), 2)
        self.assertEqual(len(loaded_system.air_gaps), 1)
        
        # 5. Simulate: Verify calculations match
        loaded_fl = loaded_system.get_system_focal_length()
        self.assertAlmostEqual(loaded_fl, initial_fl, places=5)
        
        # Verify positions
        for i in range(len(system.elements)):
            self.assertAlmostEqual(loaded_system.elements[i].position, system.elements[i].position, places=5)

    def test_nested_lenses_sharing(self):
        """Verify that when multiple assemblies share a lens, it's correctly handled."""
        shared_lens = Lens(name="SharedLens", radius_of_curvature_1=100, radius_of_curvature_2=-100, thickness=5, diameter=30)
        shared_lens.id = "shared_lens_id"
        
        sys1 = OpticalSystem(name="Sys 1")
        sys1.id = "sys1_id"
        sys1.add_lens(shared_lens)
        
        sys2 = OpticalSystem(name="Sys 2")
        sys2.id = "sys2_id"
        sys2.add_lens(shared_lens, air_gap_before=10.0)
        
        # Save both
        self.db_manager.save_assembly(sys1.to_dict())
        self.db_manager.save_assembly(sys2.to_dict())
        
        # Reload
        loaded_items = self.db_manager.load_all()
        
        # Find Sys 1 and Sys 2
        l_sys1 = [i for i in loaded_items if i.get('id') == "sys1_id"][0]
        l_sys2 = [i for i in loaded_items if i.get('id') == "sys2_id"][0]
        
        # Reconstruct
        r_sys1 = OpticalSystem.from_dict(l_sys1)
        r_sys2 = OpticalSystem.from_dict(l_sys2)
        
        # Verify lenses have same properties
        self.assertEqual(r_sys1.elements[0].lens.name, "SharedLens")
        self.assertEqual(r_sys2.elements[0].lens.name, "SharedLens")
        self.assertEqual(r_sys1.elements[0].lens.id, r_sys2.elements[0].lens.id)
        
        # Note: In real application, we'd use a shared lens pool in memory to ensure identity.
        # But for E2E verification of data integrity, ID matching is enough.

if __name__ == '__main__':
    unittest.main()
