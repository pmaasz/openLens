#!/usr/bin/env python3
"""Tests for Matrix4x4, including the inverse used by the 3D tracer."""

import math
import unittest

from src.transform import Matrix4x4


def _identity_error(rows):
    """Max |entry - identity| over a raw 4x4 row list."""
    return max(abs(rows[i][j] - (1.0 if i == j else 0.0)) for i in range(4) for j in range(4))


class TestMatrixInverse(unittest.TestCase):
    """inverse() must exist, be exact for translations, and reject singular."""

    def test_translation_inverse_exact(self):
        """Translation inverse is bit-exact (hot path for untilted tracers)."""
        mat = Matrix4x4.from_translation(30.0, -2.5, 0.0)
        err = _identity_error((mat * mat.inverse()).m)
        self.assertEqual(err, 0.0)

    def test_composed_inverse(self):
        """Rotation+translation round-trips to identity."""
        mat = Matrix4x4.from_translation(10, 3, -7) * Matrix4x4.from_euler(15, -30, 45)
        self.assertLess(_identity_error((mat * mat.inverse()).m), 1e-12)

    def test_inverse_reverses_points(self):
        """A point transformed forth and back lands where it started."""
        from src.vector3 import vec3

        mat = Matrix4x4.from_translation(5, -3, 2) * Matrix4x4.from_euler(0, 0, 10)
        original = vec3(1.5, -4.25, 7.0)
        there = mat.multiply_point(original)
        back = mat.inverse().multiply_point(there)
        self.assertAlmostEqual(back.x, original.x, places=9)
        self.assertAlmostEqual(back.y, original.y, places=9)
        self.assertAlmostEqual(back.z, original.z, places=9)

    def test_singular_raises(self):
        """Zero-scale matrices cannot be inverted."""
        with self.assertRaises(ValueError):
            Matrix4x4.from_scale(1, 0, 1).inverse()

    def test_euler_orthonormal(self):
        """Pure rotations invert to their transpose."""
        mat = Matrix4x4.from_euler(20, 30, 40)
        inv = mat.inverse().m
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(inv[i][j], mat.m[j][i], places=12)


if __name__ == "__main__":
    unittest.main()
