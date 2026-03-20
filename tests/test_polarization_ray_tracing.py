import unittest
import math
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

try:
    import numpy as np
    from ray_tracer import Ray3D, HAS_POLARIZATION
    from vector3 import vec3, Vector3
    from polarization import PolarizationCalculator
    HAS_NUMPY = True
    print(f"DEBUG: numpy imported successfully. HAS_POLARIZATION={HAS_POLARIZATION}")
except ImportError as e:
    HAS_NUMPY = False
    print(f"DEBUG: Failed to import numpy or modules: {e}")

class TestPolarizationRayTracing(unittest.TestCase):
    
    def setUp(self):
        if not HAS_NUMPY:
            self.skipTest("Numpy not available")
            
        self.n1 = 1.0
        self.n2 = 1.5
        
        # Calculate Brewster angle: tan(theta) = n2/n1
        self.brewster_angle_rad = math.atan(self.n2 / self.n1)
        self.brewster_angle_deg = math.degrees(self.brewster_angle_rad)
        
        # Normal pointing up (Y axis)
        self.normal = vec3(0, 1, 0)
        
        # Incident direction for Brewster angle (from air to glass)
        # Ray coming from top-left, hitting surface at (0,0,0)
        # Angle is measured from normal.
        # ray direction: x = sin(theta), y = -cos(theta)
        sin_b = math.sin(self.brewster_angle_rad)
        cos_b = math.cos(self.brewster_angle_rad)
        
        self.incident_dir = vec3(sin_b, -cos_b, 0).normalize()
        self.origin = vec3(0, 10, 0) # Arbitrary start

    def test_brewster_p_polarization_reflection(self):
        """P-polarized light at Brewster angle should have 0 reflectance"""
        
        # P-polarization is in the plane of incidence.
        # Plane is defined by Z=0 (since dir and normal have z=0).
        # So s-polarization is along Z.
        # p-polarization is in X-Y plane, perpendicular to direction.
        
        # Construct p-pol vector: direction x s-vector
        # s-vector = direction x normal = (0, 0, -1) (approx)
        s_vec = self.incident_dir.cross(self.normal).normalize()
        # p-vector = s x direction
        p_vec = s_vec.cross(self.incident_dir).normalize()
        
        # Create ray with p-polarization
        p_pol_array = np.array([p_vec.x, p_vec.y, p_vec.z], dtype=complex)
        
        ray = Ray3D(self.origin, self.incident_dir, n=self.n1, polarization_vector=p_pol_array)
        
        # Reflect
        # Note: Ray3D.reflect modifies the ray in place
        ray.reflect(self.normal, self.n1, self.n2)
        
        # Intensity should be effectively 0
        # (Brewster angle means p-reflectance is 0)
        self.assertLess(ray.intensity, 1e-4, "Reflected intensity for p-pol at Brewster angle should be ~0")
        
        # Check E-field magnitude is also small
        E_mag_sq = np.sum(np.abs(ray.polarization_vector)**2)
        self.assertLess(E_mag_sq, 1e-4)

    def test_brewster_s_polarization_reflection(self):
        """S-polarized light at Brewster angle should have non-zero reflectance"""
        
        # s-polarization is perpendicular to plane (along Z axis)
        s_vec = self.incident_dir.cross(self.normal).normalize()
        
        s_pol_array = np.array([s_vec.x, s_vec.y, s_vec.z], dtype=complex)
        
        ray = Ray3D(self.origin, self.incident_dir, n=self.n1, polarization_vector=s_pol_array)
        
        ray.reflect(self.normal, self.n1, self.n2)
        
        # Intensity should be significant
        # Calculate expected Fresnel reflectance
        calc = PolarizationCalculator()
        coeffs = calc.reflectance_transmittance(self.n1, self.n2, self.brewster_angle_deg)
        expected_Rs = coeffs['R_s']
        
        self.assertGreater(ray.intensity, 0.01)
        self.assertAlmostEqual(ray.intensity, expected_Rs, places=4)

    def test_refraction_transmission(self):
        """Test transmission logic updates E-field correctly"""
        
        # Normal incidence
        incident_dir = vec3(0, -1, 0)
        s_vec = vec3(0, 0, 1) # Arbitrary s
        
        pol_array = np.array([0, 0, 1], dtype=complex) # s-polarized
        
        ray = Ray3D(self.origin, incident_dir, n=self.n1, polarization_vector=pol_array)
        
        # Refract
        ray.refract(self.n1, self.n2, self.normal)
        
        # Check intensity
        # T = 4*n1*n2 / (n1+n2)^2 for normal incidence
        expected_T = (4 * self.n1 * self.n2) / (self.n1 + self.n2)**2
        
        self.assertAlmostEqual(ray.intensity, expected_T, places=4)

if __name__ == '__main__':
    unittest.main()
