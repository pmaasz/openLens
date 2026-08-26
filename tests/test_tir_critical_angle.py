#!/usr/bin/env python3
"""
Total internal reflection at the BK7 -> air critical angle.

Critical angle: theta_c = arcsin(n_air / n_BK7) = arcsin(1 / 1.5168)
              = 41.2354 degrees (locks the Ray.refract TIR contract).
"""

import math
import unittest

from src.ray_tracer import Ray

N_BK7 = 1.5168
CRITICAL_DEG = math.degrees(math.asin(1.0 / N_BK7))  # 41.2354...


class TestTIRCriticalAngle(unittest.TestCase):
    """Ray.refract behaviour around the BK7 -> air critical angle"""

    def _refract_out_of_glass(self, incidence_deg):
        ray = Ray(x=0.0, y=0.0, angle_rad=math.radians(incidence_deg))
        ray.n = N_BK7  # travelling inside glass towards the exit surface
        # Flat surface: normal along +x; incident direction makes the
        # angle with the normal equal to the ray's own angle.
        tir = not ray.refract(N_BK7, 1.0, surface_normal_angle=0.0)
        return tir, ray

    def test_critical_angle_value(self):
        """Sanity on the physics constant itself"""
        self.assertAlmostEqual(CRITICAL_DEG, 41.2452, places=4)

    def test_below_critical_refracts(self):
        """41.0 deg < theta_c: refraction succeeds"""
        tir, ray = self._refract_out_of_glass(CRITICAL_DEG - 0.25)
        self.assertFalse(tir)
        # Snell: sin(theta_t) = n * sin(theta_i) must be <= 1 and near 1 here
        theta_t = math.degrees(math.atan2(
            math.sin(ray.angle_rad), math.cos(ray.angle_rad)))
        self.assertGreater(theta_t, 80.0)   # grazing-ish exit
        self.assertLessEqual(theta_t, 90.0 + 1e-9)

    def test_above_critical_tir(self):
        """41.5 deg > theta_c: total internal reflection, angle preserved"""
        tir, ray = self._refract_out_of_glass(CRITICAL_DEG + 0.25)
        self.assertTrue(tir)
        # Reflected ray travels back into the glass: mirrored about normal
        expected = math.radians(180.0 - (CRITICAL_DEG + 0.25))
        self.assertAlmostEqual(ray.angle_rad, expected, places=9)

    def test_at_critical_grazes_surface(self):
        """Exactly at theta_c the refracted ray grazes at ~90 degrees"""
        tir, ray = self._refract_out_of_glass(CRITICAL_DEG - 1e-9)
        self.assertFalse(tir)
        theta_t = math.degrees(abs(ray.angle_rad))
        self.assertAlmostEqual(theta_t, 90.0, delta=1e-3)


if __name__ == "__main__":
    unittest.main()
