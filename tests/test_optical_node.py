
import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath('src'))

from optical_node import OpticalNode, OpticalElement, OpticalAssembly
from optical_system import OpticalSystem, LensElement
from lens import Lens
from vector3 import vec3

class TestOpticalNode(unittest.TestCase):
    def test_node_hierarchy(self):
        root = OpticalNode("Root")
        child1 = OpticalNode("Child1")
        child2 = OpticalNode("Child2")
        
        root.add_child(child1)
        child1.add_child(child2)
        
        self.assertEqual(child1.parent, root)
        self.assertEqual(child2.parent, child1)
        
        # Test positions
        root.position = vec3(0,0,0)
        child1.position = vec3(10,0,0)
        child2.position = vec3(5,0,0)
        
        # 10 + 5 = 15
        pos = child2.get_global_position()
        self.assertAlmostEqual(pos.x, 15.0)
        self.assertAlmostEqual(pos.y, 0.0)
        self.assertAlmostEqual(pos.z, 0.0)

    def test_optical_system_assembly(self):
        sys_opt = OpticalSystem("Assembly System")
        
        # Create an assembly (Doublet)
        doublet = OpticalAssembly("Doublet")
        l1 = Lens(name="L1", thickness=5.0)
        l2 = Lens(name="L2", thickness=3.0)
        
        e1 = OpticalElement(l1, "E1")
        e2 = OpticalElement(l2, "E2")
        
        # L1 at 0 relative to doublet
        e1.position = vec3(0,0,0)
        # L2 at 5 (cemented) relative to doublet
        e2.position = vec3(5,0,0)
        
        doublet.add_child(e1)
        doublet.add_child(e2)
        
        # Add assembly to system at position 20
        sys_opt.add_assembly(doublet, position=20.0)
        
        # Verify flat elements list
        self.assertEqual(len(sys_opt.elements), 2)
        
        # E1 global pos: 20 + 0 = 20
        self.assertAlmostEqual(sys_opt.elements[0].position, 20.0)
        self.assertEqual(sys_opt.elements[0].lens.name, "L1")
        
        # E2 global pos: 20 + 5 = 25
        self.assertAlmostEqual(sys_opt.elements[1].position, 25.0)
        
        # Verify air gaps
        # E1 ends at 20+5=25. E2 starts at 25. Gap should be 0.
        self.assertEqual(len(sys_opt.air_gaps), 1)
        self.assertAlmostEqual(sys_opt.air_gaps[0].thickness, 0.0)
        
    def test_mixed_hierarchy(self):
        sys_opt = OpticalSystem("Mixed System")
        
        # 1. Add single lens
        l1 = Lens("L1", thickness=5.0)
        sys_opt.add_lens(l1, air_gap_before=0.0) # Pos 0
        
        # 2. Add assembly
        doublet = OpticalAssembly("Doublet")
        l2 = Lens("L2", thickness=4.0)
        e2 = OpticalElement(l2, "E2")
        e2.position = vec3(0,0,0)
        doublet.add_child(e2)
        
        # Add assembly at pos 10
        # Wait, usually we add assembly relative to previous?
        # OpticalSystem.add_assembly takes absolute position (relative to root)
        # L1 ends at 5. Gap 5. Assembly starts at 10.
        sys_opt.add_assembly(doublet, position=10.0)
        
        # 3. Add another lens via add_lens
        # add_lens calculates position based on last element (L2 inside doublet)
        # L2 is at 10. Thick 4. Ends at 14.
        # Add L3 with gap 6. Pos should be 20.
        l3 = Lens("L3", thickness=2.0)
        sys_opt.add_lens(l3, air_gap_before=6.0)
        
        self.assertEqual(len(sys_opt.elements), 3)
        self.assertAlmostEqual(sys_opt.elements[0].position, 0.0)
        self.assertAlmostEqual(sys_opt.elements[1].position, 10.0)
        self.assertAlmostEqual(sys_opt.elements[2].position, 20.0)
        
        # Check gaps
        # G1: 0->5 to 10. Gap 5.
        # G2: 10->14 to 20. Gap 6.
        self.assertEqual(len(sys_opt.air_gaps), 2)
        self.assertAlmostEqual(sys_opt.air_gaps[0].thickness, 5.0)
        self.assertAlmostEqual(sys_opt.air_gaps[1].thickness, 6.0)

if __name__ == '__main__':
    unittest.main()
