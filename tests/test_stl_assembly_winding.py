#!/usr/bin/env python3
"""
The exported assembly must be a solid, not an inside-out shell.

The assembly branch of the STL exporter generated the back cap with the
default ``is_front=True``, so half of every exported solid had its normals
pointing into the glass. The signed volume of the mesh was negative - the
divergence-theorem sign of an inverted solid - and slicers read that as
inverted material (or refused the file).
"""

import math
import os
import struct
import sys
import tempfile
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openlens.lens import Lens
from openlens.optical_system import OpticalSystem
from openlens.stl_export import export_lens_stl


def _read_triangles(path):
    """The triangles of a binary STL file."""
    with open(path, "rb") as handle:
        data = handle.read()
    count = struct.unpack("<I", data[80:84])[0]
    triangles = []
    offset = 84
    for _ in range(count):
        values = struct.unpack("<12fH", data[offset : offset + 50])
        offset += 50
        triangles.append((values[3:6], values[6:9], values[9:12]))
    return triangles


def _signed_volume(triangles):
    """The divergence-theorem volume: negative for an inverted solid."""
    total = 0.0
    for a, b, c in triangles:
        total += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        )
    return total / 6.0


def _analytic_volume(radius, thickness, diameter):
    """The volume of a biconvex lens, ignoring the facet chord error."""
    r = abs(radius)
    h = diameter / 2.0
    integral = r * h * h / 2.0 - (r**3 - (r * r - h * h) ** 1.5) / 3.0
    return 2 * math.pi * (thickness * h * h / 2.0 - 2 * integral)


class TestAssemblyExportIsNotInsideOut(unittest.TestCase):
    """The exported mesh must be a solid with outward normals."""

    def setUp(self):
        self.system = OpticalSystem("doublet")
        self.system.add_lens(
            Lens(
                name="L1",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
            )
        )
        self.system.add_lens(
            Lens(
                name="L2",
                radius_of_curvature_1=40.0,
                radius_of_curvature_2=-40.0,
                thickness=4.0,
                diameter=25.0,
                refractive_index=1.5168,
            ),
            air_gap_before=2.0,
        )
        handle, self.path = tempfile.mkstemp(suffix=".stl")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def test_the_exported_assembly_has_a_positive_volume(self):
        """An inverted mesh has a negative signed volume"""
        export_lens_stl(self.system, self.path, resolution=20)

        volume = _signed_volume(_read_triangles(self.path))

        self.assertGreater(
            volume,
            0.0,
            msg="the exported assembly is inside-out (its signed volume is negative)",
        )

    def test_the_exported_volume_is_the_lenses_volume(self):
        """The mesh must hold the glass, not enclose the negative space"""
        export_lens_stl(self.system, self.path, resolution=20)

        volume = _signed_volume(_read_triangles(self.path))
        expected = _analytic_volume(50.0, 5.0, 25.0) + _analytic_volume(40.0, 4.0, 25.0)

        # The facets are chords, so the mesh is a little smaller than the
        # exact solid - but nowhere near the other sign.
        self.assertGreater(volume, expected * 0.9)
        self.assertLess(volume, expected * 1.05)


class TestAssemblyRespectsAlignment(unittest.TestCase):
    """A moved or tilted element must move in the exported assembly."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._next = 0

    def _export(self, **alignment):
        self._next += 1
        system = OpticalSystem("aligned")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5168,
            )
        )
        system.add_lens(
            Lens(
                radius_of_curvature_1=40.0,
                radius_of_curvature_2=-40.0,
                thickness=4.0,
                diameter=25.0,
                refractive_index=1.5168,
            ),
            air_gap_before=2.0,
        )
        if alignment:
            system.set_element_alignment(1, **alignment)

        path = os.path.join(self._tmp.name, "assembly%d.stl" % self._next)
        export_lens_stl(system, path, resolution=8)
        return _read_triangles(path)

    def test_decenter_moves_the_element_mesh(self):
        aligned = self._export()
        moved = self._export(decenter_y=3.0)

        self.assertFalse(moved == aligned, "the decentered element was exported on-axis")

    def test_tilt_rotates_the_element_mesh(self):
        aligned = self._export()
        tilted = self._export(tilt_y=5.0)

        self.assertFalse(tilted == aligned, "the tilted element was exported unrotated")


if __name__ == "__main__":
    unittest.main()
