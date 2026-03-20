
import unittest
import math
import sys
import os

# Add src to path
sys.path.append(os.path.abspath('src'))

from optical_node import OpticalNode
from vector3 import vec3

class TestOpticalNodeRotation(unittest.TestCase):
    def test_rotation_transform(self):
        root = OpticalNode("Root")
        child = OpticalNode("Child")
        root.add_child(child)
        
        # Rotate root 90 degrees around Z
        root.rotation = vec3(0, 0, 90)
        
        # Place child at (10, 0, 0) relative to root
        child.position = vec3(10, 0, 0)
        
        # Global position should be (0, 10, 0) because X axis rotated to Y
        pos = child.get_global_position()
        self.assertAlmostEqual(pos.x, 0.0)
        self.assertAlmostEqual(pos.y, 10.0)
        self.assertAlmostEqual(pos.z, 0.0)
        
    def test_nested_rotation(self):
        root = OpticalNode("Root")
        arm = OpticalNode("Arm")
        hand = OpticalNode("Hand")
        
        root.add_child(arm)
        arm.add_child(hand)
        
        # Root: at origin
        # Arm: rotated 90 Z, pos (0,0,0) -> Local X points along Global Y
        arm.rotation = vec3(0, 0, 90)
        
        # Hand: at (10, 0, 0) relative to Arm -> Global (0, 10, 0)
        hand.position = vec3(10, 0, 0)
        
        pos = hand.get_global_position()
        self.assertAlmostEqual(pos.x, 0.0)
        self.assertAlmostEqual(pos.y, 10.0, places=5)
        
        # Now rotate Hand -90 Z relative to Arm
        hand.rotation = vec3(0, 0, -90)
        
        # Add finger
        finger = OpticalNode("Finger")
        hand.add_child(finger)
        finger.position = vec3(5, 0, 0) # 5 along hand's X
        
        # Hand global rotation should be 0 (90 + -90)
        # Finger global position should be Hand Global + (5,0,0)
        # = (0, 10, 0) + (5, 0, 0) = (5, 10, 0)
        
        f_pos = finger.get_global_position()
        self.assertAlmostEqual(f_pos.x, 5.0)
        self.assertAlmostEqual(f_pos.y, 10.0)
        self.assertAlmostEqual(f_pos.z, 0.0)

if __name__ == '__main__':
    unittest.main()
